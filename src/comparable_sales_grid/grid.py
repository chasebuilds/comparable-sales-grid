"""Comp search, selection, adjustment grid and reconciliation for one subject."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from .market import ATTRS
from .model import HedonicModel, fit_hedonic, months_since_base, transform
from .paired import PairedRate, paired_rates

Method = Literal["regression", "paired", "blend"]

NET_FLAG = 0.15
GROSS_FLAG = 0.25
MIN_COMPS, MAX_COMPS = 3, 6
POOL = 20  # most similar candidates that get a full grid before selection

# Similarity: weighted gaps, each scaled so that "one unit" is a noticeable difference.
SIM_SCALE = {
    "distance": 3.0,  # km
    "recency": 12.0,  # months
    "gla": 0.20,  # gap in ln(gla)
    "beds": 2.0,
    "baths": 1.5,
    "age": 30.0,
    "lot": 0.60,  # gap in ln(lot)
    "condition": 2.0,
    "quality": 2.0,
}
SIM_WEIGHT = {
    "distance": 1.0,
    "recency": 0.8,
    "gla": 1.5,
    "beds": 0.4,
    "baths": 0.4,
    "age": 0.7,
    "lot": 0.5,
    "condition": 0.9,
    "quality": 0.9,
}
LINE_LABELS = {
    "location": "Location (area)",
    "gla": "Living area (GLA)",
    "beds": "Bedrooms",
    "baths": "Bathrooms",
    "age": "Age",
    "lot": "Lot size",
    "condition": "Condition",
    "quality": "Quality",
}
LINES = ("location", *ATTRS)


@dataclass(frozen=True)
class Rates:
    """Per-feature log-price rate: regression, paired-sales, and the one used."""

    regression: dict[str, float]
    se: dict[str, float]
    paired: dict[str, PairedRate]
    used: dict[str, float]
    method: Method

    def evidence_rows(self) -> list[dict[str, Any]]:
        rows = []
        for a in ATTRS:
            p = self.paired[a]
            rows.append(
                {
                    "feature": a,
                    "regression_rate": self.regression[a],
                    "regression_se": self.se[a],
                    "paired_rate": p.rate,
                    "paired_pairs": p.n_pairs,
                    "used_rate": self.used[a],
                }
            )
        return rows


@dataclass(frozen=True)
class MarketModel:
    model: HedonicModel
    rates: Rates
    sales: pd.DataFrame
    valuation_month: int
    valuation_date: str = ""


def build_market_model(
    sales: pd.DataFrame, valuation_date: str, method: Method = "regression"
) -> MarketModel:
    model = fit_hedonic(sales)
    paired = paired_rates(sales, model)
    used: dict[str, float] = {}
    for a in ATTRS:
        reg = model.beta[a]
        p = paired[a].rate
        if method == "regression" or p is None:
            used[a] = reg
        elif method == "paired":
            used[a] = p
        else:
            used[a] = (reg + p) / 2
    rates = Rates(
        regression=dict(model.beta), se=dict(model.se), paired=paired, used=used, method=method
    )
    vmonth = int(months_since_base(pd.Series([valuation_date]))[0])
    return MarketModel(
        model=model, rates=rates, sales=sales, valuation_month=vmonth, valuation_date=valuation_date
    )


@dataclass
class CompRow:
    sale_id: str
    sale_date: str
    neighborhood: str
    attrs: dict[str, float]
    sale_price: float
    distance_km: float
    months_ago: int
    similarity: float
    time_adjustment: float
    time_adjusted_price: float
    adjustments: dict[str, float]
    net_adjustment: float
    gross_adjustment: float
    net_pct: float
    gross_pct: float
    flags: list[str]
    adjusted_price: float
    weight: float = 0.0
    reason: str = ""


@dataclass
class GridResult:
    subject: dict[str, Any]
    valuation_date: str
    comps: list[CompRow]
    candidates: list[CompRow] = field(default_factory=list)
    indicated_value: float = 0.0
    range_low: float = 0.0
    range_high: float = 0.0
    n_candidates: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _similarity(
    subject: pd.Series, cand: pd.DataFrame, dist: np.ndarray, months_ago: np.ndarray
) -> np.ndarray:
    gaps: dict[str, np.ndarray] = {
        "distance": dist,
        "recency": months_ago.astype(float),
    }
    for a in ATTRS:
        gap = np.asarray(transform(a, cand[a].to_numpy(dtype=float)), dtype=float) - float(
            transform(a, float(subject[a]))
        )
        gaps[a] = np.abs(gap)
    d = sum(SIM_WEIGHT[k] * gaps[k] / SIM_SCALE[k] for k in SIM_SCALE)
    total_w = sum(SIM_WEIGHT.values())
    return np.asarray(100 * np.exp(-d / total_w * 1.5), dtype=float)


def _reason(subj: pd.Series, row: CompRow) -> str:
    bits = [f"{row.distance_km:.1f} km away", f"sold {row.months_ago} mo before valuation"]
    d_gla = row.attrs["gla"] - float(subj["gla"])
    bits.append(
        f"GLA within {abs(d_gla):,.0f} sf" if abs(d_gla) <= 250 else f"GLA {d_gla:+,.0f} sf"
    )
    same = [a for a in ("beds", "baths", "condition", "quality") if row.attrs[a] == float(subj[a])]
    if same:
        bits.append("same " + ", ".join(same))
    bits.append(f"gross adj {row.gross_pct * 100:.1f}%")
    return "; ".join(bits)


def _line_adjustments(
    mm: MarketModel, subj: pd.Series, comp: pd.Series, base_price: float
) -> dict[str, float]:
    out: dict[str, float] = {}
    loc = mm.model.area_effect.get(str(subj["neighborhood"]), 0.0) - mm.model.area_effect.get(
        str(comp["neighborhood"]), 0.0
    )
    out["location"] = base_price * (np.exp(loc) - 1)
    for a in ATTRS:
        gap = float(transform(a, float(subj[a]))) - float(transform(a, float(comp[a])))
        out[a] = base_price * (np.exp(mm.rates.used[a] * gap) - 1)
    return out


def appraise_subject(
    mm: MarketModel,
    subject: pd.Series,
    *,
    radius_km: float = 6.0,
    lookback_months: int = 12,
) -> GridResult:
    """Run the full sales-comparison workflow for one subject."""
    notes: list[str] = []
    sales = mm.sales
    smonth = months_since_base(sales["sale_date"])
    ago = mm.valuation_month - smonth
    dist = np.hypot(
        sales["x_km"].to_numpy(dtype=float) - float(subject["x_km"]),
        sales["y_km"].to_numpy(dtype=float) - float(subject["y_km"]),
    )
    window = lookback_months
    keep = (ago >= 0) & (ago <= window) & (dist <= radius_km)
    while keep.sum() < 8 and window < 36:
        window += 6
        keep = (ago >= 0) & (ago <= window) & (dist <= radius_km)
        notes.append(f"Widened sale window to {window} months (fewer than 8 candidates).")
    if keep.sum() < MIN_COMPS:
        keep = (ago >= 0) & (dist <= radius_km * 2)
        notes.append("Widened radius to double the default.")
    cand = sales[keep].reset_index(drop=True)
    c_dist, c_ago = dist[keep], ago[keep]
    sim = _similarity(subject, cand, c_dist, c_ago)
    order = np.argsort(-sim)[:POOL]

    v_idx = mm.model.log_index(mm.valuation_month)
    rows: list[CompRow] = []
    for i in order:
        comp = cand.iloc[int(i)]
        sale_price = float(comp["sale_price"])
        c_month = int(c_ago.item(int(i)))
        t_ln = v_idx - mm.model.log_index(mm.valuation_month - c_month)
        time_adj = sale_price * (float(np.exp(t_ln)) - 1)
        base = sale_price + time_adj
        adj = _line_adjustments(mm, subject, comp, base)
        net = sum(adj.values())
        gross = sum(abs(v) for v in adj.values())
        net_pct, gross_pct = net / base, gross / base
        flags = []
        if abs(net_pct) > NET_FLAG:
            flags.append(f"net adjustment over {NET_FLAG:.0%}")
        if gross_pct > GROSS_FLAG:
            flags.append(f"gross adjustment over {GROSS_FLAG:.0%}")
        rows.append(
            CompRow(
                sale_id=str(comp["sale_id"]),
                sale_date=str(comp["sale_date"]),
                neighborhood=str(comp["neighborhood"]),
                attrs={a: float(comp[a]) for a in ATTRS},
                sale_price=sale_price,
                distance_km=float(c_dist[int(i)]),
                months_ago=c_month,
                similarity=float(sim[int(i)]),
                time_adjustment=time_adj,
                time_adjusted_price=base,
                adjustments=adj,
                net_adjustment=net,
                gross_adjustment=gross,
                net_pct=net_pct,
                gross_pct=gross_pct,
                flags=flags,
                adjusted_price=base + net,
            )
        )
    passing = sorted((r for r in rows if not r.flags), key=lambda r: r.gross_pct)
    failing = sorted((r for r in rows if r.flags), key=lambda r: r.gross_pct)
    chosen = passing[:MAX_COMPS]
    if len(chosen) < MIN_COMPS:
        chosen += failing[: MIN_COMPS - len(chosen)]
        notes.append(
            "Fewer than 3 comps passed the 15% net / 25% gross guidelines; best remaining were added and flagged."
        )
    chosen.sort(key=lambda r: r.gross_pct)
    inv = np.array([1.0 / max(r.gross_pct, 0.03) for r in chosen])
    w = inv / inv.sum()
    for r, wi in zip(chosen, w, strict=True):
        r.weight = float(wi)
        r.reason = _reason(subject, r)
    adjusted = np.array([r.adjusted_price for r in chosen])
    return GridResult(
        subject={str(k): (v.item() if hasattr(v, "item") else v) for k, v in subject.items()},
        valuation_date=mm.valuation_date,
        comps=chosen,
        candidates=[r for r in rows if r not in chosen],
        indicated_value=float(adjusted @ w),
        range_low=float(adjusted.min()),
        range_high=float(adjusted.max()),
        n_candidates=int(keep.sum()),
        notes=notes,
    )


def appraise(
    sales: pd.DataFrame,
    subject: pd.Series,
    valuation_date: str,
    method: Method = "regression",
) -> tuple[GridResult, MarketModel]:
    mm = build_market_model(sales, valuation_date, method)
    return appraise_subject(mm, subject), mm
