"""The three headline findings, computed from the dataset so they stay in sync with the numbers."""
from __future__ import annotations

from .data import Company, Dataset, derived


def _by_code(ds: Dataset) -> dict[str, Company]:
    return {c.code: c for c in ds.companies}


def _range(values: list[float]) -> str:
    return f"{min(values):.0%}-{max(values):.0%}"


def _eur_bn(ds: Dataset, c: Company, key: str) -> str:
    return f"EUR {ds.to_eur(c, key) / 1000:.2f}bn"


def findings(ds: Dataset) -> list[str]:
    c = _by_code(ds)
    reported = [x for x in ds.companies if not x.is_model]
    ltd = {x.code: derived(ds, x)["loan_to_deposit"] for x in reported}
    lenders = [x for x in reported if ltd[x.code] and ltd[x.code] >= 0.8]
    neobanks = [x for x in reported if ltd[x.code] and ltd[x.code] < 0.8 and (x.get("fee_share") or 0) < 0.5]
    rev = c["REV"]
    # Non-consumer lending inside the neobanks' loan books (mortgages, municipal loans)
    secured = [
        f"{x.name} " + " and ".join(f"{_eur_bn(ds, x, k)} {ds.metric(k).label.lower()}"
                                    for k in ("municipal_loans", "mortgages") if x.get(k))
        for x in neobanks if x.get("mortgages") or x.get("municipal_loans")
    ]

    first = (
        "In this sample, the banks that lend out most of their deposits earned higher returns than the deposit-heavy neobanks. "
        f"These deposit-funded lenders ({', '.join(x.name for x in lenders)}; "
        f"loans {_range([ltd[x.code] for x in lenders])} of deposits) earn ROE of {_range([x.get('roe') for x in lenders])} "
        f"at cost/income of {_range([x.get('cost_income') for x in lenders])}. "
        f"{', '.join(x.name for x in neobanks[:-1])} and {neobanks[-1].name} have loans of only "
        f"{_range([ltd[x.code] for x in neobanks])} of deposits, and much of that is not consumer lending "
        f"({'; '.join(secured)}). They earn ROE of {_range([x.get('roe') for x in neobanks])}. "
        f"{rev.name} does not fit this pattern: it has the highest ROE ({rev.get('roe'):.0%}) with loans of only "
        f"{ltd['REV']:.0%} of deposits, because net fees are {rev.get('fee_share'):.0%} of its net income. "
        f"Seven banks are too few to show cause and effect."
    )

    spread = sorted(
        [(x, x.get("loan_yield") - x.get("cost_of_risk")) for x in ds.companies
         if x.get("loan_yield") is not None and x.get("cost_of_risk") is not None and x.code != "BANKX_OPT"],
        key=lambda r: -r[1],
    )
    tf, big = c["TFB"], c["BIG"]
    second = (
        "Cost of risk reflects what a bank lends and how it prices it. "
        f"{tf.name} loses {tf.get('cost_of_risk'):.1%} of its loans a year and still earns {tf.get('roe'):.0%} ROE, "
        f"because its loans yield about {tf.get('loan_yield'):.0%}. {big.name} loses only {big.get('cost_of_risk'):.1%} "
        f"and earns {big.get('loan_yield'):.1%} on loans, mainly because most of its book is business and home loans, "
        f"largely secured on real estate; unsecured consumer loans are only {big.get('consumer_loan_share'):.0%} of its portfolio. "
        "Loan yield minus cost of risk: "
        + ", ".join(f"{x.name} {s:.1%}" for x, s in spread)
        + ". This spread is approximate (the loan bases differ slightly between banks) and is before funding cost."
    )

    bx, inb = c["BANKX"], c["INB"]
    opt = c["BANKX_OPT"]
    third = (
        "How Bank X year 5 compares to Inbank today: "
        f"a loan book of EUR {bx.get('loans'):.0f}m is {bx.get('loans') / inb.get('loans'):.0%} of Inbank's "
        f"EUR {inb.get('loans') / 1000:.2f}bn. Loan pricing is the same by assumption: Bank X's loan yield of "
        f"{bx.get('loan_yield'):.1%} is calibrated to Inbank's {inb.get('loan_yield'):.1%}. "
        f"ROE is {bx.get('roe'):.1%}, against {inb.get('roe_core'):.1%} for Inbank's core business "
        f"({inb.get('roe'):.1%} reported, which includes a one-off gain from the reassessment of Polish tax assets). "
        f"The gap has two causes: cost of risk is higher "
        f"({bx.get('cost_of_risk'):.2%} vs {inb.get('cost_of_risk'):.2%}, mostly the IFRS 9 loss allowance building up on a fast-growing book), "
        f"and the bank is still sub-scale (cost/income {bx.get('cost_income'):.0%} vs {inb.get('cost_income'):.0%}). "
        f"The optimistic case (ROE {opt.get('roe'):.0%}, cost/income {opt.get('cost_income'):.0%}) would need "
        f"efficiency between {big.name} ({big.get('cost_income'):.0%}) and {tf.name} ({tf.get('cost_income'):.0%})."
    )
    return [first, second, third]
