"""Build the benchmark table, charts and report.

Usage:
    python run.py                                  # uses data/benchmarks.yaml, writes to output/
    python run.py --data my.yaml --out results
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from benchmarks.data import load, validate
from benchmarks.findings import findings
from benchmarks.report import readme_table, write_charts, write_html, write_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark digital banks and deposit-funded lenders against Bank X")
    parser.add_argument("--data", default="data/benchmarks.yaml", help="Path to the benchmarks YAML")
    parser.add_argument("--out", default="output", help="Output folder")
    args = parser.parse_args()

    ds = load(args.data)
    errors = validate(ds)
    if errors:
        sys.exit("Dataset problems:\n  " + "\n  ".join(errors))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    found = findings(ds)
    charts = write_charts(ds, out)
    write_markdown(ds, found, out / "summary.md")
    write_html(ds, found, charts, out / "report.html")
    (out / "readme_table.md").write_text(readme_table(ds), encoding="utf-8")

    print(f"{'Company':<22}{'Period':<10}{'ROE':>8}{'C/I':>8}{'CoR':>8}{'Assets EUR bn':>15}")
    for c in ds.companies:
        def pct(k):
            v = c.get(k)
            return f"{v:.1%}" if v is not None else "n/a"
        assets = ds.to_eur(c, "total_assets")
        print(f"{c.name:<22}{c.period:<10}{pct('roe'):>8}{pct('cost_income'):>8}{pct('cost_of_risk'):>8}"
              f"{assets / 1000 if assets else float('nan'):>15.2f}")
    print()
    for i, f in enumerate(found, 1):
        print(f"{i}. {f}")
    flagged = sum(v.needs_check for c in ds.companies for v in c.values.values())
    print(f"\n{flagged} values flagged needs_check")
    print(f"Outputs written to {out.resolve()}")


if __name__ == "__main__":
    main()
