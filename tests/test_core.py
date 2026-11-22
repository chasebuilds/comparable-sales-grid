from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from openpyxl import load_workbook

from comparable_sales_grid import cli
from comparable_sales_grid.grid import (
    GROSS_FLAG,
    NET_FLAG,
    appraise_subject,
    build_market_model,
)
from comparable_sales_grid.market import ATTRS, TRUE, VALUATION_DATE, generate_market
from comparable_sales_grid.model import fit_hedonic
from comparable_sales_grid.outputs import render_html, write_workbook
from comparable_sales_grid.paired import paired_rates


@pytest.fixture(scope="module")
def market():  # type: ignore[no-untyped-def]
    return generate_market(n_sales=1500, n_subjects=12, seed=7)


@pytest.fixture(scope="module")
def mm(market):  # type: ignore[no-untyped-def]
    return build_market_model(market.sales, market.valuation_date)


def test_market_is_seeded_and_clean():
    a = generate_market(300, 5, seed=1)
    b = generate_market(300, 5, seed=1)
    pd.testing.assert_frame_equal(a.sales, b.sales)
    assert a.sales["sale_price"].gt(0).all()
    assert not a.sales.isna().any().any()
    assert set(a.subjects["subject_id"]).isdisjoint(set(a.sales["sale_id"]))


def test_regression_recovers_true_rates(market):  # type: ignore[no-untyped-def]
    m = fit_hedonic(market.sales)
    assert m.beta["gla"] == pytest.approx(TRUE["gla"], abs=0.06)
    assert m.beta["lot"] == pytest.approx(TRUE["lot"], abs=0.03)
    assert m.beta["quality"] == pytest.approx(TRUE["quality"], abs=0.02)
    assert m.r2 > 0.9


def test_index_tracks_trend_and_extrapolates(market):  # type: ignore[no-untyped-def]
    m = fit_hedonic(market.sales)
    assert m.log_index(30) > m.log_index(2)
    assert m.log_index(36) > m.log_index(35) - 0.03


def test_paired_rates_have_counts_and_sane_signs(market):  # type: ignore[no-untyped-def]
    m = fit_hedonic(market.sales)
    p = paired_rates(market.sales, m)
    assert set(p) == set(ATTRS)
    assert any(v.n_pairs > 0 for v in p.values())
    if p["gla"].rate is not None:
        assert p["gla"].rate > 0
    if p["age"].rate is not None:
        assert p["age"].rate < 0


def test_grid_rules(market, mm):  # type: ignore[no-untyped-def]
    for _, s in market.subjects.iterrows():
        r = appraise_subject(mm, s)
        assert 3 <= len(r.comps) <= 6
        assert sum(c.weight for c in r.comps) == pytest.approx(1.0)
        assert r.range_low <= r.indicated_value <= r.range_high
        for c in r.comps:
            assert c.months_ago >= 0
            assert c.adjusted_price == pytest.approx(c.time_adjusted_price + c.net_adjustment)
            assert c.gross_adjustment >= abs(c.net_adjustment) - 1e-6
            over = abs(c.net_pct) > NET_FLAG or c.gross_pct > GROSS_FLAG
            assert bool(c.flags) == over
            assert c.reason


def test_identical_property_needs_little_adjustment(market, mm):  # type: ignore[no-untyped-def]
    comp = market.sales.iloc[-1]
    subj = comp.copy()
    subj["x_km"] += 0.01
    r = appraise_subject(mm, subj)
    best = min(r.comps, key=lambda c: c.gross_pct)
    assert best.gross_pct < 0.1


def test_reconciled_value_is_close_to_truth(market, mm):  # type: ignore[no-untyped-def]
    errs = [
        abs(appraise_subject(mm, s).indicated_value / s["true_value"] - 1)
        for _, s in market.subjects.iterrows()
    ]
    assert float(np.median(errs)) < 0.05


def test_workbook_formulas_match_values(tmp_path: Path, market, mm):  # type: ignore[no-untyped-def]
    s = market.subjects.iloc[0]
    r = appraise_subject(mm, s)
    out = tmp_path / "g.xlsx"
    write_workbook(r, mm, out)
    wb = load_workbook(out)
    assert wb.sheetnames == ["Grid", "Comps", "Adjustment evidence", "Market index", "Notes"]
    ws = wb["Grid"]
    labels = {ws.cell(row=i, column=1).value: i for i in range(1, ws.max_row + 1)}
    net_row = labels["Net adjustment"]
    pat = re.compile(r"=SUM\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)")
    for j, c in enumerate(r.comps, start=3):
        m = pat.fullmatch(str(ws.cell(row=net_row, column=j).value))
        assert m is not None
        total = sum(float(ws.cell(row=i, column=j).value) for i in range(int(m[2]), int(m[4]) + 1))
        assert total == pytest.approx(c.net_adjustment, abs=len(LINES_N) + 1)
    assert "not an appraisal" in str(ws["A2"].value).lower()


LINES_N = ATTRS + ("location",)


def test_html_has_disclaimer_and_flags(market, mm):  # type: ignore[no-untyped-def]
    r = appraise_subject(mm, market.subjects.iloc[1])
    page = render_html(r, mm)
    assert "USPAP-compliant appraisal" in page
    assert "Indicated value" in page
    assert "—" not in page


def test_cli_roundtrip(tmp_path: Path):
    assert cli.main(["generate", "--out", str(tmp_path), "--sales", "600", "--subjects", "4"]) == 0
    code = cli.main(
        [
            "run",
            "--sales", str(tmp_path / "sales.csv"),
            "--subjects", str(tmp_path / "subjects.csv"),
            "--subject-id", "P0001",
            "--valuation-date", VALUATION_DATE,
            "--out", str(tmp_path / "out"),
        ]
    )  # fmt: skip
    assert code == 0
    assert (tmp_path / "out" / "P0001.xlsx").exists()
    assert (tmp_path / "out" / "P0001.html").exists()


def test_cli_rejects_bad_sales_file(tmp_path: Path):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n")
    with pytest.raises(SystemExit):
        cli.load_sales(bad)


def test_demo_payload_shape(market, mm):  # type: ignore[no-untyped-def]
    d = cli.demo_payload(mm, market.subjects.head(2))
    assert len(d["subjects"]) == 2
    assert "true_value" in d["subjects"][0]
    assert d["disclaimer"]


def test_benchmark_small(market):  # type: ignore[no-untyped-def]
    from comparable_sales_grid.bench import run_benchmark, to_markdown

    b = run_benchmark(market.sales, market.subjects.head(5), market.valuation_date)
    assert set(b["methods"]) == {"regression", "paired", "blend"}
    ref = b["methods"]["regression"]["reference_direct_regression_prediction"]
    assert ref["median_abs_pct_error"] < 10
    assert "Median abs % error" in to_markdown(b)
