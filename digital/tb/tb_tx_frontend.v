// Self-checking testbench for tx_frontend: SPI register access, loading the main study's
// 128-sample frame, reading it all back, one-shot playback, looped playback of a
// full-range ramp across the frame boundary, stopping mid-frame, and a clean restart.
// Every output line is compared with the thermometer rule (unit k on iff k < code) and its
// complement on every playback cycle. Writes the played-back codes to played.txt so
// check_playback.py can compare them with sim/tx_full.py directly.
`timescale 1ns/1ps
`default_nettype none
module tb;
    reg clk = 0, rst_n = 0, sck = 0, csb = 1, mosi = 0;
    wire miso, running;
    wire [30:0] di, dbi, dq, dbq;
    tx_frontend dut(.clk(clk), .rst_n(rst_n), .sck(sck), .csb(csb), .mosi(mosi), .miso(miso),
                    .di(di), .dbi(dbi), .dq(dq), .dbq(dbq), .running(running));
    always #20 clk = ~clk;                        // 25 MHz sample clock

    integer errors = 0, checks = 0, k, f;
    reg [9:0] frame [0:127];
    reg [9:0] ramp  [0:127];
    reg [31:0] rx;
    reg [15:0] d;

    task spi(input [31:0] tx, output [31:0] r);   // mode 0, 2.5 MHz
        integer b;
        begin
            csb = 0; #200;
            for (b = 31; b >= 0; b = b - 1) begin
                mosi = tx[b]; #200; sck = 1; r = {r[30:0], miso}; #200; sck = 0;
            end
            #200 csb = 1; #400;
        end
    endtask
    task wr(input [7:0] a, input [15:0] v); begin spi({1'b1, 7'd0, a, v}, rx); end endtask
    task rd(input [7:0] a, output [15:0] v); begin spi({1'b0, 7'd0, a, 16'd0}, rx); v = rx[15:0]; end endtask

    function [30:0] thermo(input [4:0] c);
        integer j;
        for (j = 0; j < 31; j = j + 1) thermo[j] = (j < c);
    endfunction
    // sample outputs mid-cycle: in gate-level simulation they change a few ns after the clock edge
    task tick; begin @(posedge clk); @(negedge clk); end endtask
    task fail(input [255:0] what); begin errors = errors + 1; if (errors < 10) $display("FAIL %0s", what); end endtask
    task expect_out(input [9:0] w, input [255:0] what);
        begin
            checks = checks + 1;
            if (di !== thermo(w[9:5]) || dbi !== ~thermo(w[9:5]) || dq !== thermo(w[4:0]) || dbq !== ~thermo(w[4:0])) begin
                if (errors < 10) $display("  want I=%0d Q=%0d  got di=%h dbi=%h dq=%h dbq=%h", w[9:5], w[4:0], di, dbi, dq, dbq);
                fail(what);
            end
        end
    endtask
    task readback(input integer which, input [255:0] what);   // 0: frame, 1: ramp
        begin
            for (k = 0; k < 128; k = k + 1) begin
                rd(8'h00, d); checks = checks + 1;
                if (d[9:0] !== (which ? ramp[k] : frame[k])) fail(what);
            end
        end
    endtask
    task play(input integer which, input integer n, input [15:0] ctrl, input integer log);
        fork                                      // playback starts before the SPI task returns
            wr(8'h80, ctrl);
            begin
                @(posedge running);
                for (k = 0; k < n; k = k + 1) begin
                    tick; expect_out(which ? ramp[k % 128] : frame[k % 128], "playback");
                    if (log) $fdisplay(f, "%0d %0d", $countones(di), $countones(dq));
                end
            end
        join
    endtask

    initial begin
        $readmemh("frame.hex", frame);
        for (k = 0; k < 128; k = k + 1) ramp[k] = {k[4:0], 5'd31 - k[4:0]};   // all 32 codes, 4 times
        #100 rst_n = 1; #200;

        // 1. ID register and reset state
        rd(8'h83, d); checks = checks + 1; if (d !== 16'hF1D0) fail("ID");
        expect_out({5'd16, 5'd16}, "reset idle");

        // 2. load the frame, read all of it back (128 reads leave the ring as loaded)
        for (k = 0; k < 128; k = k + 1) wr(8'h00, {6'd0, frame[k]});
        readback(0, "frame readback");

        // 3. one-shot playback of all 128 samples, then idle, frame still intact
        f = $fopen("played.txt", "w");
        play(0, 128, 16'h0001, 1);
        $fclose(f);
        tick; expect_out({5'd16, 5'd16}, "idle after frame");
        checks = checks + 1; if (running) fail("still running");
        readback(0, "frame after playback");

        // 4. full-range ramp, looped: 300 samples cross the frame boundary twice
        for (k = 0; k < 128; k = k + 1) wr(8'h00, {6'd0, ramp[k]});
        play(1, 300, 16'h0003, 0);

        // 5. stop mid-frame: idle at once; the ring drains to the frame end and stays in order
        wr(8'h80, 16'h0000);
        @(posedge clk); tick; expect_out({5'd16, 5'd16}, "stopped");
        repeat (140) @(posedge clk);
        readback(1, "ramp after stop");

        // 6. restart one-shot: must begin at sample 0
        play(1, 128, 16'h0001, 0);

        // 7. new idle code and CTRL readback
        wr(8'h82, {6'd0, 5'd0, 5'd31});
        @(posedge clk); tick; expect_out({5'd0, 5'd31}, "new idle");
        rd(8'h80, d); checks = checks + 1; if (d !== 16'h0001) fail("CTRL read");

        $display("%0d checks, %0d errors: %0s", checks, errors, errors ? "FAIL" : "PASS");
        $finish;
    end
    initial begin #20_000_000 $display("TIMEOUT"); $finish; end
endmodule
`default_nettype wire
