"""Method B (M5) on LEARNED features instead of DAC level deviations
(pre-registered in PLAN.md, 2026-10-02).

A CNN (train.Net) is trained at 27 C only on the deployed chips (30 bursts per
chip). Its 128-d penultimate embedding is the feature space. Templates and the
noise covariance come from 10 further 27 C bursts per chip (40 bursts total,
the same budget as the hand-built pipeline). The drift model comes from the
wrong-corner design-time chips passed through the same CNN (noise-free, mean of
4 bursts per chip and temperature). M5 is applied unchanged.

Reported per temperature: CNN softmax accuracy, BASE (Mahalanobis in embedding
space, no drift model) and M5.

usage: python learned_m5.py <design> [--seeds 0,1,2]
"""
import argparse
import json

import numpy as np
import torch
import torch.nn as nn

from drift_test import DEPLOY, RESULTS, T_ENROLL
from generalize import SNR, WRONG, corner_params, deployed
from robust2 import drift_model, mahalanobis_acc, mixture_acc, noise_cov
from train import Net
from txmodel import transmit

N_TRAIN, N_TEMPLATE, N_TEST, N_DRIFT = 30, 10, 10, 4


def bursts(p, ti, chips, seed_fn, snr, n):
    """-> float32 (len(chips), n, 2, L) raw I/Q."""
    out = []
    for c in chips:
        z = transmit(p, ti, c, np.random.default_rng(seed_fn(c)), snr, n)
        out.append(np.stack([z.real, z.imag], 1).astype(np.float32))
    return np.stack(out)


def embed(model, X, dev, bs=256):
    model.eval()
    flat = X.reshape(-1, *X.shape[-2:])
    outs = []
    with torch.no_grad():
        for i in range(0, len(flat), bs):
            outs.append(model.f(torch.from_numpy(flat[i:i + bs]).to(dev)).cpu().numpy())
    return np.concatenate(outs).reshape(*X.shape[:-2], -1)


def softmax_acc(model, X, dev, bs=256):
    model.eval()
    flat = X.reshape(-1, *X.shape[-2:])
    preds = []
    with torch.no_grad():
        for i in range(0, len(flat), bs):
            preds.append(model(torch.from_numpy(flat[i:i + bs]).to(dev)).argmax(1).cpu().numpy())
    truth = np.repeat(np.arange(X.shape[0]), X.shape[1])
    return float((np.concatenate(preds) == truth).mean())


def run(design, seed, epochs=30):
    torch.manual_seed(seed)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    p = deployed(design)
    temps = list(p.temps)
    t0 = temps.index(T_ENROLL)
    chips = list(DEPLOY)

    Xtr = bursts(p, t0, chips, lambda c: 10_000 * seed + c, SNR, N_TRAIN)
    Xtpl = bursts(p, t0, chips, lambda c: 70_000 + 10_000 * seed + c, SNR, N_TEMPLATE)
    tests = {ti: bursts(p, ti, chips, lambda c, ti=ti: 10_000 * seed + 5000 + 300 * ti + c, SNR, N_TEST)
             for ti in range(len(temps))}

    model = Net(len(chips)).to(dev)
    opt = torch.optim.AdamW(model.parameters(), 2e-3, weight_decay=1e-4)
    xt = torch.from_numpy(Xtr.reshape(-1, *Xtr.shape[-2:]))
    yt = torch.from_numpy(np.repeat(np.arange(len(chips)), N_TRAIN))
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 3e-3, total_steps=epochs * (len(xt) // 128 + 1))
    lossf = nn.CrossEntropyLoss()
    for _ in range(epochs):
        model.train()
        perm = torch.randperm(len(xt))
        for i in range(0, len(xt), 128):
            idx = perm[i:i + 128]
            opt.zero_grad()
            lossf(model(xt[idx].to(dev)), yt[idx].to(dev)).backward()
            opt.step()
            sched.step()

    E_tpl = embed(model, Xtpl, dev)                                        # chip, burst, 128
    E_test = {ti: embed(model, X, dev) for ti, X in tests.items()}
    Fs = []
    for k, c in enumerate(WRONG):
        pc = corner_params(design, c, p.unit_nom)
        dchips = range(pc.dac_units.shape[1])
        Fs.append(np.stack([embed(model, bursts(pc, ti, dchips, lambda ch: 99_000 + 1000 * k + ch, 200.0,
                                                N_DRIFT), dev).mean(1) for ti in range(len(temps))]))

    keep = np.ones(E_tpl.shape[-1], bool)
    sw = noise_cov(E_tpl, keep) + 1e-6 * np.eye(E_tpl.shape[-1])
    base = mahalanobis_acc(E_tpl, E_test, keep, sw)
    res = {"softmax": {f"{temps[ti]:g}": softmax_acc(model, X, dev) for ti, X in tests.items()},
           "BASE": {f"{temps[ti]:g}": v for ti, v in base.items()}, "M5": {}}
    interior = {temps.index(0.0), temps.index(55.0)}
    full = drift_model(Fs, temps, t0)
    for ti in range(len(temps)):
        ms, cs = drift_model(Fs, temps, t0, exclude=ti) if ti in interior else full
        res["M5"][f"{temps[ti]:g}"] = mixture_acc(E_tpl, E_test[ti], keep, sw, ms, cs)
    return dict(design=design, seed=seed, snr=SNR, **res)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("--seeds", default="0,1,2")
    a = ap.parse_args()
    out = [run(a.design, int(s)) for s in a.seeds.split(",")]
    tag = "" if a.seeds == "0,1,2" else "_seeds" + a.seeds.replace(",", "-")
    (RESULTS / f"learned_m5_{a.design}{tag}.json").write_text(json.dumps(out, indent=1))
    m = lambda k, t: np.mean([r[k][t] for r in out])
    print(a.design)
    for k in ("softmax", "BASE", "M5"):
        print(f"  {k:<8}" + "  ".join(f"{t:>4}:{m(k, t):.3f}±{np.std([r[k][t] for r in out]):.3f}"
                                     for t in ("-40", "0", "27", "55", "85")))
    gap = {t: m("BASE", "27") - m("BASE", t) for t in ("-40", "85")}
    rec = {t: (m("M5", t) - m("BASE", t)) / gap[t] for t in gap}
    harm = all(m("M5", t) >= m("BASE", t) for t in gap)
    print(f"  M5 vs BASE: gap rec -40 {rec['-40']:.1%}  85 {rec['85']:.1%} -> "
          f"{'PASS' if min(rec.values()) >= .5 else 'FAIL'} | 27C cost {100 * (m('BASE', '27') - m('M5', '27')):+.1f} pts"
          f" | no-harm {'yes' if harm else 'NO'}")
