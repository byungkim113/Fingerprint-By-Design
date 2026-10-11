import sys; sys.path.insert(0, '.')
import numpy as np, tx_modelrx as m, tx_round3 as r3, tx_full as tx, tx_ident as ti
d = lambda tag, v, c, T: tx.WORK / f"ident_{tag}vdd{v}_{c}_T{T}"
P = {f: m.phi(*m.codes(f)) for f in ("4", "5", "cov")}
conds = [("180", 27)] + m.COND3
pred = {}
for k in conds:
    Y = {f: r3._frames(tx, ti, d(f"frame{f}_", k[0], "tt_mm", k[1]), range(1, 17), *m.codes(f)) for f in ("4", "5")}
    th = [m.fit([P["4"], P["5"]], [Y["4"][c], Y["5"][c]]) for c in range(16)]
    pr = np.array([P["cov"] @ t for t in th])
    pred[k] = np.concatenate([pr.real, pr.imag], 1)                       # chip x 256
F = pred[conds[0]] - pred[conds[0]].mean(0)
lams = 10.0 ** np.arange(-6, 3)
def ridge(X, Y, lam):
    return np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ Y) if X.shape[0] > X.shape[1] else \
        X.T @ np.linalg.solve(X @ X.T + lam * np.eye(X.shape[0]), Y)
def loo_pred(X, Y, lam):
    out = np.zeros_like(Y)
    for i in range(len(X)):
        tr = np.arange(len(X)) != i
        W = ridge(X[tr], Y[tr], lam); out[i] = X[i] @ W
    return out
res = {}
for k in conds[1:]:
    D = pred[k] - pred[conds[0]]; D = D - D.mean(0)
    preds = np.zeros_like(D)
    for i in range(16):
        tr = np.arange(16) != i
        Xt, Yt = F[tr] - F[tr].mean(0), D[tr] - D[tr].mean(0)
        best = min(lams, key=lambda l: np.sum((loo_pred(Xt, Yt, l) - Yt) ** 2))
        W = ridge(Xt, Yt, best)
        preds[i] = (F[i] - F[tr].mean(0)) @ W + D[tr].mean(0)
    r2 = 1 - np.sum((D - preds) ** 2) / np.sum(D ** 2)
    ratio = np.linalg.norm(D) / np.linalg.norm(F)
    res[k] = r2
    print(f"{k[1]:>4}C {float(k[0][0]+'.'+k[0][1:]):.2f} V: chip-specific drift / fingerprint size {ratio:.2f} | held-out R^2 {r2:+.3f}")
mean = np.mean(list(res.values()))
print(f"mean held-out R^2 {mean:+.3f} -> {'ALIVE' if mean >= 0.3 else 'DEAD'}")
