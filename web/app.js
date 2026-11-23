"use strict";
const LINES = ["location", "gla", "beds", "baths", "age", "lot", "condition", "quality"];
const LABELS = {
  location: "Location (area)", gla: "Living area (sf)", beds: "Bedrooms", baths: "Bathrooms",
  age: "Age (years)", lot: "Lot (sf)", condition: "Condition (1-5)", quality: "Quality (1-5)"
};
const stage = document.getElementById("stage");
let DATA = null;
let view = "grid";
let current = 0;

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (v) => (v < 0 ? "-$" : "$") + Math.abs(Math.round(v)).toLocaleString("en-US");
const pct = (v, signed) => (signed && v > 0 ? "+" : "") + (v * 100).toFixed(1) + "%";
const cls = (v) => (v < -0.5 ? "neg" : v > 0.5 ? "pos" : "");

function gridView() {
  const s = DATA.subjects[current];
  const sj = s.subject;
  const comps = s.comps;
  const err = s.indicated_value / s.true_value - 1;
  const inRange = s.true_value >= s.range_low && s.true_value <= s.range_high;
  const options = DATA.subjects
    .map((x, i) => `<option value="${i}" ${i === current ? "selected" : ""}>${esc(x.subject.subject_id)} - ${esc(x.subject.neighborhood)}, ${Math.round(x.subject.gla).toLocaleString()} sf</option>`)
    .join("");
  const head = comps.map((c, i) => `<th>Comp ${i + 1}<br><small class="num">${esc(c.sale_id)}</small></th>`).join("");
  const cells = (fn, c2) => comps.map((c) => `<td class="${c2 ? c2(c) : ""}">${fn(c)}</td>`).join("");
  let rows = "";
  rows += `<tr><td>Sale date</td><td></td>${cells((c) => esc(c.sale_date))}</tr>`;
  rows += `<tr><td>Area</td><td>${esc(sj.neighborhood)}</td>${cells((c) => esc(c.neighborhood))}</tr>`;
  rows += `<tr><td>Distance (km)</td><td></td>${cells((c) => c.distance_km.toFixed(2))}</tr>`;
  rows += `<tr><td>Similarity (0-100)</td><td></td>${cells((c) => c.similarity.toFixed(0))}</tr>`;
  rows += `<tr class="strong"><td>Sale price</td><td></td>${cells((c) => money(c.sale_price))}</tr>`;
  rows += `<tr><td>Market conditions (time)</td><td></td>${cells((c) => money(c.time_adjustment), (c) => cls(c.time_adjustment))}</tr>`;
  rows += `<tr class="strong"><td>Time-adjusted price</td><td></td>${cells((c) => money(c.time_adjusted_price))}</tr>`;
  rows += `<tr class="sec"><td colspan="${comps.length + 2}">Line-item adjustments (comp value, then dollars)</td></tr>`;
  for (const l of LINES) {
    const subj = l === "location" ? "" : Number(sj[l]).toLocaleString();
    rows += `<tr><td>${LABELS[l]}</td><td>${subj}</td>${cells(
      (c) => (l === "location" ? "" : `${c.attrs[l].toLocaleString()}<br>`) + `<b>${money(c.adjustments[l])}</b>`,
      (c) => cls(c.adjustments[l])
    )}</tr>`;
  }
  rows += `<tr class="strong"><td>Net adjustment</td><td></td>${cells((c) => `${money(c.net_adjustment)} (${pct(c.net_pct, true)})`)}</tr>`;
  rows += `<tr><td>Gross adjustment</td><td></td>${cells((c) => `${money(c.gross_adjustment)} (${pct(c.gross_pct)})`)}</tr>`;
  rows += `<tr class="strong"><td>Adjusted price</td><td></td>${cells((c) => money(c.adjusted_price))}</tr>`;
  rows += `<tr><td>Weight</td><td></td>${cells((c) => (c.weight * 100).toFixed(0) + "%")}</tr>`;
  rows += `<tr><td>Flags (15% net, 25% gross)</td><td></td>${cells((c) => (c.flags.length ? `<span class="pill bad">${esc(c.flags.join(", "))}</span>` : `<span class="pill good">within guidelines</span>`))}</tr>`;
  rows += `<tr><td>Why chosen</td><td></td>${comps.map((c) => `<td class="why">${esc(c.reason)}</td>`).join("")}</tr>`;
  return `<div class="view">
    <div class="picker"><label for="pick">Subject</label><select id="pick">${options}</select>
      <span class="note">${s.n_candidates} candidate sales in the search window. ${esc(s.notes.join(" "))}</span></div>
    <div class="tiles">
      <div class="card tile solid"><span class="lbl">Indicated value</span><span class="big num">${money(Math.round(s.indicated_value / 100) * 100)}</span><span class="note" style="color:inherit;opacity:.75">weighted over ${comps.length} comps</span></div>
      <div class="card tile"><span class="lbl">Range from comps</span><span class="big num" style="font-size:19px">${money(s.range_low)} to ${money(s.range_high)}</span></div>
      <div class="card tile"><span class="lbl">Known synthetic truth</span><span class="big num">${money(s.true_value)}</span><span class="note">only exists because the data is made up</span></div>
      <div class="card tile"><span class="lbl">Error vs truth</span><span class="big num">${pct(err, true)}</span><span class="pill ${inRange ? "good" : "warn"}">${inRange ? "truth inside range" : "truth outside range"}</span></div>
    </div>
    <div class="card scroll"><table><thead><tr><th>Item</th><th>Subject</th>${head}</tr></thead><tbody>${rows}</tbody></table></div>
    <div class="card panel-card"><h2>Checks an appraiser would make</h2>
      <p><b>Leave-one-out:</b> dropping any single comp moves the indicated value by up to ${pct(s.loo_spread_pct)} across the cases (${s.leave_one_out.map(money).join(", ")}).</p>
      <p><b>Bracketing:</b> ${Object.entries(s.bracketing).map(([k, v]) => `<span class="pill ${v ? "good" : "warn"}">${LABELS[k]}: ${v ? "bracketed" : "not bracketed"}</span>`).join(" ")}</p></div>
    <p class="note">Weights are the inverse of each comp's gross adjustment percent (floor 3%). Percentages are of the time-adjusted price.</p>
  </div>`;
}

