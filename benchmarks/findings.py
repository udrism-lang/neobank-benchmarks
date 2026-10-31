"""The three headline findings, computed from the dataset so they stay in sync with the numbers."""
from __future__ import annotations

from .data import Company, Dataset, derived


def _by_code(ds: Dataset) -> dict[str, Company]:
    return {c.code: c for c in ds.companies}


def _range(values: list[float]) -> str:
    return f"{min(values):.0%}-{max(values):.0%}"


def findings(ds: Dataset) -> list[str]:
    c = _by_code(ds)
    reported = [x for x in ds.companies if not x.is_model]
    ltd = {x.code: derived(ds, x)["loan_to_deposit"] for x in reported}
    lenders = [x for x in reported if ltd[x.code] and ltd[x.code] >= 0.8]
    neobanks = [x for x in reported if ltd[x.code] and ltd[x.code] < 0.8 and (x.get("fee_share") or 0) < 0.5]
    rev = c["REV"]

    first = (
        "Lending margin, not app scale, drives returns for deposit-funded banks. "
        f"The consumer lenders that lend out most of their deposits ({', '.join(x.name for x in lenders)}; "
        f"loans {_range([ltd[x.code] for x in lenders])} of deposits) earn ROE of {_range([x.get('roe') for x in lenders])} "
        f"at cost/income of {_range([x.get('cost_income') for x in lenders])}. "
        f"The deposit-heavy neobanks ({', '.join(x.name for x in neobanks)}) lend out only "
        f"{_range([ltd[x.code] for x in neobanks])} of deposits and earn {_range([x.get('roe') for x in neobanks])}. "
        f"{rev.name} is the exception: {rev.get('fee_share'):.0%} of revenue from fees and ROE of about {rev.get('roe'):.0%}, "
        f"with loans only {ltd['REV']:.0%} of deposits."
    )

    spread = sorted(
        [(x, x.get("loan_yield") - x.get("cost_of_risk")) for x in ds.companies
         if x.get("loan_yield") is not None and x.get("cost_of_risk") is not None and x.code != "BANKX_OPT"],
        key=lambda r: -r[1],
    )
    tf, big = c["TFB"], c["BIG"]
    second = (
        "Cost of risk is a pricing choice, not a verdict. "
        f"{tf.name} loses {tf.get('cost_of_risk'):.1%} of its loans a year and still earns {tf.get('roe'):.0%} ROE "
        f"because it charges about {tf.get('loan_yield'):.0%}; {big.name} loses only {big.get('cost_of_risk'):.1%} "
        f"but earns {big.get('loan_yield'):.1%} on loans. Loan yield minus cost of risk: "
        + ", ".join(f"{x.name} {s:.1%}" for x, s in spread) + "."
    )

    bx, inb = c["BANKX"], c["INB"]
    opt = c["BANKX_OPT"]
    third = (
        "How Bank X year 5 compares to Inbank today: "
        f"a loan book of EUR {bx.get('loans'):.0f}m is {bx.get('loans') / inb.get('loans'):.0%} of Inbank's "
        f"EUR {inb.get('loans') / 1000:.2f}bn, with the same pricing (loan yield {bx.get('loan_yield'):.1%} vs "
        f"{inb.get('loan_yield'):.1%}). ROE is {bx.get('roe'):.1%} vs {inb.get('roe'):.1%} because cost of risk is higher "
        f"({bx.get('cost_of_risk'):.2%} vs {inb.get('cost_of_risk'):.2%}, mostly day-one IFRS 9 provisions on a fast-growing book) "
        f"and the bank is still sub-scale (cost/income {bx.get('cost_income'):.0%} vs {inb.get('cost_income'):.0%}). "
        f"The optimistic case (ROE {opt.get('roe'):.0%}, cost/income {opt.get('cost_income'):.0%}) would need "
        f"efficiency between Bigbank ({big.get('cost_income'):.0%}) and TF Bank ({tf.get('cost_income'):.0%})."
    )
    return [first, second, third]
