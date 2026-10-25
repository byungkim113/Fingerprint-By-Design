"""Cross-check the front end's played-back frame (tb/played.txt, written by the testbench)
against the frame and thermometer coding the transistor-level simulations used
(sim/tx_full.py, TX_FRAME=1). usage: python check_playback.py"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "sim"))
import tx_full as tx  # noqa: E402

ci, cq, _ = tx.qpsk_codes(128, seed=1)
played = np.loadtxt(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "played.txt", dtype=int)
want_i, want_q = tx.thermometer(ci).sum(0), tx.thermometer(cq).sum(0)
ok = played.shape == (128, 2) and (played[:, 0] == want_i).all() and (played[:, 1] == want_q).all()
print(f"{len(played)} samples; matches sim/tx_full.py frame and thermometer: {'PASS' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