function evidenceView() {
  const rows = DATA.evidence
    .map((r) => `<tr><td>${LABELS[r.feature]}</td><td>${r.regression_rate.toFixed(4)}</td><td>${r.regression_se.toFixed(4)}</td><td>${r.paired_rate === null ? "n/a" : r.paired_rate.toFixed(4)}</td><td>${r.paired_pairs}</td><td>${r.used_rate.toFixed(4)}</td></tr>`)
    .join("");
  const areas = Object.entries(DATA.area_effect)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v.toFixed(3)}</td><td>${pct(Math.exp(v) - 1, true)}</td></tr>`)
    .join("");
  return `<div class="view">
    <div class="card panel-card"><h2>Where the adjustment rates come from</h2>
      <p>Each rate is the change in ln(price) per unit (per ln unit for living area and lot). Two estimates are shown side by side: a regression on all ${DATA.n_sales.toLocaleString()} sales (R squared ${DATA.r2.toFixed(3)}), and paired sales, which are same-area sale pairs that match on everything else and differ in one feature. Method used here: ${esc(DATA.method)}. Options: regression, paired, or blend (the average of the two when paired has 10 or more pairs); the benchmark compares all three.</p>
      <div class="scroll"><table style="min-width:520px"><thead><tr><th>Feature</th><th>Regression</th><th>Std error</th><th>Paired</th><th>Pairs</th><th>Used</th></tr></thead><tbody>${rows}</tbody></table></div></div>
    <div class="card panel-card"><h2>Area effects</h2>
      <p>Location adjustments come from the area fixed effects in the regression, measured against the first area alphabetically.</p>
      <div class="scroll"><table style="min-width:360px"><thead><tr><th>Area</th><th>ln effect</th><th>vs first area</th></tr></thead><tbody>${areas}</tbody></table></div></div>
  </div>`;
}

function aboutView() {
  return `<div class="view">
    <div class="card panel-card"><h2>What this does</h2>
      <p>Takes one subject property and a file of sales, searches for comparable sales by distance, recency and similarity, picks 3 to 6, adjusts each comp line by line, then reconciles to one weighted value and a range.</p>
      <p>The adjustments are measured from the sales file, not typed in. Net and gross percentages are checked against the usual 15% and 25% guidelines.</p></div>
    <div class="card panel-card"><h2>What it is not</h2>
      <p>${esc(DATA.disclaimer)}</p>
      <p>Every property and sale here is synthetic, generated with a seeded model, so the true value of each subject is known. Real sales carry noise and unobserved features, so real errors will be larger than the benchmark numbers in the repository.</p></div>
    <div class="card panel-card"><h2>Get the workbook</h2>
      <p>The command line tool writes an Excel workbook (grid, comps, adjustment evidence, market index) and a printable HTML page for any subject. See the <a href="https://github.com/chasebuilds/comparable-sales-grid">repository</a>.</p></div>
  </div>`;
}

function render() {
  if (!DATA) return;
  stage.innerHTML = `<div class="warn"><b>Not an appraisal.</b> ${esc(DATA.disclaimer)}</div>
    <h1>Comparable Sales Grid</h1><p class="sub">Pick a synthetic subject and see how the sales comparison approach gets to a value.</p>` +
    (view === "grid" ? gridView() : view === "evidence" ? evidenceView() : aboutView());
  const pick = document.getElementById("pick");
  if (pick) pick.addEventListener("change", () => { current = Number(pick.value); render(); });
  document.querySelectorAll(".dock button").forEach((b) => b.setAttribute("aria-current", b.dataset.view === view ? "page" : "false"));
}

document.querySelectorAll(".dock button").forEach((b) => b.addEventListener("click", () => { view = b.dataset.view; render(); }));
fetch("data.json")
  .then((r) => r.json())
  .then((d) => {
    DATA = d;
    document.getElementById("chip").textContent = `${d.n_sales.toLocaleString()} synthetic sales, valuation ${d.valuation_date}`;
    const q = new URLSearchParams(location.search).get("subject");
    const i = q ? d.subjects.findIndex((x) => x.subject.subject_id === q) : -1;
    if (i >= 0) current = i;
    const v = new URLSearchParams(location.search).get("view");
    if (v === "evidence" || v === "about") view = v;
    render();
  })
  .catch((e) => { stage.textContent = "Could not load data.json: " + e; });
