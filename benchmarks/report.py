"""Outputs: PNG charts, a markdown summary and a single-file HTML report."""
from __future__ import annotations

import html
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import PercentFormatter  # noqa: E402

from .data import AMOUNT, COUNT, RATIO, Company, Dataset, derived  # noqa: E402

REPORTED, MODEL = "#2a78d6", "#eb6834"  # categorical slots 1 and 2
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

# Columns of the main table: (key, label, source) where source "derived" means computed here
TABLE = [
    ("total_assets", "Total assets", "reported"),
    ("loans", "Loans", "reported"),
    ("deposits", "Deposits", "reported"),
    ("equity", "Equity", "reported"),
    ("total_income", "Total income", "reported"),
    ("net_profit", "Net profit", "reported"),
    ("roe", "ROE", "reported"),
    ("cost_income", "Cost / income", "reported"),
    ("cost_of_risk", "Cost of risk", "reported"),
    ("nim", "NIM", "reported"),
    ("loan_yield", "Loan yield", "reported"),
    ("fee_share", "Fees / income", "reported"),
    ("customers", "Customers (m)", "reported"),
    ("loan_to_deposit", "Loans / deposits", "derived"),
    ("equity_to_assets", "Equity / assets", "derived"),
]


def _value(ds: Dataset, c: Company, key: str, source: str):
    return derived(ds, c)[key] if source == "derived" else c.get(key)


def _fmt(ds: Dataset, c: Company, key: str, source: str) -> str:
    v = _value(ds, c, key, source)
    if v is None:
        return "n/a"
    kind = RATIO if source == "derived" else ds.metric(key).kind
    if kind == RATIO:
        return f"{v:.1%}"
    if kind == COUNT:
        return f"{v:,.1f}"
    sym = {"EUR": "€", "GBP": "£", "SEK": "SEK "}.get(c.currency, c.currency + " ")
    return f"{sym}{v / 1000:,.2f}bn" if abs(v) >= 1000 else f"{sym}{v:,.1f}m"


def _style(ax, title: str) -> None:
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color=INK)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=INK_2)
    ax.set_axisbelow(True)


def _bar_chart(ds: Dataset, key: str, title: str, xlabel: str, path: Path, source: str = "reported") -> Path | None:
    rows = [(c, _value(ds, c, key, source)) for c in ds.companies]
    rows = sorted([(c, v) for c, v in rows if v is not None], key=lambda r: r[1])
    if not rows:
        return None
    fig, ax = plt.subplots(figsize=(8, 0.45 * len(rows) + 1.4))
    y = range(len(rows))
    ax.barh(list(y), [v for _, v in rows], color=[MODEL if c.is_model else REPORTED for c, _ in rows], height=0.62)
    ax.set_yticks(list(y), [c.name for c, _ in rows])
    xmax = max(v for _, v in rows)
    for yi, (c, v) in zip(y, rows):
        ax.text(v + xmax * 0.01, yi, f"{v:.1%}", va="center", color=INK, fontsize=9)
    ax.set_xlim(0, xmax * 1.15)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xlabel(xlabel, color=INK_2)
    ax.grid(axis="x", color=GRID)
    _style(ax, title)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=REPORTED), plt.Rectangle((0, 0), 1, 1, color=MODEL)],
              labels=["Reported, latest full year", "Bank X model, year 5"], frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def write_charts(ds: Dataset, outdir: Path) -> list[Path]:
    files = []
    pts = [(c, c.get("cost_income"), c.get("roe")) for c in ds.companies]
    pts = [p for p in pts if p[1] is not None and p[2] is not None and -0.5 < p[2] < 0.6]
    fig, ax = plt.subplots(figsize=(8, 5.2))
    for is_model, color, marker, label in [(False, REPORTED, "o", "Reported, latest full year"),
                                           (True, MODEL, "D", "Bank X model, year 5")]:
        sel = [p for p in pts if p[0].is_model == is_model]
        ax.scatter([p[1] for p in sel], [p[2] for p in sel], s=70, color=color, marker=marker,
                   edgecolor="white", linewidth=2, label=label, zorder=3)
        for c, x, y in sel:
            # Model points are labelled below-left so they do not collide with the reported banks around them
            offset, ha = ((-8, -14), "right") if c.is_model else ((7, 5), "left")
            ax.annotate(c.name, (x, y), xytext=offset, textcoords="offset points", fontsize=9, color=INK, ha=ha)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Cost / income (lower is better)", color=INK_2)
    ax.set_ylabel("Return on equity", color=INK_2)
    ax.axhline(0, color=INK_2, linewidth=0.8)
    ax.grid(color=GRID)
    ax.set_xlim(left=0)
    _style(ax, "Profitability vs efficiency")
    ax.legend(frameon=False, loc="upper right")
    files.append(outdir / "roe_vs_cost_income.png")
    fig.tight_layout()
    fig.savefig(files[-1], dpi=150)
    plt.close(fig)

    for key, title, xlabel, name, source in [
        ("cost_of_risk", "Cost of risk: credit losses as % of average loans", "% of average loans", "cost_of_risk.png", "reported"),
        ("loan_to_deposit", "Loans as % of deposits", "Loans / deposits", "loans_to_deposits.png", "derived"),
    ]:
        p = _bar_chart(ds, key, title, xlabel, outdir / name, source)
        if p:
            files.append(p)
    return files


