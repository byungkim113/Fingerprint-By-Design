"""Execute the actual notebook's code cells locally, preserving figures and output."""
import contextlib
import io
import json
import os
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'review/notebook-output'
OUT.mkdir(parents=True, exist_ok=True)
os.environ['MPLBACKEND'] = 'Agg'
import matplotlib.pyplot as plt

count = 0
def show(*args, **kwargs):
    global count
    for n in plt.get_fignums():
        count += 1
        plt.figure(n).savefig(OUT / f'figure-{count:02d}.png', dpi=100)
    plt.close('all')
plt.show = show

nb = json.loads((ROOT / 'notebook/fingerprint_by_design.ipynb').read_text(encoding='utf-8'))
os.chdir(ROOT / 'notebook')
env = {'__name__': '__main__'}
log = io.StringIO()
ok = 0
with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
    for index, cell in enumerate(nb['cells']):
        if cell['cell_type'] != 'code':
            continue
        print('CELL', index, flush=True)
        try:
            exec(compile(''.join(cell['source']), f'notebook-cell-{index}', 'exec'), env)
            ok += 1
        except Exception:
            traceback.print_exc()
            (OUT / 'execution.log').write_text(log.getvalue(), encoding='utf-8')
            print(log.getvalue(), file=__import__('sys').__stdout__)
            raise
(OUT / 'execution.log').write_text(log.getvalue(), encoding='utf-8')
print(log.getvalue())
print('PASS:', ok, 'code cells;', count, 'figures')
