"""Hedonic regression on the sales file: feature rates, area effects and a monthly index."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .market import ATTRS, BASE_MONTH, BASE_YEAR

LOG_ATTRS = ("gla", "lot")


def transform(attr: str, value: float | np.ndarray) -> float | np.ndarray:
    """Attributes enter the model as ln(x) for size-like items and as x otherwise."""
    if attr in LOG_ATTRS:
        return np.log(value)
    return value


def months_since_base(
    dates: pd.Series, base: tuple[int, int] = (BASE_YEAR, BASE_MONTH)
) -> np.ndarray:
    d = pd.to_datetime(dates)
    year = d.dt.year.to_numpy(dtype=int)
    month = d.dt.month.to_numpy(dtype=int)
    return (year - base[0]) * 12 + (month - base[1])


@dataclass(frozen=True)
class HedonicModel:
    beta: dict[str, float]
    se: dict[str, float]
    area_effect: dict[str, float]
    month_effect: dict[int, float]
    resid_sd: float
    r2: float
    n: int
    base: tuple[int, int]
    intercept: float = 0.0

    def log_index(self, month: int) -> float:
        """ln index for a month. Months past the last sale extrapolate the last 6-month trend."""
        known = sorted(self.month_effect)
        if month in self.month_effect:
            return self.month_effect[month]
        if month < known[0]:
            return self.month_effect[known[0]]
        if month < known[-1]:
            return float(np.interp(month, known, [self.month_effect[k] for k in known]))
        tail = known[-6:]
        slope, intercept = np.polyfit(tail, [self.month_effect[k] for k in tail], 1)
        return float(slope * month + intercept)

    def predict_ln(self, row: pd.Series, month: int) -> float:
        total = (
            self.intercept
            + self.area_effect.get(str(row["neighborhood"]), 0.0)
            + self.log_index(month)
        )
        for a in ATTRS:
            total += self.beta[a] * float(transform(a, float(row[a])))
        return total


def fit_hedonic(sales: pd.DataFrame) -> HedonicModel:
    """OLS of ln(price) on attributes, area fixed effects and month fixed effects."""
    months = months_since_base(sales["sale_date"])
    areas = sorted(sales["neighborhood"].unique())
    obs_months = sorted({int(m) for m in months})
    ref_month = obs_months[0]
    cols: list[np.ndarray] = [np.ones(len(sales))]
    names: list[str] = ["const"]
    for a in ATTRS:
        cols.append(np.asarray(transform(a, sales[a].to_numpy(dtype=float)), dtype=float))
        names.append(a)
    for area in areas[1:]:
        cols.append((sales["neighborhood"] == area).to_numpy(dtype=float))
        names.append(f"area:{area}")
    for m in obs_months:
        if m == ref_month:
            continue
        cols.append((months == m).astype(float))
        names.append(f"month:{m}")
    x = np.column_stack(cols)
    y = np.log(sales["sale_price"].to_numpy(dtype=float))
    xtx_inv = np.linalg.pinv(x.T @ x)
    coef = xtx_inv @ x.T @ y
    resid = y - x @ coef
    dof = max(len(y) - x.shape[1], 1)
    s2 = float(resid @ resid) / dof
    se_all = np.sqrt(np.diag(xtx_inv) * s2)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    pos = {n: i for i, n in enumerate(names)}
    month_effect = {ref_month: 0.0}
    for m in obs_months[1:]:
        month_effect[m] = float(coef[pos[f"month:{m}"]])
    area_effect = {areas[0]: 0.0}
    for area in areas[1:]:
        area_effect[area] = float(coef[pos[f"area:{area}"]])
    return HedonicModel(
        beta={a: float(coef[pos[a]]) for a in ATTRS},
        se={a: float(se_all[pos[a]]) for a in ATTRS},
        area_effect=area_effect,
        month_effect=month_effect,
        resid_sd=float(np.sqrt(s2)),
        r2=1 - float(resid @ resid) / ss_tot,
        n=len(y),
        base=(BASE_YEAR, BASE_MONTH),
        intercept=float(coef[0]),
    )