def _flagged(ds: Dataset) -> list[str]:
    return [f"{c.name} / {ds.metric(k).label}" + (f": {v.note}" if v.note else "")
            for c in ds.companies for k, v in c.values.items() if v.needs_check]


def write_markdown(ds: Dataset, findings: list[str], path: Path) -> None:
    lines = [f"# {ds.title}", "", f"Data as of {ds.as_of}. Amounts in reporting currency.", ""]
    lines += [f"{i}. {f}" for i, f in enumerate(findings, 1)]
    head = ["Company", "Period"] + [label for _, label, _ in TABLE]
    lines += ["", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for c in ds.companies:
        lines.append("| " + " | ".join([c.name, c.period] + [_fmt(ds, c, k, s) for k, _, s in TABLE]) + " |")
    flagged = _flagged(ds)
    if flagged:
        lines += ["", "## Values flagged needs_check", ""] + [f"- {f}" for f in flagged]
    lines += ["", "![ROE vs cost/income](roe_vs_cost_income.png)", "", "![Cost of risk](cost_of_risk.png)", "",
              "![Loans to deposits](loans_to_deposits.png)", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


CSS = """
.viz-root{color-scheme:light;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e4e3df;--link:#2a78d6;--model:#fdf0ea}
@media (prefers-color-scheme:dark){.viz-root{color-scheme:dark;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#383835;--link:#3987e5;--model:#3a2a22}}
body{margin:0;font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
.viz-root{background:var(--surface);color:var(--ink);padding:32px;max-width:1400px;margin:auto}
h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 12px}.muted{color:var(--ink2)}
ol{max-width:900px}li{margin:6px 0}
.scroll{overflow-x:auto}table{border-collapse:collapse;font-variant-numeric:tabular-nums;white-space:nowrap}
th,td{text-align:right;padding:6px 10px;border-bottom:1px solid var(--grid)}th:first-child,td:first-child{text-align:left}
th{color:var(--ink2);font-weight:600}tr.model td{background:var(--model)}
td[title]{cursor:help}.flag{color:#b06d00;font-weight:600}a{color:var(--link)}
img{max-width:100%;height:auto}
"""


def write_html(ds: Dataset, findings: list[str], charts: list[Path], path: Path) -> None:
    import base64

    e = html.escape
    parts = [f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>{e(ds.title)}</title>",
             f"<meta name='viewport' content='width=device-width,initial-scale=1'><style>{CSS}</style></head>",
             "<body><main class='viz-root'>",
             f"<h1>{e(ds.title)}</h1><p class='muted'>Data as of {e(ds.as_of)}. Amounts in reporting currency. "
             "Hover a value for its source note; <span class='flag'>*</span> = needs check. "
             "Shaded rows are the Bank X model, not reported results.</p>",
             "<h2>Findings</h2><ol>"]
    parts += [f"<li>{e(f)}</li>" for f in findings]
    parts.append("</ol><h2>Benchmarks</h2><div class='scroll'><table><tr><th>Company</th><th>Period</th>")
    parts += [f"<th>{e(label)}</th>" for _, label, _ in TABLE]
    parts.append("</tr>")
    for c in ds.companies:
        parts.append(f"<tr class='{'model' if c.is_model else ''}'><td>{e(c.name)}<br><span class='muted'>"
                     f"{e(c.country)} · {e(c.model)}</span></td><td>{e(c.period)}</td>")
        for key, _, source in TABLE:
            text = _fmt(ds, c, key, source)
            v = c.values.get(key) if source == "reported" else None
            tip = " | ".join(x for x in [v.note, v.source] if x) if v else "Computed from reported loans, deposits, equity and assets"
            flag = "<span class='flag'>*</span>" if v and v.needs_check else ""
            parts.append(f"<td title='{e(tip)}'>{e(text)}{flag}</td>")
        parts.append("</tr>")
    parts.append("</table></div>")
    for chart in charts:
        data = base64.b64encode(chart.read_bytes()).decode()
        parts.append(f"<p><img alt='{e(chart.stem)}' src='data:image/png;base64,{data}'></p>")
    parts.append("<h2>Sources</h2><ul>")
    seen = []
    for c in ds.companies:
        for v in c.values.values():
            if v.source.startswith("http") and v.source not in seen:
                seen.append(v.source)
                parts.append(f"<li>{e(c.name)}: <a href='{e(v.source)}' target='_blank' rel='noopener'>{e(v.source)}</a></li>")
    for cur, f in ds.fx.items():
        parts.append(f"<li>FX {e(cur)}: {f['eur_per_unit']} EUR ({e(str(f.get('date', '')))}) "
                     f"<a href='{e(f['source'])}' target='_blank' rel='noopener'>source</a></li>")
    parts.append("</ul></main></body></html>")
    path.write_text("".join(parts), encoding="utf-8")
