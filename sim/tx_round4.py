"""Gated sequence v2 simulations (PLAN.md 2026-10-04): coverage sequence + fresh frames 4, 5 for chips 1-16."""
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS = [dict(TX_FRAME=f, TX_TAG=f"frame{f}_", TX_VARIANT="vdd180") for f in ("cov", "4", "5")]


def run(env):
    subprocess.run([sys.executable, "-c", "import tx_ident as ti; ti.run_one(('tt_mm', 1, 16, 27.0))"],
                   cwd=HERE, env=dict(os.environ, **env), check=True)
    return f"done {env}"


if __name__ == "__main__":
    with ThreadPoolExecutor(2) as ex:
        for out in ex.map(run, JOBS):
            print(out, flush=True)
