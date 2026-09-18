# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Lao profit tax — mirrors `lao_regional/profit_tax.py`. Roadmap 1b.4.

`test_net_profit_agrees_with_erpnexts_own_profit_and_loss` is the one that earns
its place. This module computes net profit straight from the ledger rather than
running ERPNext's Profit and Loss Statement, because the report is built for
presentation — hierarchies, period columns, accumulated values — and none of that
is wanted here. That is a defensible shortcut only while the two agree, so the
agreement is asserted rather than assumed. Two instruments, one question; if they
ever diverge, this app is the one that is wrong.

`test_a_microenterprise_period_before_july_2026_is_refused_not_zero_rated` is the
three-state discipline this repository already applies to fonts, applied to a
rate: *no rate in force* is not *a rate of zero*. Before 1 July 2026
microenterprises were taxed by activity, so an estimate for an earlier period has
to say it cannot be made.
"""

import itertools

import frappe
from frappe.utils import add_days, flt, getdate

from berp_lao.lao_regional.profit_tax import (
	ALWAYS_TRUE,
	MICRO,
	REGIME_FIELD,
	STANDARD,
	build_profit_tax_estimate,
	company_regime,
	net_profit,
	rate_in_force,
	regimes,
)
from berp_lao.tests.fixtures import COMPANY, LaoVatReturnFixture


class TestLaoProfitTaxRates(LaoVatReturnFixture):
	"""The dated rate table, asked directly."""

	def test_the_standard_rate_fell_to_twenty_percent_on_1_july_2026(self):
		"""Law 88/NA cut it from 24%. A period before the change keeps the old rate."""
		self.assertEqual(rate_in_force(STANDARD, "2026-06-30"), 24.0)
		self.assertEqual(rate_in_force(STANDARD, "2026-07-01"), 20.0)
		self.assertEqual(rate_in_force(STANDARD, "2026-12-31"), 20.0)

	def test_the_microenterprise_rate_is_five_percent_from_1_july_2026(self):
		self.assertEqual(rate_in_force(MICRO, "2026-07-01"), 5.0)
		self.assertEqual(rate_in_force(MICRO, "2026-12-31"), 5.0)

	def test_no_microenterprise_rate_existed_before_that(self):
		"""None, not 0.0. They were taxed by activity, not at a uniform rate."""
		self.assertIsNone(rate_in_force(MICRO, "2026-06-30"))
		self.assertIsNone(rate_in_force(MICRO, "2024-01-01"))

	def test_no_rate_window_overlaps_another_in_the_same_regime(self):
		"""Overlapping rows would make the rate depend on row order."""
		from berp_lao.lao_regional.profit_tax import _data

		for regime in _data()["regimes"]:
			rows = sorted(regime["rates"], key=lambda r: getdate(r["from_date"]))
			for earlier, later in itertools.pairwise(rows):
				with self.subTest(regime=regime["regime"]):
					self.assertLess(
						getdate(earlier["to_date"]),
						getdate(later["from_date"]),
						f"{regime['regime']} has overlapping rate windows",
					)

	def test_the_lump_sum_regime_is_not_offered(self):
		"""It is available only to businesses that keep no books. Ours keep books.

		Offering it as a choice would invite a tenant to select a regime that
		running this software disqualifies them from.
		"""
		self.assertNotIn("Lump-sum", regimes())
		self.assertEqual(sorted(regimes()), sorted([STANDARD, MICRO]))


class TestLaoNetProfit(LaoVatReturnFixture):
	def _period(self):
		return self.posting_date, add_days(self.posting_date, 27)

	def test_net_profit_agrees_with_erpnexts_own_profit_and_loss(self):
		"""Two instruments, one question. If they diverge, we are the wrong one."""
		fy = frappe.get_all(
			"Fiscal Year",
			filters={"name": str(getdate(self.posting_date).year)},
			fields=["year_start_date", "year_end_date"],
		)
		if not fy:
			self.skipTest("no fiscal year covering the fixture period")
		start, end = fy[0].year_start_date, fy[0].year_end_date

		ours = net_profit(COMPANY, start, end)["net_profit"]

		from erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement import (
			execute,
		)

		_columns, data = execute(
			frappe._dict(
				{
					"company": COMPANY,
					"filter_based_on": "Date Range",
					"period_start_date": start,
					"period_end_date": end,
					"from_date": start,
					"to_date": end,
					"periodicity": "Yearly",
					"accumulated_values": 1,
				}
			)
		)[:2]
		rows = [r for r in data if r and "Profit" in str(r.get("account") or "")]
		self.assertTrue(rows, "ERPNext's P&L produced no profit row to compare against")
		self.assertAlmostEqual(
			flt(ours, 2),
			flt(rows[0].get("total"), 2),
			places=1,
			msg="the ledger aggregation disagrees with ERPNext's Profit and Loss Statement",
		)

	def test_income_and_expense_are_reported_the_way_a_reader_expects(self):
		"""Both positive, and the profit is the difference — not a signed jumble."""
		totals = net_profit(COMPANY, *self._period())
		self.assertGreaterEqual(totals["income"], 0)
		self.assertGreaterEqual(totals["expense"], 0)
		self.assertAlmostEqual(totals["net_profit"], flt(totals["income"] - totals["expense"], 2), places=1)

	def test_a_period_with_nothing_posted_is_zero_not_an_error(self):
		totals = net_profit(COMPANY, add_days(self.posting_date, 900), add_days(self.posting_date, 930))
		self.assertEqual(totals, {"income": 0.0, "expense": 0.0, "net_profit": 0.0})


class TestLaoProfitTaxEstimate(LaoVatReturnFixture):
	def tearDown(self):
		frappe.db.set_value("Company", COMPANY, REGIME_FIELD, STANDARD)
		frappe.clear_document_cache("Company", COMPANY)
		super().tearDown()

	def _set(self, regime):
		frappe.db.set_value("Company", COMPANY, REGIME_FIELD, regime)
		frappe.clear_document_cache("Company", COMPANY)

	def _estimate(self, to_date=None):
		return build_profit_tax_estimate(
			COMPANY, self.posting_date, to_date or add_days(self.posting_date, 27)
		)

	def test_the_regime_defaults_to_standard_never_to_the_cheaper_one(self):
		"""An unset field must not silently reduce somebody's tax."""
		frappe.db.set_value("Company", COMPANY, REGIME_FIELD, None)
		frappe.clear_document_cache("Company", COMPANY)
		self.assertEqual(company_regime(COMPANY), STANDARD)

		frappe.db.set_value("Company", COMPANY, REGIME_FIELD, "Something Else")
		frappe.clear_document_cache("Company", COMPANY)
		self.assertEqual(company_regime(COMPANY), STANDARD, "an unrecognised value must not apply")

	def test_a_standard_company_is_estimated_at_twenty_percent(self):
		self._set(STANDARD)
		est = self._estimate()
		self.assertEqual(est.rate, 20.0)
		if est.net_profit > 0:
			self.assertAlmostEqual(est.tax, flt(est.net_profit * 0.20, 2), places=1)

	def test_a_microenterprise_is_estimated_at_five_percent(self):
		self._set(MICRO)
		est = self._estimate()
		self.assertEqual(est.rate, 5.0)
		if est.net_profit > 0:
			self.assertAlmostEqual(est.tax, flt(est.net_profit * 0.05, 2), places=1)

	def test_the_microenterprise_saving_is_the_point_of_the_flag(self):
		"""Same ledger, two regimes: the flag has to change the number."""
		self._set(STANDARD)
		standard = self._estimate()
		self._set(MICRO)
		micro = self._estimate()

		self.assertEqual(standard.net_profit, micro.net_profit)
		if standard.net_profit > 0:
			self.assertLess(micro.tax, standard.tax)
			self.assertAlmostEqual(micro.tax, flt(standard.tax / 4, 2), places=0)

	def test_a_microenterprise_period_before_july_2026_is_refused_not_zero_rated(self):
		"""No rate in force is not a rate of zero — the three-state rule, again."""
		self._set(MICRO)
		est = build_profit_tax_estimate(COMPANY, "2026-01-01", "2026-06-30")
		self.assertIsNone(est.rate)
		self.assertIsNone(est.tax, "a missing rate must not resolve to no tax")
		self.assertTrue(
			any("No Micro-enterprise rate was in force" in p for p in est.check()),
			est.check(),
		)

	def test_a_period_ending_before_the_cut_uses_the_old_standard_rate(self):
		"""24% until 1 July 2026. A period is assessed on the law at its end."""
		self._set(STANDARD)
		est = build_profit_tax_estimate(COMPANY, "2026-01-01", "2026-06-30")
		self.assertEqual(est.rate, 24.0)

	def test_every_estimate_carries_the_caveat(self):
		"""A caveat that appears only sometimes is read as 'fine the rest of the time'."""
		for regime in (STANDARD, MICRO):
			with self.subTest(regime=regime):
				self._set(regime)
				self.assertIn(ALWAYS_TRUE, self._estimate().check())

	def test_a_microenterprise_estimate_says_the_qualification_is_not_tested(self):
		self._set(MICRO)
		self.assertTrue(any("does not test that qualification" in p for p in self._estimate().check()))

	def test_a_loss_produces_no_tax_and_says_so(self):
		import dataclasses

		est = self._estimate()
		loss = dataclasses.replace(est, net_profit=-500_000.0, tax=0.0)
		self.assertTrue(any("is a loss of" in p for p in loss.check()), loss.check())

	def test_an_inverted_period_is_reported(self):
		import dataclasses

		est = self._estimate()
		flipped = dataclasses.replace(est, period_from=est.period_to, period_to=est.period_from)
		self.assertTrue(any("after period end" in p for p in flipped.check()))

	def test_a_non_lao_company_is_refused(self):
		from unittest.mock import patch

		import berp_lao.lao_regional.profit_tax as mod

		with patch.object(mod, "is_lao_company", return_value=False):
			with self.assertRaises(frappe.ValidationError):
				self._estimate()

	def test_the_whitelisted_call_returns_the_estimate_and_its_problems(self):
		from berp_lao.lao_regional.profit_tax import profit_tax_estimate

		payload = profit_tax_estimate(COMPANY, self.posting_date, add_days(self.posting_date, 27))
		self.assertIn("estimate", payload)
		self.assertIn("problems", payload)
		self.assertTrue(payload["problems"], "an estimate with no caveats is a bug")
		for key in ("regime", "rate", "net_profit", "tax", "statute"):
			self.assertIn(key, payload["estimate"])
