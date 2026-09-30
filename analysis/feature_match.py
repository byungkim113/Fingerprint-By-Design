"""Explicit DAC-pattern fingerprint: estimate each burst's DAC unit steps from
the received signal and match against templates enrolled at one temperature.

Receiver: matched filter -> QPSK decisions -> rebuild the ideal shaped
waveform -> per-sample I and Q DAC codes -> least-squares fit of the received
signal on one-hot code indicators (complex weight per code level) -> unit
levels minus ideal levels.

Features: complex deviation of every observed DAC level from the ideal DAC
(offset, gain error, nonlinearity, I/Q imbalance), projected with LDA fitted
on enrollment bursts, centered on the enrollment population mean.

Matchers
  absolute : Euclidean distance to each enrolled template (keeps size)
  shape    : cosine similarity (discards the size of the deviation vector,
             keeps its direction)

usage: python feature_match.py <exp_name> [--snr 20] [--train-t 27] [--avg 1]
"""
import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

from txmodel import H_RRC, N_DATA, N_PRE, SPS, load_params, transmit

RESULTS = Path(__file__).resolve().parents[1] / "results"
LO_CODE, HI_CODE = 5, 26          # code levels observed with this pulse shaping
N_LEV = HI_CODE - LO_CODE + 1


def _preamble():
    return np.exp(1j * np.pi / 4 * (2 * np.random.default_rng(12345).integers(0, 4, N_PRE) + 1))


def estimate_levels(z, pa_terms=True):
    """z: (n_bursts, L) received, preamble-normalized -> (n_bursts, 2, N_LEV)
    complex DAC level estimates minus the ideal DAC levels (offset, gain error,
    nonlinearity and I/Q imbalance all remain; PA compression is absorbed by
    x|x|^2, x|x|^4 regressors when pa_terms)."""
    ideal = 2 * np.arange(LO_CODE, HI_CODE + 1) / 31 - 1
    out = np.full((len(z), 2, N_LEV), np.nan, complex)
    for b, r in enumerate(z):
        s = np.convolve(r, H_RRC, "same")[::SPS]
        # same constellation expression as the transmitter: waveform samples
        # that sit exactly on the mid-code boundary must round identically
        k = np.round((np.angle(s) - np.pi / 4) / (np.pi / 2)).astype(int) % 4
        sym = np.exp(1j * np.pi / 4 * (2 * k + 1))
        sym[:N_PRE] = _preamble()
        up = np.zeros(len(r), complex)
        up[::SPS] = sym
        x = np.convolve(up, H_RRC, "same")
        x /= np.abs(x).max()
        codes = [np.round((comp + 1) / 2 * 31).astype(int) for comp in (x.real, x.imag)]
        keep = np.all([(c >= LO_CODE) & (c <= HI_CODE) for c in codes], 0)
        cols = [np.eye(N_LEV)[c[keep] - LO_CODE] for c in codes]
        xi = ideal[codes[0][keep] - LO_CODE] + 1j * ideal[codes[1][keep] - LO_CODE]
        extra = [xi * np.abs(xi) ** 2, xi * np.abs(xi) ** 4] if pa_terms else []
        # I levels map onto the real axis, Q levels onto j; Q's code-LO column
        # is dropped (shared constant), its level is recovered from I's offset
        A = np.column_stack([cols[0], 1j * cols[1][:, 1:], *extra])
        w, *_ = np.linalg.lstsq(A, r[keep], rcond=None)
        out[b, 0] = w[:N_LEV] - ideal
        out[b, 1] = np.concatenate([[0], w[N_LEV:2 * N_LEV - 1]]) - (ideal - ideal[0])
    return out


def flat(lev):
    """(..., 2, N_LEV) complex -> (..., 4*N_LEV) real feature vector."""
    v = lev.reshape(*lev.shape[:-2], -1)
    return np.concatenate([v.real, v.imag], -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--snr", type=float, default=20)
    ap.add_argument("--train-t", type=float, default=27)
    ap.add_argument("--n-enroll", type=int, default=40)
    ap.add_argument("--n-test", type=int, default=10)
    ap.add_argument("--avg", type=int, default=1, help="bursts averaged per test decision")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    p = load_params()
    temps = list(p.temps)
    n_chips = p.dac_units.shape[1]
    ti0 = temps.index(a.train_t)

    enroll = np.stack([flat(estimate_levels(transmit(p, ti0, c, np.random.default_rng(10_000 * a.seed + c),
                                                     a.snr, a.n_enroll), pa_terms=False))
                       for c in range(n_chips)])                       # chip, burst, feat
    # LDA fitted on enrollment bursts only (the receiver never sees other T):
    # weights feature directions by between-chip vs within-chip (noise) spread
    keep = enroll.reshape(-1, enroll.shape[-1]).std(0) > 0
    lda = LinearDiscriminantAnalysis(solver="eigen", shrinkage="auto")
    lda.fit(enroll[..., keep].reshape(-1, keep.sum()), np.repeat(np.arange(n_chips), a.n_enroll))
    proj = lambda f: lda.transform(f[..., keep].reshape(-1, keep.sum())).reshape(*f.shape[:-1], -1)
    e = proj(enroll)
    mu = e.reshape(-1, e.shape[-1]).mean(0)
    tpl = e.mean(1) - mu
    tpl_n = tpl / np.linalg.norm(tpl, axis=1, keepdims=True)

    res = {"absolute": {}, "shape": {}}
    for ti, t in enumerate(temps):
        n = a.n_test * a.avg
        v = np.stack([flat(estimate_levels(transmit(p, ti, c,
                                                    np.random.default_rng(10_000 * a.seed + 5000 + 300 * ti + c),
                                                    a.snr, n), pa_terms=False)) for c in range(n_chips)])
        v = v.reshape(n_chips, a.n_test, a.avg, -1).mean(2)
        v = proj(v) - mu
        truth = np.arange(n_chips)[:, None]
        d = ((v[:, :, None, :] - tpl[None, None]) ** 2).sum(-1)
        res["absolute"][f"{t:g}"] = float((d.argmin(-1) == truth).mean())
        sim = (v / np.linalg.norm(v, axis=-1, keepdims=True)) @ tpl_n.T
        res["shape"][f"{t:g}"] = float((sim.argmax(-1) == truth).mean())
        print(f"T={t:5g}  absolute {res['absolute'][f'{t:g}']:.3f}   shape {res['shape'][f'{t:g}']:.3f}",
              flush=True)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{a.name}.json").write_text(json.dumps(dict(vars(a), **res, chance=1 / n_chips), indent=1))


if __name__ == "__main__":
    main()
