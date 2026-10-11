"""Stage 3 simulations (PLAN.md 2026-10-04/05): fresh frames 4, 5 for chips 1-16 at drifted conditions;
design chips (ss_mm/ff_mm seeds 101-106) on the coverage sequence at nominal and the same conditions."""
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
COND = [("vdd162", 27.0), ("vdd198", 27.0), ("vdd180", 85.0), ("vdd162", -40.0)]
JOBS = [(dict(TX_FRAME="cov", TX_TAG="framecov_", TX_VARIANT=v), (c, 101, 6, T))
        for v, T in [("vdd180", 27.0)] + COND for c in ("ss_mm", "ff_mm")]
JOBS += [(dict(TX_FRAME=f, TX_TAG=f"frame{f}_", TX_VARIANT=v), ("tt_mm", 1, 16, T)) for v, T in COND for f in ("4", "5")]


def run(job):
    env, args = job
    subprocess.run([sys.executable, "-c", f"import tx_ident as ti; ti.run_one({args!r})"],
                   cwd=HERE, env=dict(os.environ, **env), check=True)
    return f"done {env} {args}"


if __name__ == "__main__":
    with ThreadPoolExecutor(2) as ex:
        for out in ex.map(run, JOBS):
            print(out, flush=True)
