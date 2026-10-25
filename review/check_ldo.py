"""Fresh LDO DC and startup checks; retain logs and measurements, not study data."""
import concurrent.futures
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sim'))
import ldo
from spice import SPINIT
import numpy as np

LAID_OUT = '--laid-out' in sys.argv
PEX = '--pex' in sys.argv
OUT = ROOT / ('review/ldo-pex-output' if PEX else 'review/ldo-layout-values-output' if LAID_OUT else 'review/ldo-output')
OUT.mkdir(exist_ok=True)

def startup(job):
    temp, ramp = job
    d = OUT / f'T{temp}_ramp{ramp}us'
    d.mkdir(exist_ok=True)
    stop = max(100e-6, 2 * ramp * 1e-6)
    control = f'save v(vout) v(vin)\ntran 10n {stop} 0 50n\nwrdata wave.txt v(vout) v(vin)'
    text = ldo.bench(control, temp=temp, vin=3.63)
    if PEX:
        extracted = ROOT / 'review/ldo-pex/ldo_blk_pex_c.spice'
        text = text.replace('X1 vin vout 0 ldo', f'.include "{extracted}"\nX1 vin vout 0 ldo_blk')
    if LAID_OUT:
        text = text.replace('XCss ldo_vss_ref VSS sky130_fd_pr__cap_mim_m3_1 W=70 L=70',
                            'XCss ldo_vss_ref VSS sky130_fd_pr__cap_mim_m3_1 W=30 L=30')
    text = text.replace('Vin vin 0 3.63', f'Vin vin 0 PWL(0 0 {ramp}u 3.63)')
    shutil.copy(SPINIT, d / '.spiceinit')
    (d / 'c.sp').write_text(text)
    r = subprocess.run(['ngspice', '-b', 'c.sp'], cwd=d, capture_output=True, text=True, timeout=300)
    (d / 'ngspice.log').write_text(r.stdout + r.stderr)
    result = dict(temp=temp, ramp_us=ramp, returncode=r.returncode)
    if (d / 'wave.txt').exists():
        a = np.loadtxt(d / 'wave.txt')
        if a.ndim == 2:
            result.update(stop_s=float(a[-1, 0]), complete=bool(a[-1, 0] >= stop * .9999),
                          peak_V=float(a[:, 1].max()), final_V=float(a[-1, 1]))
    print(result, flush=True)
    return result

if __name__ == '__main__':
    jobs = [(t, ramp) for t in (-40, 27, 85) for ramp in ((1, 50) if (LAID_OUT or PEX) else (1, 10, 50, 200, 1000))]
    with concurrent.futures.ThreadPoolExecutor(2) as ex:
        results = list(ex.map(startup, jobs))
    (OUT / 'startup.json').write_text(json.dumps(results, indent=2))
