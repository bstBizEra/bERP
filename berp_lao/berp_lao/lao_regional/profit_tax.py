# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Lao profit tax (CIT) — roadmap 1b.4.

WHAT USING THIS SOFTWARE DOES TO A LAO MICROENTERPRISE'S TAX POSITION
    Lao PDR runs two regimes side by side, and which one a business falls into
    turns on something bERP itself changes.

    The **lump-sum tax** (ອາກອນເໝົາ) is assessed on *turnover*, at low
    sector-dependent rates, and is available to small businesses **that do not
    maintain Lao accounting books**. Keeping proper books is the disqualifying
    condition, not a requirement.

    A business that adopts this system keeps proper books. It therefore leaves
    the lump-sum regime and is assessed on **net profit** — at 5% if it is a
    microenterprise under Law on Income Tax No. 88/NA, and 20% otherwise.

    That is a real consequence of adopting the product, in both directions: the
    profit base may be far kinder than a turnover base for a thin-margin trader,
    and far worse for a profitable one. It is stated here because a Lao
    microenterprise owner may reasonably expect to keep paying the turnover tax
    they have always paid, and nothing else in the system would tell them
    otherwise. **It is a matter for their tax adviser, not for this module.**

WHAT THIS MODULE DECIDES, AND WHAT IT REFUSES TO
    It decides: given a regime and a date, what rate was in force, and what the
    net profit for the period was.

    It refuses to decide whether a company *qualifies* as a microenterprise.
    The qualifying turnover threshold under 88/NA is not established in the
    sources available — VDB Loi's alert on the new law states the 5%-on-net-
    profit rate and says explicitly that the thresholds are absent from it. So
    the regime is a field a human sets on the Company, and this module applies
    the rate for whatever they set. Guessing a threshold and enforcing it would
    be inventing statute.

EVERY NUMBER HERE IS AN ESTIMATE
    ``check()`` returns the reasons an estimate should not be relied on, and the
    list is never empty by construction — see :data:`ALWAYS_TRUE`. A profit tax
    figure produced by accounting software is an input to a return, not a return.
