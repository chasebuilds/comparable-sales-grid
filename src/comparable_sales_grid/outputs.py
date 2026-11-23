"""Excel workbook and printable HTML page for one grid."""

from __future__ import annotations

import html
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import DISCLAIMER
from .grid import LINE_LABELS, LINES, GridResult, MarketModel
from .market import ATTRS

HEAD = PatternFill("solid", fgColor="2A2019")
FLAG = PatternFill("solid", fgColor="F6C9BD")
MONEY = '"$"#,##0;[Red]-"$"#,##0'
PCT = "0.0%"


def _head(ws, row: int, values: list[str]) -> None:  # type: ignore[no-untyped-def]
    for i, v in enumerate(values, start=1):
        c = ws.cell(row=row, column=i, value=v)
        c.font = Font(bold=True, color="FBF5EE")
        c.fill = HEAD
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def write_workbook(result: GridResult, mm: MarketModel, path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Grid"
    ws["A1"] = "Sales comparison grid"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = DISCLAIMER
    ws["A2"].font = Font(italic=True, color="A8670F")
    comps = result.comps
    n = len(comps)
    ws["A3"] = (
        f"Subject {result.subject.get('subject_id', '')}, valuation date {result.valuation_date}"
    )
    _head(ws, 5, ["Item", "Subject", *[f"Comp {i + 1}" for i in range(n)]])
    r = 6
    ws.cell(row=r, column=1, value="Sale ID")
    ws.cell(row=r + 1, column=1, value="Sale date")
    ws.cell(row=r + 2, column=1, value="Area")
    ws.cell(row=r + 3, column=1, value="Distance (km)")
    ws.cell(row=r + 4, column=1, value="Similarity (0-100)")
    ws.cell(row=r + 5, column=1, value="Sale price")
    ws.cell(row=r + 6, column=1, value="Market conditions (time) adjustment")
    ws.cell(row=r + 7, column=1, value="Time-adjusted price")
    ws.cell(row=r + 2, column=2, value=str(result.subject.get("neighborhood", "")))
    for j, c in enumerate(comps, start=3):
        ws.cell(row=r, column=j, value=c.sale_id)
        ws.cell(row=r + 1, column=j, value=c.sale_date)
        ws.cell(row=r + 2, column=j, value=c.neighborhood)
        ws.cell(row=r + 3, column=j, value=round(c.distance_km, 2))
        ws.cell(row=r + 4, column=j, value=round(c.similarity, 1))
        ws.cell(row=r + 5, column=j, value=round(c.sale_price)).number_format = MONEY
        ws.cell(row=r + 6, column=j, value=round(c.time_adjustment)).number_format = MONEY
        col = get_column_letter(j)
        ws.cell(row=r + 7, column=j, value=f"={col}{r + 5}+{col}{r + 6}").number_format = MONEY
    r_base = r + 7
    r += 9
    ws.cell(row=r - 1, column=1, value="Features (subject and comps)").font = Font(bold=True)
    for k, line in enumerate(LINES):
        row = r + k
        ws.cell(row=row, column=1, value=LINE_LABELS[line])
        if line != "location":
            ws.cell(row=row, column=2, value=float(result.subject[line]))
        for j, c in enumerate(comps, start=3):
            if line != "location":
                ws.cell(row=row, column=j, value=c.attrs[line])
    r += len(LINES) + 1
    ws.cell(row=r - 1, column=1, value="Adjustment amounts").font = Font(bold=True)
    adj_first = r
    for k, line in enumerate(LINES):
        ws.cell(row=r + k, column=1, value=LINE_LABELS[line])
        for j, c in enumerate(comps, start=3):
            ws.cell(row=r + k, column=j, value=round(c.adjustments[line])).number_format = MONEY
    adj_last = r + len(LINES) - 1
    r = adj_last + 2
    labels = [
        "Net adjustment",
        "Gross adjustment",
        "Net adjustment %",
        "Gross adjustment %",
        "Adjusted sale price",
        "Weight",
        "Flags",
        "Why chosen",
    ]
    for k, lab in enumerate(labels):
        ws.cell(row=r + k, column=1, value=lab).font = Font(bold=True)
    for j, c in enumerate(comps, start=3):
        col = get_column_letter(j)
        rng = f"{col}{adj_first}:{col}{adj_last}"
        ws.cell(row=r, column=j, value=f"=SUM({rng})").number_format = MONEY
        ws.cell(row=r + 1, column=j, value=f"=SUMPRODUCT(ABS({rng}))").number_format = MONEY
        ws.cell(row=r + 2, column=j, value=f"={col}{r}/{col}{r_base}").number_format = PCT
        ws.cell(row=r + 3, column=j, value=f"={col}{r + 1}/{col}{r_base}").number_format = PCT
        ws.cell(row=r + 4, column=j, value=f"={col}{r_base}+{col}{r}").number_format = MONEY
        ws.cell(row=r + 5, column=j, value=round(c.weight, 4)).number_format = "0.0%"
        flag_cell = ws.cell(row=r + 6, column=j, value="; ".join(c.flags) or "none")
        if c.flags:
            flag_cell.fill = FLAG
        ws.cell(row=r + 7, column=j, value=c.reason).alignment = Alignment(
            wrap_text=True, vertical="top"
        )
    r_adj, r_w = r + 4, r + 5
    r += len(labels) + 1
    last = get_column_letter(2 + n)
    ws.cell(row=r, column=1, value="Indicated value (weighted)").font = Font(bold=True)
    ws.cell(
        row=r, column=3, value=f"=SUMPRODUCT(C{r_adj}:{last}{r_adj},C{r_w}:{last}{r_w})"
    ).number_format = MONEY
    ws.cell(row=r + 1, column=1, value="Range low")
    ws.cell(row=r + 1, column=3, value=f"=MIN(C{r_adj}:{last}{r_adj})").number_format = MONEY
    ws.cell(row=r + 2, column=1, value="Range high")
    ws.cell(row=r + 2, column=3, value=f"=MAX(C{r_adj}:{last}{r_adj})").number_format = MONEY
    ws.cell(
        row=r + 3,
        column=1,
        value="Flag rules: net over 15% or gross over 25% of the time-adjusted price.",
    )
    ws.cell(row=r + 4, column=1, value="Leave-one-out spread (indicated value without each comp)")
    ws.cell(row=r + 4, column=3, value=f"{result.loo_spread_pct:.1%} of indicated value")
    ws.cell(row=r + 5, column=1, value="Bracketing (subject inside the comps' range)")
    ws.cell(
        row=r + 5,
        column=3,
        value="; ".join(
            f"{LINE_LABELS[k]}: {'yes' if v else 'NO'}" for k, v in result.bracketing.items()
        ),
    )
    ws.column_dimensions["A"].width = 40
    for j in range(2, 3 + n):
        ws.column_dimensions[get_column_letter(j)].width = 22
    ws.freeze_panes = "B6"

    wc = wb.create_sheet("Comps")
    cols = [
        "sale_id",
        "sale_date",
        "neighborhood",
        "distance_km",
        "months_ago",
        "similarity",
        *ATTRS,
        "sale_price",
        "gross_pct",
        "net_pct",
        "chosen",
    ]
    _head(wc, 1, cols)
    chosen_ids = {c.sale_id for c in comps}
    for i, c in enumerate([*comps, *result.candidates], start=2):
        vals = [
            c.sale_id,
            c.sale_date,
            c.neighborhood,
            round(c.distance_km, 2),
            c.months_ago,
            round(c.similarity, 1),
            *[c.attrs[a] for a in ATTRS],
            round(c.sale_price),
            round(c.gross_pct, 4),
            round(c.net_pct, 4),
            "yes" if c.sale_id in chosen_ids else "no",
        ]
        for j, v in enumerate(vals, start=1):
            wc.cell(row=i, column=j, value=v)
    for j in range(1, len(cols) + 1):
        wc.column_dimensions[get_column_letter(j)].width = 14

    we = wb.create_sheet("Adjustment evidence")
    we["A1"] = (
        "Rates are changes in ln(price) per unit (per ln unit for GLA and lot). "
        f"Method used: {mm.rates.method}. Blend = average of regression and paired when paired has 10+ pairs."
    )
    _head(
        we,
        3,
        [
            "Feature",
            "Regression rate",
            "Regression SE",
            "Paired rate",
            "Paired pairs",
            "Rate used",
            "Approx % per unit at rate used",
        ],
    )
    for i, er in enumerate(mm.rates.evidence_rows(), start=4):
        we.cell(row=i, column=1, value=LINE_LABELS[er["feature"]])
        we.cell(row=i, column=2, value=er["regression_rate"])
        we.cell(row=i, column=3, value=er["regression_se"])
        we.cell(row=i, column=4, value=er["paired_rate"])
        we.cell(row=i, column=5, value=er["paired_pairs"])
        we.cell(row=i, column=6, value=er["used_rate"])
        we.cell(row=i, column=7, value=f"=EXP(F{i})-1").number_format = "0.00%"
    base = 4 + len(ATTRS) + 2
    we.cell(row=base, column=1, value="Model fit").font = Font(bold=True)
    we.cell(row=base + 1, column=1, value="Sales used")
    we.cell(row=base + 1, column=2, value=mm.model.n)
    we.cell(row=base + 2, column=1, value="R squared (ln price)")
    we.cell(row=base + 2, column=2, value=round(mm.model.r2, 4))
    we.cell(row=base + 3, column=1, value="Residual SD (ln price)")
    we.cell(row=base + 3, column=2, value=round(mm.model.resid_sd, 4))
    we.cell(row=base + 5, column=1, value="Area effects (ln price vs first area)").font = Font(
        bold=True
    )
    for k, (a, v) in enumerate(sorted(mm.model.area_effect.items()), start=base + 6):
        we.cell(row=k, column=1, value=a)
        we.cell(row=k, column=2, value=v)
    for col, w in zip("ABCDEFG", (34, 16, 14, 14, 13, 12, 26), strict=True):
        we.column_dimensions[col].width = w

    wm = wb.create_sheet("Market index")
    _head(wm, 1, ["Month", "ln index", "Index (first month = 100)", "Note"])
    months = sorted(mm.model.month_effect)
    for i, m in enumerate([*months, mm.valuation_month], start=2):
        total = mm.model.base[0] * 12 + (mm.model.base[1] - 1) + m
        wm.cell(row=i, column=1, value=f"{total // 12:04d}-{total % 12 + 1:02d}")
        ln = mm.model.log_index(m)
        wm.cell(row=i, column=2, value=ln)
        wm.cell(row=i, column=3, value=f"=100*EXP(B{i})")
        if m == mm.valuation_month and m not in mm.model.month_effect:
            wm.cell(row=i, column=4, value="valuation month, extrapolated from last 6 months")
    wm.column_dimensions["D"].width = 48

    wn = wb.create_sheet("Notes")
    for i, line in enumerate(
        [DISCLAIMER, "", *result.notes, "Data is synthetic. See LIMITATIONS.md in the repository."],
        start=1,
    ):
        wn.cell(row=i, column=1, value=line)
    wn.column_dimensions["A"].width = 120
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def _money(v: float) -> str:
    return f"${v:,.0f}" if v >= 0 else f"-${-v:,.0f}"


def render_html(result: GridResult, mm: MarketModel) -> str:
    e = html.escape
    comps = result.comps
    head = "".join(
        f"<th>Comp {i + 1}<br><small>{e(c.sale_id)}</small></th>" for i, c in enumerate(comps)
    )

    def row(label: str, subj: str, cells: list[str], cls: str = "") -> str:
        tds = "".join(f"<td>{c}</td>" for c in cells)
        return f'<tr class="{cls}"><th>{e(label)}</th><td>{subj}</td>{tds}</tr>'

    s = result.subject
    body = [
        row("Sale date", "", [e(c.sale_date) for c in comps]),
        row("Area", e(str(s.get("neighborhood", ""))), [e(c.neighborhood) for c in comps]),
        row("Distance (km)", "", [f"{c.distance_km:.2f}" for c in comps]),
        row("Similarity", "", [f"{c.similarity:.0f}" for c in comps]),
        row("Sale price", "", [_money(c.sale_price) for c in comps], "strong"),
        row("Time adjustment", "", [_money(c.time_adjustment) for c in comps]),
        row("Time-adjusted price", "", [_money(c.time_adjusted_price) for c in comps], "strong"),
    ]
    for line in LINES:
        if line == "location":
            body.append(row(LINE_LABELS[line], "", [_money(c.adjustments[line]) for c in comps]))
        else:
            body.append(
                row(
                    LINE_LABELS[line],
                    f"{float(s[line]):g}",
                    [f"{c.attrs[line]:g}<br><b>{_money(c.adjustments[line])}</b>" for c in comps],
                )
            )
    body += [
        row(
            "Net adjustment",
            "",
            [f"{_money(c.net_adjustment)} ({c.net_pct:+.1%})" for c in comps],
            "strong",
        ),
        row(
            "Gross adjustment",
            "",
            [f"{_money(c.gross_adjustment)} ({c.gross_pct:.1%})" for c in comps],
        ),
        row("Adjusted price", "", [_money(c.adjusted_price) for c in comps], "strong"),
        row("Weight", "", [f"{c.weight:.0%}" for c in comps]),
        row("Flags", "", [e(", ".join(c.flags)) or "none" for c in comps]),
        row("Why chosen", "", [e(c.reason) for c in comps]),
    ]
    ev = "".join(
        f"<tr><td>{e(LINE_LABELS[r['feature']])}</td><td>{r['regression_rate']:+.4f}</td>"
        f"<td>{'' if r['paired_rate'] is None else format(r['paired_rate'], '+.4f')}</td>"
        f"<td>{r['paired_pairs']}</td><td>{r['used_rate']:+.4f}</td></tr>"
        for r in mm.rates.evidence_rows()
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Sales comparison grid {e(str(s.get("subject_id", "")))}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{font:13px/1.45 system-ui,sans-serif;color:#2a2019;margin:24px;max-width:1100px}}
h1{{font-size:20px;margin:0 0 4px}} .warn{{background:#fbefd5;border:1px solid #e0b660;padding:8px 12px;border-radius:8px}}
table{{border-collapse:collapse;width:100%;margin:14px 0}} th,td{{border:1px solid #d9cdbf;padding:5px 8px;text-align:right;vertical-align:top}}
th:first-child{{text-align:left;width:190px}} thead th{{background:#2a2019;color:#fbf5ee}} tr.strong td,tr.strong th{{background:#f4ece2}}
.big{{font-size:22px;font-weight:700}} @media print{{body{{margin:8mm}} .warn{{break-inside:avoid}}}}
</style></head><body>
<h1>Sales comparison grid</h1>
<p>Subject {e(str(s.get("subject_id", "")))} in {e(str(s.get("neighborhood", "")))}, valuation date {e(result.valuation_date)}.</p>
<p class="warn"><b>Not an appraisal.</b> {e(DISCLAIMER)}</p>
<table><thead><tr><th>Item</th><th>Subject</th>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>
<p class="big">Indicated value {_money(round(result.indicated_value, -2))}
<span style="font-weight:400;font-size:14px"> range {_money(result.range_low)} to {_money(result.range_high)}</span></p>
<p>Leave-one-out: dropping any single comp moves the indicated value by up to {result.loo_spread_pct:.1%} across the cases.
Not bracketed by the comps: {e(", ".join(LINE_LABELS[k] for k, v in result.bracketing.items() if not v) or "none")}.</p>
<p>Weights are the inverse of each comp's gross adjustment percent (floor 3%). Flag rules: net over 15% or gross over 25% of the time-adjusted price.
{e(" ".join(result.notes))}</p>
<h2>Adjustment evidence</h2>
<p>Rates are changes in ln(price) per unit (per ln unit for living area and lot). Method used: {e(mm.rates.method)}.
Model fit on {mm.model.n} sales: R squared {mm.model.r2:.3f}.</p>
<table><thead><tr><th>Feature</th><th>Regression</th><th>Paired sales</th><th>Pairs</th><th>Used</th></tr></thead><tbody>{ev}</tbody></table>
</body></html>
"""
