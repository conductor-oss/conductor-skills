#!/usr/bin/env python3
"""Render Conductor-skill eval reports as a single-page HTML.

Consumes one or more JSON reports produced by run_evals.py and emits an
HTML page with:
  - Run summary (per-model totals)
  - Per-scenario matrix (all models side-by-side)
  - Per-scenario drill-down with each failing criterion and the judge's reason

Inline CSS, no external assets. Render output works open-in-browser or
as a CI artifact.

Usage:
  python3 scripts/render_evals_html.py report.json -o report.html
  python3 scripts/render_evals_html.py claude.json gpt.json gemini.json -o compare.html
"""

import argparse
import html
import json
import sys
from datetime import datetime
from pathlib import Path


def load_report(path):
    d = json.loads(Path(path).read_text())
    results = d.get("results") or []
    by_name = {r["name"]: r for r in results}
    return {
        "label": d.get("model") or Path(path).stem,
        "provider": d.get("provider"),
        "model": d.get("model"),
        "judge": d.get("judge_model"),
        "timestamp": d.get("timestamp"),
        "results": by_name,
    }


def pass_rate(report):
    rs = report["results"].values()
    n = len(rs)
    p = sum(1 for r in rs if r.get("overall_pass"))
    crit_total = sum(r.get("total", 0) for r in rs)
    crit_pass = sum(r.get("passed", 0) for r in rs)
    return {"evals": (p, n), "criteria": (crit_pass, crit_total)}