"""

from __future__ import annotations

import dataclasses
import json
import os
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate

from berp_lao.lao_regional.country import is_lao_company

SCHEMA_VERSION = "berp_lao.profit_tax_estimate.v1"

STATUTE = "Law on Income Tax No. 88/NA"

REGIME_FIELD = "lao_profit_tax_regime"
STANDARD = "Standard"
MICRO = "Micro-enterprise"

#: Said on every estimate, whatever else is or is not wrong with it. A caveat
#: that only appears sometimes is read as "fine the rest of the time".
ALWAYS_TRUE = (
	"This is an estimate from the ledger, not a filed return. A Lao tax adviser "
	"must confirm the regime, the deductibility of the expenses behind it, and any "
	"incentive or special rate before it is used for anything."
)


def _data() -> dict:
	path = os.path.join(os.path.dirname(__file__), "data", "lao_profit_tax.json")
	with open(path, encoding="utf-8") as handle:
		return json.load(handle)


def regimes() -> list[str]:
	return [row["regime"] for row in _data().get("regimes", [])]


def rate_in_force(regime: str, on_date) -> float | None:
	"""The rate for `regime` on `on_date`, or None when none was in force.

	None is a real answer, not a zero. Microenterprises had no uniform rate before
	1 July 2026 — they were taxed by activity — so an estimate for an earlier
	period must say it cannot be made rather than quietly assess at 0%.
	"""
	on_date = getdate(on_date)
	for row in _data().get("regimes", []):
		if row["regime"] != regime:
			continue
		for rate in row.get("rates", []):
			if getdate(rate["from_date"]) <= on_date <= getdate(rate["to_date"]):
				return flt(rate["rate"])
	return None


def company_regime(company: str) -> str:
	"""What the company is flagged as. Defaults to Standard, never to the cheaper one."""
	value = frappe.get_cached_value("Company", company, REGIME_FIELD)
	return value if value in regimes() else STANDARD


def net_profit(company: str, from_date, to_date) -> dict[str, float]:
	"""Income less expense over the period, straight from the ledger.

	Cross-checked against ERPNext's own Profit and Loss Statement in
	``tests/test_profit_tax.py`` — two instruments, one question. They agreed on
	the fixture company when this was written, and the test exists so they keep
	agreeing.
	"""
	rows = frappe.db.sql(
		"""
		SELECT a.root_type AS root_type,
		       SUM(gle.credit) AS credit,
		       SUM(gle.debit)  AS debit
		FROM `tabGL Entry` gle
		JOIN `tabAccount` a ON a.name = gle.account
		WHERE gle.company = %(company)s
		  AND gle.is_cancelled = 0
		  AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
		  AND a.root_type IN ('Income', 'Expense')
		GROUP BY a.root_type
		""",
		{"company": company, "from_date": getdate(from_date), "to_date": getdate(to_date)},
		as_dict=True,
	)

	income = expense = 0.0
	for row in rows:
		if row.root_type == "Income":
			income = flt(row.credit) - flt(row.debit)  # income carries a credit balance
		else:
			expense = flt(row.debit) - flt(row.credit)  # expense carries a debit balance

	return {
		"income": flt(income, 2),
		"expense": flt(expense, 2),
		"net_profit": flt(income - expense, 2),
	}


@dataclasses.dataclass(frozen=True)
class ProfitTaxEstimate:
	"""One company's profit tax position for one period, as far as the ledger knows."""

	schema: str
	statute: str

	company: str
	regime: str
	currency: str

	period_from: str
	period_to: str

	income: float
	expense: float
	net_profit: float

	rate: float | None
	tax: float | None

	def as_dict(self) -> dict[str, Any]:
		return dataclasses.asdict(self)

	def check(self) -> list[str]:
		"""Reasons not to rely on this. Never empty — see ALWAYS_TRUE."""
		problems = [_(ALWAYS_TRUE)]

		if self.rate is None:
			problems.append(
				_(
					"No {0} rate was in force on {1}, so no tax has been estimated. Before "
					"1 July 2026 microenterprises were taxed by activity rather than at a "
					"uniform rate."
				).format(self.regime, self.period_to)
			)

		if getdate(self.period_from) > getdate(self.period_to):
			problems.append(_("Period start is after period end."))

		if self.net_profit < 0:
			problems.append(
				_(
					"The period is a loss of {0}, so no profit tax arises on it. Whether the "
					"loss can be carried forward is a question for an adviser."
				).format(abs(self.net_profit))
			)

		if self.regime == MICRO:
			problems.append(
				_(
					"Assessed as a microenterprise. This app does not test that qualification — "
					"the threshold under {0} is not established in the sources it was built "
					"from, so the regime is whatever the Company record says."
				).format(self.statute)
			)

		if not self.income and not self.expense:
			problems.append(_("Nothing was posted to income or expense in this period."))

		return problems


def build_profit_tax_estimate(company: str, from_date, to_date) -> ProfitTaxEstimate:
	if not is_lao_company(company):
		frappe.throw(_("{0} is not registered in Lao PDR, so Lao profit tax does not apply.").format(company))

	totals = net_profit(company, from_date, to_date)
	regime = company_regime(company)
	# The rate in force at the END of the period: a return is assessed on the law
	# as it stands at the period end, and a period that straddles a rate change is
	# a question for an adviser rather than an arithmetic mean.
	rate = rate_in_force(regime, to_date)
	profit = totals["net_profit"]

	tax = None
	if rate is not None and profit > 0:
		tax = flt(profit * rate / 100.0, 2)
	elif rate is not None:
		tax = 0.0

	return ProfitTaxEstimate(
		schema=SCHEMA_VERSION,
		statute=STATUTE,
		company=company,
		regime=regime,
		currency=frappe.get_cached_value("Company", company, "default_currency"),
		period_from=str(getdate(from_date)),
		period_to=str(getdate(to_date)),
		income=totals["income"],
		expense=totals["expense"],
		net_profit=profit,
		rate=rate,
		tax=tax,
	)


@frappe.whitelist()
def profit_tax_estimate(company: str, from_date: str, to_date: str) -> dict:
	"""Estimate, plus every reason not to rely on it."""
	frappe.only_for(("System Manager", "Accounts Manager"))

	estimate = build_profit_tax_estimate(company, from_date, to_date)
	return {"estimate": estimate.as_dict(), "problems": estimate.check()}
