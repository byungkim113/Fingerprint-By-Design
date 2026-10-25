"""Focused reproducible review checks; run with the review Python environment."""
import ast
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'sim'), str(ROOT / 'analysis')]
import numpy as np
import tx_full as tx
import tx_ident as ti
from tx_validate import level_fit
from live_demo import demo_codes

errors = []
for folder in ('sim', 'analysis', 'layout', 'notebook'):
    paths = list((ROOT / folder).rglob('*.py'))
    for p in paths:
        ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    print('Python syntax', folder, len(paths), 'PASS')
for p in (ROOT / 'notebook' / 'sim').glob('*.py'):
    print('Bundled script identical', p.name, p.read_bytes() == (ROOT / 'sim' / p.name).read_bytes())
for p in (ROOT / 'notebook' / 'data').glob('*.json'):
    json.loads(p.read_text())
    original = ROOT / 'results' / p.name
    if original.exists() and p.read_bytes() != original.read_bytes():
        errors.append('Bundled result differs: ' + p.name)
for name, original in [('tx_core', ROOT / 'layout/tx_core.gds'), ('tx_frontend', ROOT / 'digital/final/tx_frontend.gds.gz')]:
    data = gzip.decompress((ROOT / f'notebook/gds/{name}.gds.gz').read_bytes())
    other = original.read_bytes()
    if original.suffix == '.gz':
        other = gzip.decompress(other)
    print('Bundled GDS identical', name, data == other)

print('RRC energy', np.sum(__import__('txmodel').H_RRC ** 2))
print('Thermometer exhaustive', np.array_equal(tx.thermometer(np.arange(32)).sum(0), np.arange(32)))
ci, cq, _ = tx.qpsk_codes(128, seed=1)
frame = np.loadtxt(ROOT / 'digital/tb/frame.hex', dtype=str)
words = np.array([int(v, 16) for v in frame])
print('Digital frame matches analog stimulus', np.array_equal(words, ci * 32 + cq))

for name, codes in [(f'frame{f}', tx.qpsk_codes(128, seed=f)[:2]) for f in range(1, 6)] + [('demo', demo_codes())]:
    ci, cq = codes
    keep = (ci >= 5) & (ci <= 26) & (cq >= 5) & (cq <= 26)
    A = np.concatenate([np.eye(22)[ci[keep]-5], np.eye(22)[cq[keep]-5][:, 1:]], 1)
    active = np.any(A, axis=0)
    rank = np.linalg.matrix_rank(A)
    print('Level fit rank', name, 'rows', len(A), 'rank', rank, 'observed columns', active.sum())
    x = (2*ci/31-1) + 1j*(2*cq/31-1)
    li, lq, si, sq = level_fit(x, ci, cq)
    ti.MASKED = False
    f = ti.features(x, ci, cq)
    ti.MASKED = True
    fm = ti.features(x, ci, cq)
    print('Ideal linear ladder residual rms', name, 'unmasked', np.sqrt(np.mean(f*f)), 'masked', np.sqrt(np.mean(fm*fm)))
    ti.MASKED = False

# A known sinusoid verifies the sign and amplitude of RF downconversion.
t = np.arange(0, 4/tx.FS + 1e-12, 20e-12)
expected = .2 + .1j
v = np.real(expected * np.exp(2j*np.pi*tx.FLO*t))
y = tx.downconvert(t, v, 4)
print('Downconversion max complex error', float(np.max(np.abs(y-expected))))

from robust2 import mahalanobis_acc, mixture_acc, noise_cov, drift_model
from scipy.spatial.distance import cdist
rng = np.random.default_rng(975)
en = rng.normal(size=(4, 12, 6))
test = rng.normal(size=(4, 8, 6))
keep = np.ones(6, dtype=bool)
sw = noise_cov(en, keep)
truth = np.repeat(np.arange(4), 8)
direct = float(np.mean(cdist(test.reshape(-1, 6), en.mean(1), 'mahalanobis', VI=np.linalg.inv(sw)).argmin(1) == truth))
calculated = mahalanobis_acc(en, {0: test}, keep, sw)[0]
mixture = mixture_acc(en, test, keep, sw, np.zeros((1, 6)), np.zeros((1, 6, 6)))
assert abs(direct-calculated) < 1e-12 and abs(direct-mixture) < 1e-12
print('Mahalanobis and one-component Gaussian mixture vs independent scipy distances: PASS', direct)
archives = list((ROOT / 'data').glob('*.npz'))
for p in archives:
    with np.load(p) as archive:
        for key in archive.files:
            a = archive[key]
            if np.issubdtype(a.dtype, np.number) and not np.isfinite(a).all():
                errors.append(f'Non-finite archive values: {p.name}:{key}')
print('Finite numeric arrays in source archives:', len(archives))
print('Errors', errors)
assert not errors
