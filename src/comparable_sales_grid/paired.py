"""Paired-sales extraction: find sale pairs that differ mainly in one feature.

Prices are first moved to one date with the monthly index. A pair must sit in the same area
and match on every other feature within a tolerance. The rate for the feature is the pooled
least-squares slope of the log price gap on the feature gap (through the origin).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .market import ATTRS
from .model import HedonicModel, months_since_base, transform

# Tolerance on the gap for features held equal, and the gap window for the feature under test.
HOLD_TOL = {
    "gla": 0.06,  # gap in ln(gla)
    "beds": 0.0,
    "baths": 0.0,
    "age": 6.0,
    "lot": 0.15,  # gap in ln(lot)
    "condition": 0.0,
    "quality": 0.0,
}
TEST_WINDOW = {
    "gla": (0.12, 0.50),
    "beds": (1.0, 1.0),
    "baths": (0.5, 1.0),
    "age": (15.0, 80.0),
    "lot": (0.30, 1.20),
    "condition": (1.0, 1.0),
    "quality": (1.0, 1.0),
}
MIN_PAIRS = 10


@dataclass(frozen=True)
class PairedRate:
    attr: str
    rate: float | None
    n_pairs: int


def paired_rates(sales: pd.DataFrame, model: HedonicModel) -> dict[str, PairedRate]:
    months = months_since_base(sales["sale_date"])
    log_idx = np.array([model.log_index(int(m)) for m in months])
    lnp = np.log(sales["sale_price"].to_numpy(dtype=float)) - log_idx
    feats = {
        a: np.asarray(transform(a, sales[a].to_numpy(dtype=float)), dtype=float) for a in ATTRS
    }
    areas = sales["neighborhood"].to_numpy()
    num = dict.fromkeys(ATTRS, 0.0)
    den = dict.fromkeys(ATTRS, 0.0)
    count = dict.fromkeys(ATTRS, 0)
    for area in np.unique(areas):
        idx = np.flatnonzero(areas == area)
        gaps = {a: np.abs(feats[a][idx][:, None] - feats[a][idx][None, :]) for a in ATTRS}
        signed = {a: feats[a][idx][None, :] - feats[a][idx][:, None] for a in ATTRS}
        dlnp = lnp[idx][None, :] - lnp[idx][:, None]
        upper = np.triu(np.ones_like(dlnp, dtype=bool), k=1)
        for test in ATTRS:
            ok = upper.copy()
            for other in ATTRS:
                if other != test:
                    ok &= gaps[other] <= HOLD_TOL[other] + 1e-9
            lo, hi = TEST_WINDOW[test]
            ok &= (gaps[test] >= lo - 1e-9) & (gaps[test] <= hi + 1e-9)
            if not ok.any():
                continue
            dx = signed[test][ok]
            dy = dlnp[ok]
            num[test] += float(dx @ dy)
            den[test] += float(dx @ dx)
            count[test] += int(ok.sum())
    out: dict[str, PairedRate] = {}
    for a in ATTRS:
        rate = num[a] / den[a] if count[a] >= MIN_PAIRS and den[a] > 0 else None
        out[a] = PairedRate(attr=a, rate=rate, n_pairs=count[a])
    return out
