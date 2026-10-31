"""Load and validate the benchmark dataset; convert amounts to EUR and derive ratios."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

AMOUNT, RATIO, COUNT = "amount", "ratio", "count"


@dataclass(frozen=True)
class Value:
    value: float | None
    source: str
    note: str
    needs_check: bool


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    kind: str  # amount (millions of reporting currency), ratio (decimal), count (millions)
    description: str


@dataclass
class Company:
    code: str
    name: str
    country: str
    model: str
    period: str
    currency: str
    is_model: bool  # True for Bank X (projection, not reported results)
    values: dict[str, Value] = field(default_factory=dict)

    def get(self, key: str) -> float | None:
        v = self.values.get(key)
        return v.value if v else None


@dataclass
class Dataset:
    title: str
    as_of: str
    fx: dict[str, dict]  # currency -> {eur_per_unit, source, date}
    metrics: list[Metric]
    companies: list[Company]

    def metric(self, key: str) -> Metric:
        return next(m for m in self.metrics if m.key == key)

    def to_eur(self, company: Company, key: str) -> float | None:
        """Amount in EUR millions; ratios and counts are returned unchanged."""
        v = company.get(key)
        if v is None or self.metric(key).kind != AMOUNT or company.currency == "EUR":
            return v
        return v * self.fx[company.currency]["eur_per_unit"]


def load(path: str | Path) -> Dataset:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    metrics = [Metric(k, m["label"], m["kind"], m["description"]) for k, m in raw["metrics"].items()]
    companies = []
    for code, c in raw["companies"].items():
        values = {
            k: Value(v.get("value"), v.get("source", ""), v.get("note", ""), bool(v.get("needs_check", False)))
            for k, v in (c.get("values") or {}).items()
        }
        companies.append(Company(code, c["name"], c["country"], c["model"], str(c["period"]), c["currency"],
                                 bool(c.get("is_model", False)), values))
    return Dataset(raw["title"], str(raw["as_of"]), raw.get("fx") or {}, metrics, companies)


def validate(ds: Dataset) -> list[str]:
    """Return a list of problems; empty means the dataset is usable."""
    errors = []
    keys = {m.key for m in ds.metrics}
    for c in ds.companies:
        if c.currency != "EUR" and c.currency not in ds.fx:
            errors.append(f"{c.code}: no FX rate for {c.currency}")
        for k, v in c.values.items():
            where = f"{c.code}/{k}"
            if k not in keys:
                errors.append(f"{where}: unknown metric")
                continue
            if v.value is None:
                if not v.note:
                    errors.append(f"{where}: missing value needs a note explaining why")
                continue
            if not v.source and not v.needs_check:
                errors.append(f"{where}: no source and not flagged needs_check")
            kind = ds.metric(k).kind
            if kind == RATIO and not -2 <= v.value <= 2:
                errors.append(f"{where}: ratio {v.value} looks like a percentage, use decimals")
            if kind in (AMOUNT, COUNT) and v.value < 0 and k != "net_profit":
                errors.append(f"{where}: negative {kind}")
    for cur, f in ds.fx.items():
        if not f.get("source") or not f.get("eur_per_unit"):
            errors.append(f"fx/{cur}: rate and source required")
    return errors


def derived(ds: Dataset, c: Company) -> dict[str, float | None]:
    """Ratios computed from reported amounts, so every company is measured the same way."""
    loans, deposits = c.get("loans"), c.get("deposits")
    equity, assets = c.get("equity"), c.get("total_assets")
    return {
        "loan_to_deposit": loans / deposits if loans and deposits else None,
        "equity_to_assets": equity / assets if equity and assets else None,
        "assets_eur_bn": (ds.to_eur(c, "total_assets") or 0) / 1000 or None,
    }
