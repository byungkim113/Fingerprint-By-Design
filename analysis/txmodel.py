"""Baseband-equivalent transmitter built from per-chip SPICE extractions.

Chain: QPSK symbols -> RRC pulse shaping -> 5-bit unary I/Q DACs (per-chip unit
currents) -> RC-CR quadrature LO (per-chip I/Q gain and phase) -> PA (per-chip
AM/AM, AM/PM) -> AWGN + random carrier phase -> receiver: least-squares complex
gain from a known preamble, derotate/normalize.

Ablation: any block can be made "ideal" for fingerprinting by replacing each
chip's parameters with the population mean at the same temperature, which
removes chip-to-chip differences but keeps the common temperature drift.
"""
from dataclasses import dataclass

import numpy as np

from features import load

SPS = 8
N_PRE, N_DATA = 32, 256
ROLLOFF = 0.35
N_BITS_UNITS = 31
UNIT_NOM = 10e-6
PA_VMAX = 0.4             # peak baseband amplitude maps to max measured drive


def rrc(beta=ROLLOFF, sps=SPS, span=8):
    t = np.arange(-span * sps // 2, span * sps // 2 + 1) / sps
    h = np.zeros_like(t)
    for i, ti in enumerate(t):
        if ti == 0:
            h[i] = 1 - beta + 4 * beta / np.pi
        elif abs(abs(4 * beta * ti) - 1) < 1e-9:
            h[i] = beta / np.sqrt(2) * ((1 + 2 / np.pi) * np.sin(np.pi / (4 * beta))
                                        + (1 - 2 / np.pi) * np.cos(np.pi / (4 * beta)))
        else:
            h[i] = (np.sin(np.pi * ti * (1 - beta)) + 4 * beta * ti * np.cos(np.pi * ti * (1 + beta))) \
                / (np.pi * ti * (1 - (4 * beta * ti) ** 2))
    return h / np.sqrt((h ** 2).sum())


H_RRC = rrc()


@dataclass
class ChipParams:
    """Per (temperature, chip) transmitter parameters."""
    dac_units: np.ndarray     # (T, chip, 2, 31) amps, Vo=0.9
    lo: np.ndarray            # (T, chip, 4) |vi|, ang vi, |vq|, ang vq
    pa: np.ndarray            # (T, chip, amp, 2) output mag, phase deg
    pa_amps: np.ndarray
    temps: np.ndarray
    unit_nom: float = UNIT_NOM   # design's nominal unit current (A)
    differential: bool = False   # False: offset referenced to a fixed nominal
                                 # full scale; True: differential DAC, offset
                                 # referenced to the chip's own total current


def params_from(dac, pa, lo, vdd=1.8, unit_nom=UNIT_NOM, differential=False):
    """Build ChipParams from the three SPICE result archives."""
    assert (dac["temps"] == pa["temps"]).all() and (dac["temps"] == lo["temps"]).all()
    assert (dac["chips"] == pa["chips"]).all() and (dac["chips"] == lo["chips"]).all()
    vi = int(np.argmin(np.abs(pa["vdds"] - vdd)))
    return ChipParams(dac_units=dac["data"][:, :, :, 1, :], lo=lo["data"],
                      pa=pa["data"][:, vi], pa_amps=pa["amps"], temps=dac["temps"],
                      unit_nom=unit_nom, differential=differential)


def load_params(vdd=1.8, differential=False):
    return params_from(*load(), vdd=vdd, differential=differential)


def idealize(p: ChipParams, blocks):
    """Replace listed blocks' per-chip params with the per-temperature mean."""
    d = dict(dac_units=p.dac_units, lo=p.lo, pa=p.pa)
    key = {"dac": "dac_units", "lo": "lo", "pa": "pa"}
    for b in blocks:
        a = d[key[b]]
        d[key[b]] = np.broadcast_to(a.mean(1, keepdims=True), a.shape).copy()
    return ChipParams(**d, pa_amps=p.pa_amps, temps=p.temps, unit_nom=p.unit_nom,
                      differential=p.differential)


def _dac(x, units, unit_nom=UNIT_NOM, differential=False):
    """x in [-1, 1] -> unary code 0..31 -> output normalized to nominal FS."""
    code = np.clip(np.round((x + 1) / 2 * N_BITS_UNITS), 0, N_BITS_UNITS).astype(int)
    cum = np.concatenate([[0.0], np.cumsum(units)])
    ref = cum[-1] if differential else N_BITS_UNITS * unit_nom
    return (2 * cum[code] - ref) / (N_BITS_UNITS * unit_nom)


def transmit(p: ChipParams, ti, chip, rng, snr_db, n_bursts):
    """-> complex array (n_bursts, (N_PRE + N_DATA) * SPS) after receiver
    preamble normalization; also returns the known preamble symbols."""
    units = p.dac_units[ti, chip]
    vi_m, vi_p, vq_m, vq_p = p.lo[ti, chip]
    # nominal RC-CR phases are -45/+45 deg; keep deviations and relative gains
    gi = vi_m * np.exp(1j * (vi_p + np.pi / 4))
    gq = vq_m * np.exp(1j * (vq_p - np.pi / 4))
    lo_scale = (abs(gi) + abs(gq)) / 2
    gi, gq = gi / lo_scale, gq / lo_scale      # absolute LO loss is not observable
    pa_in = p.pa_amps
    pa_mag = p.pa[ti, chip, :, 0]
    pa_ph = np.radians(p.pa[ti, chip, :, 1] - p.pa[ti, chip, 0, 1])
    pa_gain0 = pa_mag[0] / pa_in[0]

    pre = np.exp(1j * np.pi / 4 * (2 * np.random.default_rng(12345).integers(0, 4, N_PRE) + 1))
    out = np.empty((n_bursts, (N_PRE + N_DATA) * SPS), complex)
    for b in range(n_bursts):
        data = np.exp(1j * np.pi / 4 * (2 * rng.integers(0, 4, N_DATA) + 1))
        sym = np.concatenate([pre, data])
        up = np.zeros(len(sym) * SPS, complex)
        up[::SPS] = sym
        x = np.convolve(up, H_RRC, mode="same")
        x = x / np.abs(x).max()
        bi = _dac(x.real, units[0], p.unit_nom, p.differential)
        bq = _dac(x.imag, units[1], p.unit_nom, p.differential)
        s = gi * bi + 1j * gq * bq
        # interpolate gain (not output magnitude) so drive below the first
        # measured amplitude sees the small-signal gain, i.e. stays linear
        a = np.abs(s) / np.abs(s).max() * PA_VMAX
        y = s * np.interp(a, pa_in, pa_mag / pa_in) / pa_gain0 \
            * np.exp(1j * np.interp(a, pa_in, pa_ph))
        y *= np.exp(1j * rng.uniform(0, 2 * np.pi))
        sig_pow = np.mean(np.abs(y) ** 2)
        n = np.sqrt(sig_pow / 10 ** (snr_db / 10) / 2) * (rng.standard_normal(len(y))
                                                         + 1j * rng.standard_normal(len(y)))
        out[b] = y + n
    # receiver: LS complex gain on the preamble segment against the ideal shaped preamble
    up = np.zeros(len(pre) * SPS, complex)
    up[::SPS] = pre
    ref = np.convolve(up, H_RRC, mode="same")
    seg = out[:, :len(ref)]
    h = (seg @ ref.conj()) / (ref @ ref.conj())
    return out / h[:, None]


def dataset(p, ti, rng, snr_db, n_bursts, chips=None):
    """-> X float32 (N, 2, L), y int (N,)"""
    chips = range(p.dac_units.shape[1]) if chips is None else chips
    xs, ys = [], []
    for c in chips:
        z = transmit(p, ti, c, rng, snr_db, n_bursts)
        xs.append(np.stack([z.real, z.imag], 1).astype(np.float32))
        ys.append(np.full(n_bursts, c))
    return np.concatenate(xs), np.concatenate(ys)
