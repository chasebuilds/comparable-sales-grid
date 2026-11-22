"""Benchmark: reconciled value vs the known synthetic truth for many subjects."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .grid import Method, appraise_subject, build_market_model
from .model import months_since_base

METHODS: tuple[Method, ...] = ("regression", "paired", "blend")


def _summary(est: np.ndarray, truth: np.ndarray) -> dict[str, float]:
    err = np.abs(est / truth - 1)
    signed = est / truth - 1
    return {
        "median_abs_pct_error": float(np.median(err) * 100),
        "mean_abs_pct_error": float(err.mean() * 100),
        "share_within_5pct": float((err <= 0.05).mean() * 100),
        "share_within_10pct": float((err <= 0.10).mean() * 100),
        "bias_pct": float(signed.mean() * 100),
    }


def run_benchmark(
    sales: pd.DataFrame, subjects: pd.DataFrame, valuation_date: str
) -> dict[str, Any]:
    truth = subjects["true_value"].to_numpy(dtype=float)
    out: dict[str, Any] = {"n_subjects": len(subjects), "n_sales": len(sales), "methods": {}}
    for method in METHODS:
        mm = build_market_model(sales, valuation_date, method)
        reconciled, unadjusted, in_range, n_comps, flagged = [], [], [], [], []
        for _, s in subjects.iterrows():
            r = appraise_subject(mm, s)
            reconciled.append(r.indicated_value)
            unadjusted.append(float(np.median([c.time_adjusted_price for c in r.comps])))
            tv = float(s["true_value"])
            in_range.append(r.range_low <= tv <= r.range_high)
            n_comps.append(len(r.comps))
            flagged.append(any(c.flags for c in r.comps))
        res: dict[str, Any] = dict(_summary(np.array(reconciled), truth))
        res["truth_inside_range_pct"] = float(np.mean(in_range) * 100)
        res["mean_comps_used"] = float(np.mean(n_comps))
        res["subjects_with_flagged_comp_pct"] = float(np.mean(flagged) * 100)
        res["baseline_time_adjusted_median_only"] = _summary(np.array(unadjusted), truth)
        if method == "regression":
            vm = mm.valuation_month
            direct = np.array([np.exp(mm.model.predict_ln(s, vm)) for _, s in subjects.iterrows()])
            res["reference_direct_regression_prediction"] = _summary(direct, truth)
        out["methods"][method] = res
    out["valuation_month_index"] = int(months_since_base(pd.Series([valuation_date]))[0])
    return out


def to_markdown(b: dict[str, Any]) -> str:
    lines = [
        "# Benchmark",
        "",
        f"{b['n_subjects']} synthetic subjects scored against the known true value, "
        f"market of {b['n_sales']} synthetic sales. Subjects are not in the sales file.",
        "",
        "| Method | Median abs % error | Mean abs % error | Within 5% | Within 10% | Bias | Truth inside range |",
        "|---|---|---|---|---|---|---|",
    ]
    for m, r in b["methods"].items():
        lines.append(
            f"| {m} | {r['median_abs_pct_error']:.2f}% | {r['mean_abs_pct_error']:.2f}% | "
            f"{r['share_within_5pct']:.1f}% | {r['share_within_10pct']:.1f}% | "
            f"{r['bias_pct']:+.2f}% | {r['truth_inside_range_pct']:.1f}% |"
        )
    base = next(iter(b["methods"].values()))["baseline_time_adjusted_median_only"]
    ref = b["methods"]["regression"]["reference_direct_regression_prediction"]
    lines += [
        "",
        "Context rows (same subjects):",
        "",
        "| Estimate | Median abs % error | Within 5% | Within 10% |",
        "|---|---|---|---|",
        f"| Median of chosen comps, time-adjusted only (no line adjustments) | "
        f"{base['median_abs_pct_error']:.2f}% | {base['share_within_5pct']:.1f}% | {base['share_within_10pct']:.1f}% |",
        f"| Direct regression prediction (no comps) | {ref['median_abs_pct_error']:.2f}% | "
        f"{ref['share_within_5pct']:.1f}% | {ref['share_within_10pct']:.1f}% |",
        "",
        "Truth is the noise-free synthetic value at the valuation date. Real sales carry noise and "
        "unobserved features the generator does not have, so real-world errors will be larger.",
        "",
    ]
    return "\n".join(lines)
