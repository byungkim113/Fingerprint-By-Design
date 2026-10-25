// Digital front end for the SKY130 transmitter core.
//
// Replaces the core's 124 data pins (31 thermometer lines + complements, I and Q) with an
// SPI port and a sample clock. An outside controller loads a 128-sample I/Q frame (5-bit
// codes) over SPI; the block then plays it back at one sample per clk, decoding each
// code into the 31-line thermometer word the DAC switches need (unit k on iff k < code,
// as in sim/tx_full.py), with registered true and complement outputs so both change on
// the same clock edge.
//
// The frame is held in a 128-word ring of flip-flops rather than an addressed memory:
// playback only ever reads samples in order, so the ring rotates by one word per sample
// and there is no 128-way read multiplexer (a first version with one failed timing and
// slew limits because of it). A full frame rotates the ring 128 times, which leaves it
// in its original order, ready to play again. The ring's 1280 flip-flops run on a gated
// clock (SKY130 integrated clock gate) that only ticks when the ring moves, so they need
// no enable multiplexers and the idle ring draws no clock power.
//
// SPI: mode 0, MSB first, 32-bit frames {rw, 7'b0, addr[7:0], data[15:0]}; rw=1 writes.
// SPI pins are sampled in the clk domain (clk must be at least 8x sck), so the whole
// block has one clock. Reads return the addressed register on miso during the data phase.
//   addr 0x00  DATA: write pushes {I[4:0], Q[4:0]} (data[9:0]) into the ring; after 128
//              writes the ring holds the frame in write order. Read returns the oldest
//              word and rotates, so 128 reads return the frame and restore it.
//   addr 0x80  CTRL: bit0 run, bit1 loop (play the frame continuously)
//   addr 0x82  IDLE: data[9:5] I code, data[4:0] Q code sent while not playing
//   addr 0x83  ID  : read-only 16'hF1D0
// Writing run=1 starts a frame from sample 0. Clearing run sends IDLE at once; the ring
// keeps rotating silently to the end of the frame so it stays in order. Ring access over
// SPI is only meaningful while not playing.
`default_nettype none
module tx_frontend (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        sck,
    input  wire        csb,
    input  wire        mosi,
    output wire        miso,
    output reg  [30:0] di,
    output reg  [30:0] dbi,
    output reg  [30:0] dq,
    output reg  [30:0] dbq,
    output wire        running
);
    localparam N = 128;

    // ---- SPI pins: two-flop synchronisers and edge detection in the clk domain
    reg [2:0] sck_s;
    reg [1:0] csb_s;
    reg [1:0] mosi_s;
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            sck_s <= 3'b000; csb_s <= 2'b11; mosi_s <= 2'b00;
        end else begin
            sck_s <= {sck_s[1:0], sck}; csb_s <= {csb_s[0], csb}; mosi_s <= {mosi_s[0], mosi};
        end
    wire sck_rise = sck_s[1] & ~sck_s[2];
    wire sck_fall = ~sck_s[1] & sck_s[2];
    wire sel = ~csb_s[1];

    // ---- playback state (declared first: the SPI logic uses start_now)
    reg  [6:0]  count;
    reg         active;   // the ring is rotating through a frame
    reg         live;     // this frame started cleanly and run is still set: send samples
    reg         pending;  // run was written; start at the next frame boundary
    wire        start_now = pending & ~active;
    wire        playing = active & live;
    assign running = playing;

    // ---- SPI frame and control registers
    reg  [5:0]  bitcnt;
    reg  [30:0] shreg;
    reg  [15:0] rdata;
    reg         miso_r;
    reg         run, loop;
    reg  [9:0]  idle;
    reg  [9:0]  ring [0:N-1];
    assign miso = miso_r;
    wire [31:0] shnext = {shreg, mosi_s[1]};
    wire addr_done = sel & sck_rise & (bitcnt == 6'd15);
    wire frame_done = sel & sck_rise & (bitcnt == 6'd31);
    wire push = frame_done & shnext[31] & (shnext[23:16] == 8'h00);   // write DATA
    wire pop = addr_done & ~shnext[15] & (shnext[7:0] == 8'h00);      // read DATA

    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            bitcnt <= 0; shreg <= 0; rdata <= 0; miso_r <= 0;
            run <= 0; loop <= 0; pending <= 0; idle <= {5'd16, 5'd16};
        end else begin
            if (start_now) pending <= 0;
            if (!sel) begin
                bitcnt <= 0;
            end else begin
                if (sck_rise) begin
                    shreg  <= shnext[30:0];
                    bitcnt <= bitcnt + 1;
                    if (addr_done)
                        case (shnext[7:0])
                            8'h00:   rdata <= {6'd0, ring[0]};
                            8'h80:   rdata <= {14'd0, loop, run};
                            8'h82:   rdata <= {6'd0, idle};
                            8'h83:   rdata <= 16'hF1D0;
                            default: rdata <= 16'd0;
                        endcase
                    if (frame_done && shnext[31])
                        case (shnext[23:16])
                            8'h80: begin run <= shnext[0]; loop <= shnext[1]; pending <= shnext[0]; end
                            8'h82: idle <= shnext[9:0];
                            default: ;
                        endcase
                end
                if (sck_fall) miso_r <= bitcnt[4] ? rdata[4'd15 - bitcnt[3:0]] : 1'b0;   // data phase
            end
        end

    // ---- playback
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            count <= 0; active <= 0; live <= 0;
        end else if (start_now) begin
            count <= 0; active <= 1; live <= 1;
        end else begin
            if (!run) live <= 0;
            if (active) begin
                count <= count + 1;                            // wraps 127 -> 0
                if (count == 7'd127) begin
                    active <= loop & live & run;
                    if (!(loop & run)) live <= 0;
                end
            end
        end

    // ring: rotate while active or on a DATA read; shift in a new word on a DATA write.
    // Clock gate: the enable is latched while clk is low, so ring_clk only pulses on
    // cycles where the ring moves.
    wire ring_en = active | pop | push;
    wire ring_clk;
`ifdef FE_BEHAVIORAL_ICG
    reg  ring_en_l;                                         // RTL simulation model of the cell
    always @(clk or ring_en) if (!clk) ring_en_l = ring_en;
    assign ring_clk = clk & ring_en_l;
`else
    /* verilator lint_off PINMISSING */   // power pins: connected by the power-grid step
    sky130_fd_sc_hd__dlclkp_4 ring_cg (.CLK(clk), .GATE(ring_en), .GCLK(ring_clk));
    /* verilator lint_on PINMISSING */
`endif
    integer j;
    always @(posedge ring_clk) begin
        for (j = 0; j < N - 1; j = j + 1) ring[j] <= ring[j + 1];
        ring[N - 1] <= push ? shnext[9:0] : ring[0];
    end

    // ---- thermometer decode, registered true and complement outputs
    function [30:0] thermo(input [4:0] code);
        integer k;
        for (k = 0; k < 31; k = k + 1) thermo[k] = (k < code);
    endfunction
    wire [9:0] word = playing ? ring[0] : idle;
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            di <= thermo(5'd16); dbi <= ~thermo(5'd16); dq <= thermo(5'd16); dbq <= ~thermo(5'd16);
        end else begin
            di <= thermo(word[9:5]); dbi <= ~thermo(word[9:5]);
            dq <= thermo(word[4:0]); dbq <= ~thermo(word[4:0]);
        end
endmodule
`default_nettype wire
