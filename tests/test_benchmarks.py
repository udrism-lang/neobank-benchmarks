"""Tests: the dataset is well-formed and internally consistent; derived figures are computed correctly."""
from dataclasses import replace
from pathlib import Path

import pytest

from benchmarks.data import AMOUNT, RATIO, derived, load, validate
from benchmarks.findings import findings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ds():
    return load(ROOT / "data" / "benchmarks.yaml")


def test_dataset_is_valid(ds):
    assert validate(ds) == []


def test_every_value_has_source_or_needs_check(ds):
    for c in ds.companies:
        for k, v in c.values.items():
            if v.value is not None:
                assert v.source or v.needs_check, f"{c.code}/{k}"


def test_ratios_are_decimals(ds):
    for c in ds.companies:
        for m in ds.metrics:
            v = c.get(m.key)
            if m.kind == RATIO and v is not None:
                assert -2 <= v <= 2, f"{c.code}/{m.key} = {v}"


def test_balance_sheet_sizes_are_consistent(ds):
    """Loans and equity cannot exceed total assets."""
    for c in ds.companies:
        assets = c.get("total_assets")
        for k in ("loans", "equity"):
            if assets and c.get(k):
                assert c.get(k) <= assets, f"{c.code}: {k} > total assets"


# Banks whose stated ROE uses a different basis than net profit / average total equity.
# TF Bank: profit to shareholders / average equity excluding its SEK 250m Tier 1 instrument
# (annual report 2025 p13, p26-27): 641.2 / ((3,038.0 + 2,522.7) / 2) = 23.1%. See the yaml note on TFB/roe.
ROE_STATED_BASIS = {"TFB": 641.2 / ((3038.0 + 2522.7) / 2)}


def test_roe_matches_profit_over_average_equity(ds):
    """ROE is within 1 percentage point of net profit / average equity (opening and closing equity)."""
    checked = 0
    for c in ds.companies:
        roe, profit = c.get("roe"), c.get("net_profit")
        equity, prev = c.get("equity"), c.get("equity_prev")
        if c.is_model or roe is None or profit is None:
            continue
        assert equity and prev, f"{c.code}: ROE needs equity and equity_prev to be checked"
        expected = ROE_STATED_BASIS.get(c.code, profit / ((equity + prev) / 2))
        assert abs(roe - expected) < 0.01, f"{c.code}: ROE {roe:.1%} vs computed {expected:.1%}"
        checked += 1
    assert checked >= 7


def test_tf_bank_roe_on_total_equity_is_lower(ds):
    """The exception is real: on total equity TF Bank's ROE is about 1 point lower than stated."""
    tf = next(c for c in ds.companies if c.code == "TFB")
    on_total = tf.get("net_profit") / ((tf.get("equity") + tf.get("equity_prev")) / 2)
    assert 0.005 < tf.get("roe") - on_total < 0.02


def test_fee_share_is_net_fee_over_total_income(ds):
    """Every bank's fee share uses one definition (net fee income / total net income); the note must show net fees."""
    for c in ds.companies:
        v = c.values.get("fee_share")
        if c.is_model or not v or v.value is None:
            continue
        assert "net fee" in v.note.lower(), f"{c.code}: fee share note does not show net fee income"


def test_fx_conversion(ds):
    for c in ds.companies:
        assets = c.get("total_assets")
        if assets is None:
            continue
        eur = ds.to_eur(c, "total_assets")
        if c.currency == "EUR":
            assert eur == assets
        else:
            assert eur == pytest.approx(assets * ds.fx[c.currency]["eur_per_unit"])


def test_ratios_not_converted(ds):
    gbp = next(c for c in ds.companies if c.currency != "EUR")
    assert ds.to_eur(gbp, "roe") == gbp.get("roe")


def test_derived_loan_to_deposit(ds):
    for c in ds.companies:
        d = derived(ds, c)
        if c.get("loans") and c.get("deposits"):
            assert d["loan_to_deposit"] == pytest.approx(c.get("loans") / c.get("deposits"))


def test_bank_x_is_marked_as_model(ds):
    models = [c for c in ds.companies if c.is_model]
    assert models and all("Bank X" in c.name for c in models)


def test_validate_catches_percentages_and_missing_sources(ds):
    c = ds.companies[0]
    bad_values = {**c.values, "roe": replace(c.values["roe"], value=12.3, source="", needs_check=False)}
    bad = replace(ds, companies=[replace(c, values=bad_values)] + ds.companies[1:])
    errors = validate(bad)
    assert any("percentage" in e for e in errors)
    assert any("no source" in e for e in errors)


def test_findings_present(ds):
    f = findings(ds)
    assert len(f) == 3
    assert f[-1].startswith("How Bank X year 5 compares to Inbank today")


def test_amount_metrics_declared(ds):
    assert {m.key for m in ds.metrics if m.kind == AMOUNT} >= {"loans", "deposits", "total_assets", "equity"}
