"""Step 6: identify 200 virtual chips from their transmitted I/Q bursts.

Train at one temperature, test at every temperature. Optional ablation keeps
chip-to-chip mismatch in only some blocks (others idealized per temperature).

usage: python train.py <exp_name> [--only dac,lo,pa] [--snr 20] [--train-t 27]
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from txmodel import dataset, idealize, load_params

RESULTS = Path(__file__).resolve().parents[1] / "results"
BLOCKS = ["dac", "lo", "pa"]


class ResBlock(nn.Module):
    def __init__(self, i, o, s):
        super().__init__()
        self.c1 = nn.Conv1d(i, o, 7, s, 3, bias=False)
        self.b1 = nn.BatchNorm1d(o)
        self.c2 = nn.Conv1d(o, o, 7, 1, 3, bias=False)
        self.b2 = nn.BatchNorm1d(o)
        self.sc = nn.Sequential() if (i == o and s == 1) else nn.Sequential(
            nn.Conv1d(i, o, 1, s, bias=False), nn.BatchNorm1d(o))

    def forward(self, x):
        y = torch.relu(self.b1(self.c1(x)))
        return torch.relu(self.b2(self.c2(y)) + self.sc(x))


class ResNet1D(nn.Module):
    """Stronger baseline: 8 residual blocks (~0.7M parameters at ch=32)."""
    def __init__(self, n_cls, ch=32):
        super().__init__()
        self.stem = nn.Sequential(nn.Conv1d(2, ch, 7, 1, 3, bias=False), nn.BatchNorm1d(ch), nn.ReLU())
        cfg = [(ch, ch, 1), (ch, ch, 1), (ch, 2 * ch, 2), (2 * ch, 2 * ch, 1),
               (2 * ch, 2 * ch, 2), (2 * ch, 2 * ch, 1), (2 * ch, 4 * ch, 2), (4 * ch, 4 * ch, 1)]
        self.blocks = nn.Sequential(*[ResBlock(*c) for c in cfg])
        self.head = nn.Sequential(nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Linear(4 * ch, n_cls))

    def forward(self, x):
        return self.head(self.blocks(self.stem(x)))


class Net(nn.Module):
    def __init__(self, n_cls, ch=64):
        super().__init__()
        def blk(i, o, k, s):
            return nn.Sequential(nn.Conv1d(i, o, k, s, k // 2), nn.BatchNorm1d(o), nn.ReLU())
        self.f = nn.Sequential(blk(2, ch, 9, 1), blk(ch, ch, 9, 2), blk(ch, ch, 7, 2),
                               blk(ch, 2 * ch, 7, 2), blk(2 * ch, 2 * ch, 5, 2),
                               nn.AdaptiveAvgPool1d(1), nn.Flatten())
        self.head = nn.Linear(2 * ch, n_cls)

    def forward(self, x):
        return self.head(self.f(x))


def evaluate(model, X, y, dev, bs=256):
    model.eval()
    correct = 0
    with torch.no_grad():
        for i in range(0, len(X), bs):
            xb = torch.from_numpy(X[i:i + bs]).to(dev)
            correct += (model(xb).argmax(1).cpu().numpy() == y[i:i + bs]).sum()
    return correct / len(X)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--only", default="dac,lo,pa")
    ap.add_argument("--snr", type=float, default=20)
    ap.add_argument("--train-t", default="27", help="comma list of training temperatures")
    ap.add_argument("--arch", default="cnn", choices=["cnn", "resnet"])
    ap.add_argument("--n-train", type=int, default=40)
    ap.add_argument("--n-test", type=int, default=10)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    torch.manual_seed(a.seed)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    keep = a.only.split(",")
    p = idealize(load_params(), [b for b in BLOCKS if b not in keep])
    temps = list(p.temps)
    ti_train = [temps.index(float(t)) for t in a.train_t.split(",")]
    n_cls = p.dac_units.shape[1]

    t0 = time.time()
    # training bursts split evenly across the training temperatures
    n_per = max(1, a.n_train // len(ti_train))
    parts = [dataset(p, ti, np.random.default_rng(1000 + a.seed + 7 * ti), a.snr, n_per) for ti in ti_train]
    Xtr, ytr = np.concatenate([q[0] for q in parts]), np.concatenate([q[1] for q in parts])
    Xva, yva = dataset(p, ti_train[0], np.random.default_rng(2000 + a.seed), a.snr, a.n_test)
    tests = {t: dataset(p, i, np.random.default_rng(3000 + a.seed + i), a.snr, a.n_test)
             for i, t in enumerate(temps)}
    print(f"data {time.time() - t0:.0f}s  train {Xtr.shape}  dev {dev}", flush=True)

    model = (ResNet1D if a.arch == "resnet" else Net)(n_cls).to(dev)
    print("params:", sum(q.numel() for q in model.parameters()), flush=True)
    opt = torch.optim.AdamW(model.parameters(), 2e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 3e-3, total_steps=a.epochs * (len(Xtr) // 128 + 1))
    lossf = nn.CrossEntropyLoss()
    Xt, yt = torch.from_numpy(Xtr), torch.from_numpy(ytr)
    for ep in range(a.epochs):
        model.train()
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), 128):
            idx = perm[i:i + 128]
            xb, yb = Xt[idx].to(dev), yt[idx].to(dev)
            opt.zero_grad()
            lossf(model(xb), yb).backward()
            opt.step()
            sched.step()
        if ep % 5 == 4 or ep == a.epochs - 1:
            print(f"ep {ep + 1}  val@{temps[ti_train[0]]:g}C {evaluate(model, Xva, yva, dev):.3f}", flush=True)

    acc = {f"{t:g}": float(evaluate(model, *tests[t], dev)) for t in temps}
    print("test acc by temperature:", acc)
    RESULTS.mkdir(exist_ok=True)
    out = dict(vars(a), val=float(evaluate(model, Xva, yva, dev)), test=acc,
               n_classes=n_cls, chance=1 / n_cls)
    (RESULTS / f"{a.name}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
