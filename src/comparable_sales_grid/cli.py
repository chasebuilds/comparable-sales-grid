"""Command line: generate data, run one subject, benchmark, export demo data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from . import DISCLAIMER
from .bench import run_benchmark, to_markdown
from .grid import MarketModel, Method, appraise_subject, build_market_model
from .market import ATTRS, VALUATION_DATE, generate_market
from .outputs import render_html, write_workbook

REQUIRED_SALES = ("sale_id", "sale_date", "neighborhood", "x_km", "y_km", "sale_price", *ATTRS)


def load_sales(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_SALES if c not in df.columns]
    if missing:
        raise SystemExit(f"sales file missing columns: {', '.join(missing)}")
    return df


def demo_payload(mm: MarketModel, subjects: pd.DataFrame) -> dict[str, Any]:
    items = []
    for _, s in subjects.iterrows():
        r = appraise_subject(mm, s)
        d = r.to_dict()
        d.pop("candidates")
        d["true_value"] = float(s["true_value"])
        items.append(d)
    return {
        "disclaimer": DISCLAIMER,
        "valuation_date": mm.valuation_date,
        "method": mm.rates.method,
        "evidence": mm.rates.evidence_rows(),
        "area_effect": mm.model.area_effect,
        "r2": mm.model.r2,
        "n_sales": mm.model.n,
        "subjects": items,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="csg", description=DISCLAIMER)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="write synthetic sales.csv and subjects.csv")
    g.add_argument("--out", type=Path, default=Path("data"))
    g.add_argument("--sales", type=int, default=3000)
    g.add_argument("--subjects", type=int, default=200)
    g.add_argument("--seed", type=int, default=20261122)

    r = sub.add_parser("run", help="grid for one subject: workbook plus printable HTML")
    r.add_argument("--sales", type=Path, required=True)
    r.add_argument("--subjects", type=Path, required=True)
    r.add_argument("--subject-id", required=True)
    r.add_argument("--valuation-date", default=VALUATION_DATE)
    r.add_argument("--method", choices=("regression", "paired", "blend"), default="regression")
    r.add_argument("--out", type=Path, default=Path("out"))

    b = sub.add_parser("benchmark", help="error vs known truth for every subject")
    b.add_argument("--sales", type=Path, required=True)
    b.add_argument("--subjects", type=Path, required=True)
    b.add_argument("--valuation-date", default=VALUATION_DATE)
    b.add_argument("--out", type=Path, default=Path("benchmark"))

    d = sub.add_parser("demo-data", help="export grid results for the static web demo")
    d.add_argument("--sales", type=Path, required=True)
    d.add_argument("--subjects", type=Path, required=True)
    d.add_argument("--valuation-date", default=VALUATION_DATE)
    d.add_argument("--out", type=Path, default=Path("web/data.json"))

    a = p.parse_args(argv)
    if a.cmd == "generate":
        m = generate_market(a.sales, a.subjects, a.seed)
        a.out.mkdir(parents=True, exist_ok=True)
        m.sales.to_csv(a.out / "sales.csv", index=False)
        m.subjects.to_csv(a.out / "subjects.csv", index=False)
        print(f"wrote {len(m.sales)} sales and {len(m.subjects)} subjects to {a.out}")
        return 0

    sales = load_sales(a.sales)
    subjects = pd.read_csv(a.subjects)
    if a.cmd == "run":
        method: Method = a.method
        mm = build_market_model(sales, a.valuation_date, method)
        hit = subjects[subjects["subject_id"] == a.subject_id]
        if hit.empty:
            raise SystemExit(f"subject {a.subject_id} not found")
        res = appraise_subject(mm, hit.iloc[0])
        a.out.mkdir(parents=True, exist_ok=True)
        write_workbook(res, mm, a.out / f"{a.subject_id}.xlsx")
        (a.out / f"{a.subject_id}.html").write_text(render_html(res, mm), encoding="utf-8")
        print(
            f"indicated value {res.indicated_value:,.0f}; range {res.range_low:,.0f} to {res.range_high:,.0f}"
        )
        print(f"wrote {a.out / (a.subject_id + '.xlsx')} and .html")
        return 0
    if a.cmd == "benchmark":
        bench = run_benchmark(sales, subjects, a.valuation_date)
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / "results.json").write_text(json.dumps(bench, indent=2), encoding="utf-8")
        md = to_markdown(bench)
        (a.out / "BENCHMARK.md").write_text(md, encoding="utf-8")
        print(md)
        return 0
    mm = build_market_model(sales, a.valuation_date, "regression")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(
        json.dumps(demo_payload(mm, subjects), separators=(",", ":")), encoding="utf-8"
    )
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
