"""Identification accuracy vs. the number of frames averaged per received burst (review follow-up, 2026-10-25).

The headline results use bursts of REPS = 18 repetitions of the 128-sample frame (2,304 samples, 92.16 us at 25 MS/s)
for every enrolment and test decision. This reruns the same analysis as tx_more_tests.py ("more": 16 / 32 / 64 chips,
27 C, BASE classifier, masked features, 40 enrolment and 10 test bursts per chip, 3 noise seeds) with fewer frames per
burst. SNR is per received sample, so averaging R frames improves the fingerprint SNR by about 10*log10(R) dB.
The REPS = 18 row must reproduce results/tx_more_chips.json.

usage: python tx_burst_length.py      -> results/tx_burst_length.json
"""
import json

import numpy as np

import tx_full as tx
import tx_ident as ti
import tx_more_tests as mt

REPS_LIST = (1, 2, 4, 9, 18)
SNRS = (30.0, 20.0, 15.0, 10.0)


def main():
    cache = tx.WORK / "burst_length_frames.npy"
    if cache.exists():
        Y = np.load(cache)
    else:
        Y = np.concatenate([mt.frames(ti.run_dir("tt_mm", 27.0), range(1, 17)),
                            mt.frames(tx.WORK / "ident_more_a_tt_mm_T27", range(17, 41)),
                            mt.frames(tx.WORK / "ident_more_b_tt_mm_T27", range(41, 65))])
        np.save(cache, Y)
    out = {}
    for reps in REPS_LIST:
        ti.REPS = reps                                   # bursts() reads the module-level REPS
        out[reps] = {}
        for n in (16, 64):
            out[reps][n] = {f"{snr:g}dB": mt.accuracy(Y[:n], {"27": Y[:n]}, snr)["27"] for snr in SNRS}
            print(f"frames/burst {reps:2d}  N={n:2d}: " + "  ".join(f"{k}: {v:.4f}" for k, v in out[reps][n].items()),
                  flush=True)
    ref = json.loads((ti.RESULTS / "tx_more_chips.json").read_text())
    same = all(abs(out[18][n][k] - ref[str(n)][k]) < 1e-12 for n in (16, 64) for k in out[18][n])
    print("REPS=18 reproduces tx_more_chips.json:", same)
    (ti.RESULTS / "tx_burst_length.json").write_text(json.dumps(
        {"frames_per_burst": {str(r): {str(n): v for n, v in d.items()} for r, d in out.items()},
         "samples_per_frame": ti.N_SAMPLES, "sample_rate_Hz": tx.FS, "reproduces_reference": same}, indent=1))


if __name__ == "__main__":
    main()