def render(reports, title="Conductor Skill — Eval Report"):
    all_names = sorted({n for r in reports for n in r["results"].keys()})

    css = """
    :root {
      --bg: #fafafa;
      --panel: #ffffff;
      --border: #e6e6e8;
      --muted: #6b7280;
      --text: #18181b;
      --pass: #15803d;
      --pass-bg: #ecfdf5;
      --fail: #b91c1c;
      --fail-bg: #fef2f2;
      --partial-bg: #fffbeb;
      --partial: #92400e;
      --link: #2563eb;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; padding: 32px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, "Helvetica Neue", sans-serif;
      color: var(--text); background: var(--bg);
      font-size: 14px; line-height: 1.5;
    }
    h1 { font-size: 24px; margin: 0 0 4px; font-weight: 600; }
    h2 { font-size: 16px; margin: 32px 0 12px; font-weight: 600; }
    .sub { color: var(--muted); font-size: 13px; margin-bottom: 24px; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;
    }
    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 24px; }
    .card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; }
    .card .label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 6px; font-weight: 500; }
    .card .model { font-size: 13px; font-weight: 600; color: var(--text); margin-bottom: 10px; font-family: ui-monospace, "SF Mono", Menlo, monospace; }
    .card .stat { display: flex; align-items: baseline; gap: 8px; }
    .card .big { font-size: 24px; font-weight: 600; }
    .card .small { color: var(--muted); font-size: 12px; }
    .bar { height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; margin-top: 8px; }
    .bar > div { height: 100%; }
    .bar.green > div { background: var(--pass); }
    .bar.yellow > div { background: #f59e0b; }
    .bar.red > div { background: var(--fail); }
    table { width: 100%; border-collapse: collapse; font-size: 13px; background: var(--panel); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
    th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); }
    th { background: #f4f4f5; font-weight: 600; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
    tr:last-child td { border-bottom: none; }
    td.eval-name { font-weight: 500; }
    td.cell { font-family: ui-monospace, "SF Mono", Menlo, monospace; white-space: nowrap; }
    .pill { display: inline-flex; align-items: center; gap: 6px; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 500; }
    .pill.pass { background: var(--pass-bg); color: var(--pass); }
    .pill.fail { background: var(--fail-bg); color: var(--fail); }
    .pill.partial { background: var(--partial-bg); color: var(--partial); }
    .pill.empty { background: #f4f4f5; color: var(--muted); }
    details { margin-bottom: 8px; }
    details summary { cursor: pointer; padding: 10px 14px; background: var(--panel); border: 1px solid var(--border); border-radius: 8px; font-weight: 500; list-style: none; display: flex; align-items: center; gap: 10px; }
    details summary::before { content: "▸"; color: var(--muted); font-size: 12px; transition: transform 0.15s; }
    details[open] summary::before { transform: rotate(90deg); }
    details summary::-webkit-details-marker { display: none; }
    details > div { padding: 14px 16px; background: var(--panel); border: 1px solid var(--border); border-top: none; border-radius: 0 0 8px 8px; margin-top: -1px; }
    .crit { display: grid; grid-template-columns: 16px 1fr; gap: 8px; padding: 6px 0; align-items: start; font-size: 13px; border-bottom: 1px solid #f4f4f5; }
    .crit:last-child { border-bottom: none; }
    .crit .icon { font-weight: 600; line-height: 1.4; }
    .crit.pass .icon { color: var(--pass); }
    .crit.fail .icon { color: var(--fail); }
    .crit .text { color: var(--text); }
    .crit .reason { color: var(--muted); font-size: 12px; margin-top: 3px; font-style: italic; }
    .footer { color: var(--muted); font-size: 12px; margin-top: 32px; text-align: center; }
    .legend { color: var(--muted); font-size: 12px; margin-top: 4px; }
    code { font-family: ui-monospace, "SF Mono", Menlo, monospace; background: #f4f4f5; padding: 1px 5px; border-radius: 3px; font-size: 12px; }
    """

    # Per-model summary cards
    cards = []
    for r in reports:
        rate = pass_rate(r)
        ep, en = rate["evals"]
        cp, ct = rate["criteria"]
        pct = (cp / ct * 100) if ct else 0
        bar_class = "green" if pct >= 95 else ("yellow" if pct >= 80 else "red")
        cards.append(f"""
          <div class="card">
            <div class="label">Model</div>
            <div class="model">{html.escape(r['label'])}</div>
            <div class="stat"><span class="big">{ep}/{en}</span><span class="small">evals passed</span></div>
            <div class="stat" style="margin-top:6px;"><span class="big">{cp}/{ct}</span><span class="small">criteria ({pct:.1f}%)</span></div>
            <div class="bar {bar_class}"><div style="width:{pct:.1f}%"></div></div>
          </div>""")

    # Matrix header
    header_cells = "".join(f"<th>{html.escape(r['label'])}</th>" for r in reports)

    # Matrix rows
    rows = []
    for n in all_names:
        cells = []
        for r in reports:
            res = r["results"].get(n)
            if res is None:
                cells.append('<td class="cell"><span class="pill empty">—</span></td>')
                continue
            overall = res.get("overall_pass")
            p, t = res.get("passed", 0), res.get("total", 0)
            crit_failed = sum(1 for c in res.get("criteria_results", []) if not c.get("pass"))
            if overall and crit_failed == 0:
                cells.append(f'<td class="cell"><span class="pill pass">PASS {p}/{t}</span></td>')
            elif overall:
                cells.append(f'<td class="cell"><span class="pill partial">PASS {p}/{t}</span></td>')
            else:
                cells.append(f'<td class="cell"><span class="pill fail">FAIL {p}/{t}</span></td>')
        rows.append(f"<tr><td class='eval-name'>{html.escape(n)}</td>{''.join(cells)}</tr>")
    matrix_table = f"""
      <table>
        <thead><tr><th>Scenario</th>{header_cells}</tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>"""

    # Drill-down per scenario (only when at least one model has criteria detail)
    drill_blocks = []
    for n in all_names:
        per_model_blocks = []
        any_fail = False
        for r in reports:
            res = r["results"].get(n)
            if res is None:
                continue
            criteria = res.get("criteria_results", [])
            if not criteria:
                continue
            crit_html = []
            for c in criteria:
                cls = "pass" if c.get("pass") else "fail"
                icon = "✓" if c.get("pass") else "✗"
                reason = c.get("reason") or ""
                if not c.get("pass"):
                    any_fail = True
                reason_html = f'<div class="reason">{html.escape(reason)}</div>' if reason and not c.get("pass") else ""
                crit_html.append(f"""
                  <div class="crit {cls}">
                    <div class="icon">{icon}</div>
                    <div class="text">{html.escape(c.get('criterion',''))}{reason_html}</div>
                  </div>""")
            p, t = res.get("passed", 0), res.get("total", 0)
            overall = res.get("overall_pass")
            pill = ('<span class="pill pass">PASS</span>' if overall and p==t else
                    '<span class="pill partial">PASS w/ deltas</span>' if overall else
                    '<span class="pill fail">FAIL</span>')
            per_model_blocks.append(f"""
              <div style="margin-bottom:14px;">
                <div style="display:flex; align-items:center; gap:10px; margin-bottom:6px;">
                  <code>{html.escape(r['label'])}</code> {pill}
                  <span class="small" style="color:var(--muted);font-size:12px;">{p}/{t} criteria</span>
                </div>
                {''.join(crit_html)}
              </div>""")
        if per_model_blocks and any_fail:
            drill_blocks.append(f"""
              <details>
                <summary>{html.escape(n)}</summary>
                <div>{''.join(per_model_blocks)}</div>
              </details>""")
    drill_html = "".join(drill_blocks) or "<p style='color:var(--muted)'>No failing criteria recorded.</p>"

    now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    metas = " · ".join(f"<code>{html.escape(r['label'])}</code>" for r in reports)

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>{css}</style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <div class="sub">Generated {now} · Models: {metas} · Judge: <code>{html.escape(reports[0]['judge'] or 'claude-sonnet-4-20250514')}</code></div>

  <h2>Summary</h2>
  <div class="cards">{''.join(cards)}</div>

  <h2>Per-scenario matrix</h2>
  <div class="legend">Pill shape: <span class="pill pass">PASS</span> all criteria · <span class="pill partial">PASS</span> with criteria deltas · <span class="pill fail">FAIL</span> overall · <span class="pill empty">—</span> not run</div>
  <div style="margin-top:12px;">{matrix_table}</div>

  <h2>Failures &amp; deltas — drill-down</h2>
  <div class="legend">Only scenarios with at least one failing criterion are shown. Click to expand.</div>
  <div style="margin-top:12px;">{drill_html}</div>

  <div class="footer">conductor-skills evals · run_evals.py + render_evals_html.py</div>
</body>
</html>"""
    return html_doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reports", nargs="+", help="One or more eval JSON reports")
    ap.add_argument("-o", "--output", required=True, help="Output HTML path")
    ap.add_argument("--title", default="Conductor Skill — Eval Report")
    args = ap.parse_args()

    loaded = [load_report(p) for p in args.reports]
    html_doc = render(loaded, title=args.title)
    Path(args.output).write_text(html_doc)
    print(f"Wrote {args.output}")
    print(f"  Reports: {len(loaded)} model(s)")
    print(f"  Evals:   {len({n for r in loaded for n in r['results']})} unique scenarios")
    return 0


if __name__ == "__main__":
    sys.exit(main())
