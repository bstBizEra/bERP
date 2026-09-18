# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Lao rules on the Purchase Invoice — mirrors `lao_regional/rules/purchase_invoice.py`.

The input-VAT window is the subject of most of these. Lao input VAT is claimable
only within three months of the date incurred, measured from the supplier's
`bill_date` rather than the posting date — a purchase booked late is precisely
the case that misses it, and ERPNext posts the claim without complaint.
"""

import frappe
from frappe.utils import add_days, add_months, flt, getdate, nowdate

from berp_lao.tests.fixtures import (
	COMPANY,
	DOMESTIC_A,
	DOMESTIC_B,
	EXPECTED_INPUT_VAT,
	EXPECTED_OUTPUT_VAT,
	EXPORT,
	FREIGHT,
	ITEM,
	PRICE_LIST_BUYING,
	PURCHASE,
	SUPPLIER,
	LaoVatReturnFixture,
	account_by_number,
	load_tax_data,
)


class TestLaoInputVatWindow(LaoVatReturnFixture):
	"""Input VAT is claimable only within three months of the date incurred."""

	def _purchase(self, bill_date, posting_date, with_vat=True):
		taxes = []
		if with_vat:
			taxes = [
				{
					"charge_type": "On Net Total",
					"account_head": self.input_vat,
					"rate": 10,
					"add_deduct_tax": "Add",
					"category": "Total",
					"description": "Input VAT 10%",
					"cost_center": self.cost_center,
				}
			]
		return frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"company": COMPANY,
				"supplier": SUPPLIER,
				"currency": "LAK",
				"conversion_rate": 1,
				"buying_price_list": PRICE_LIST_BUYING,
				"price_list_currency": "LAK",
				"plc_conversion_rate": 1,
				"set_posting_time": 1,
				"posting_date": posting_date,
				"bill_date": bill_date,
				"due_date": add_days(posting_date, 30),
				"credit_to": self.payable,
				"items": [
					{
						"item_code": ITEM,
						"qty": 1,
						"rate": 100000,
						"expense_account": self.expense,
						"cost_center": self.cost_center,
					}
				],
				"taxes": taxes,
			}
		)

	def test_claim_inside_the_window_is_quiet(self):
		frappe.clear_messages()
		self._purchase(add_days(self.posting_date, -60), self.posting_date).insert()
		messages = " ".join(str(m) for m in frappe.get_message_log())
		self.assertNotIn("Input VAT Window", messages)

	def test_claim_past_the_window_warns(self):
		frappe.clear_messages()
		self._purchase(add_days(self.posting_date, -120), self.posting_date).insert()
		messages = " ".join(str(m) for m in frappe.get_message_log())
		self.assertIn("Input VAT Window", messages)

	def test_the_window_runs_from_the_bill_date_not_the_posting_date(self):
		"""A purchase booked late is exactly the case that misses the window."""
		frappe.clear_messages()
		# Same posting date as the quiet case above, but the supplier invoiced long
		# before. Measuring from posting_date would find nothing wrong.
		self._purchase(add_months(self.posting_date, -5), self.posting_date).insert()
		messages = " ".join(str(m) for m in frappe.get_message_log())
		self.assertIn("Input VAT Window", messages)

	def test_an_invoice_with_no_input_vat_is_never_warned_about(self):
		frappe.clear_messages()
		self._purchase(add_days(self.posting_date, -200), self.posting_date, with_vat=False).insert()
		messages = " ".join(str(m) for m in frappe.get_message_log())
		self.assertNotIn("Input VAT Window", messages)

	def test_no_bill_date_means_no_claim_to_judge(self):
		frappe.clear_messages()
		self._purchase(None, self.posting_date).insert()
		messages = " ".join(str(m) for m in frappe.get_message_log())
		self.assertNotIn("Input VAT Window", messages)


class TestLaoWithholdingTax(LaoVatReturnFixture):
	"""Withholding is applied, not just warned about — roadmap 1.2.

	The app created nine Tax Withholding Categories with correct dated rates and
	correct PCG accounts, and **not one of them could withhold anything**. Two
	separate reasons, both invisible:

	1. `single_threshold = 0`. ERPNext's `get_tds_amount` guards on
	   `if (threshold and net >= threshold)`, and 0 is falsy, so a zero threshold
	   means *never withhold* rather than *withhold from the first kip*.
	2. `apply_tds` is only defaulted from the supplier in
	   `set_missing_values(for_validate=False)`, which the Desk form triggers and a
	   scripted insert does not.

	Neither produces an error. The categories exist, the rates are right, and every
	purchase invoice silently withholds nothing — the same failure shape as the
	country match that made every doc_event dead code.
	"""

	CATEGORY = "WHT - Services & Consulting 10% (ຮ.ຕ. ບໍລິການ)"
	WHT_ACCOUNT_NUMBER = "4431"
	NET = 1_000_000.0
	RATE = 10.0

	def setUp(self):
		super().setUp()
		if not frappe.db.exists("Tax Withholding Category", self.CATEGORY):
			self.skipTest("the Lao withholding categories are not installed on this site")

		# Bring this site to the state after_migrate leaves it in. Idempotent, and
		# it means these tests do not depend on when a migrate last ran.
		from berp_lao.setup.tax_templates import repair_withholding_thresholds

		repair_withholding_thresholds()

		# A supplier of this test's own. ERPNext withholding is *period-cumulative*:
		# get_tds_amount sums every invoice for the party inside the rate row's date
		# window and deducts what was already withheld. Sharing one supplier makes
		# each test's expected amount depend on which tests ran before it — which is
		# exactly what happened the first time this suite was run.
		self.supplier = self._make_supplier()

	def _make_supplier(self) -> str:
		name = f"_Test Lao WHT Supplier {frappe.generate_hash(length=8)}"
		doc = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": name,
				"supplier_group": frappe.db.get_value("Supplier", SUPPLIER, "supplier_group"),
				"country": frappe.db.get_value("Supplier", SUPPLIER, "country"),
				"tax_withholding_category": self.CATEGORY,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _purchase_invoice(self, **overrides):
		doc = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"company": COMPANY,
				"supplier": self.supplier,
				"currency": "LAK",
				"conversion_rate": 1,
				"buying_price_list": PRICE_LIST_BUYING,
				"price_list_currency": "LAK",
				"plc_conversion_rate": 1,
				"set_posting_time": 1,
				"posting_date": self.posting_date,
				"due_date": add_days(self.posting_date, 30),
				"credit_to": self.payable,
				"items": [
					{
						"item_code": ITEM,
						"qty": 1,
						"rate": self.NET,
						"expense_account": self.expense,
						"cost_center": self.cost_center,
					}
				],
				**overrides,
			}
		)
		doc.insert()
		return doc

	@staticmethod
	def _withheld(doc) -> float:
		return flt(sum(row.tax_amount for row in doc.taxes if row.is_tax_withholding_account), 2)

	def test_the_seeding_never_produces_an_inert_rate_row(self):
		"""Ask the seeding function, not the site. Deterministic, and it is the source.

		A rate row with `single_threshold = 0` is not "no threshold" — ERPNext's
		`get_tds_amount` guards on `if (threshold and ...)`, so zero means *never*.
		"""
		from berp_lao.setup.tax_templates import _data, _rate_rows

		inert = [
			f"{spec['name']} [{row['from_date']}–{row['to_date']}]"
			for spec in _data().get("tax_withholding_categories", [])
			for row in _rate_rows(spec)
			if not flt(row["single_threshold"]) and not flt(row["cumulative_threshold"])
		]
		self.assertEqual(
			inert,
			[],
			"these rate rows would be seeded with no truthy threshold, so ERPNext "
			"would withhold nothing on them whatever rate they carry: " + ", ".join(inert),
		)

	def test_no_installed_category_is_inert(self):
		"""And the same question asked of the site, which `after_migrate` repairs."""
		from berp_lao.setup.tax_templates import CATEGORY_NAME_PREFIX

		inert = []
		for name in frappe.get_all(
			"Tax Withholding Category",
			filters={"name": ["like", f"{CATEGORY_NAME_PREFIX}%"]},
			pluck="name",
		):
			doc = frappe.get_doc("Tax Withholding Category", name)
			for row in doc.rates:
				if not flt(row.single_threshold) and not flt(row.cumulative_threshold):
					inert.append(f"{name} [{row.from_date}–{row.to_date}]")
		self.assertEqual(inert, [], "repair_withholding_thresholds did not reach: " + ", ".join(inert))

	def test_a_scripted_invoice_picks_up_the_supplier_category(self):
		"""The second half of the defect: the Desk sets apply_tds, an API insert does not."""
		doc = self._purchase_invoice()
		self.assertTrue(doc.apply_tds, "apply_tds was not defaulted from the supplier")
		self.assertEqual(doc.tax_withholding_category, self.CATEGORY)

	def test_the_withheld_amount_is_the_statutory_rate(self):
		doc = self._purchase_invoice()
		self.assertAlmostEqual(
			self._withheld(doc),
			flt(self.NET * self.RATE / 100.0, 2),
			places=1,
			msg="withholding is not the category's rate on the net total",
		)

	def test_withholding_reduces_what_the_supplier_is_paid(self):
		"""The point of withholding: the supplier receives the net of tax."""
		doc = self._purchase_invoice()
		self.assertAlmostEqual(
			flt(doc.grand_total, 2),
			flt(self.NET - self.NET * self.RATE / 100.0, 2),
			places=1,
		)

	def test_the_withheld_tax_lands_in_the_pcg_account(self):
		"""End to end: the ledger, not the document."""
		doc = self._purchase_invoice()
		doc.submit()

		wht_account = account_by_number(self.WHT_ACCOUNT_NUMBER)
		entries = frappe.get_all(
			"GL Entry",
			filters={"voucher_no": doc.name, "account": wht_account, "is_cancelled": 0},
			fields=["debit", "credit"],
		)
		self.assertTrue(entries, f"nothing posted to {wht_account}")
		credited = flt(sum(flt(row.credit) - flt(row.debit) for row in entries), 2)
		self.assertAlmostEqual(
			credited,
			flt(self.NET * self.RATE / 100.0, 2),
			places=1,
			msg="the withheld tax did not land in the PCG withholding account as a credit",
		)

	def test_the_ledger_balances(self):
		doc = self._purchase_invoice()
		doc.submit()
		entries = frappe.get_all(
			"GL Entry",
			filters={"voucher_no": doc.name, "is_cancelled": 0},
			fields=["debit", "credit"],
		)
		self.assertAlmostEqual(
			flt(sum(flt(e.debit) for e in entries), 2),
			flt(sum(flt(e.credit) for e in entries), 2),
			places=1,
		)

	def test_a_supplier_with_no_category_withholds_nothing(self):
		"""The rule must not invent withholding where the supplier carries none."""
		frappe.db.set_value("Supplier", self.supplier, "tax_withholding_category", None)
		doc = self._purchase_invoice()
		self.assertFalse(doc.apply_tds)
		self.assertEqual(self._withheld(doc), 0.0)

	def test_a_non_lao_company_is_left_alone(self):
		"""A multi-country site must not have this rule applied to its other books."""
		import berp_lao.lao_regional.rules.purchase_invoice as rules

		doc = frappe.get_doc({"doctype": "Purchase Invoice", "company": COMPANY, "supplier": SUPPLIER})
		from unittest.mock import patch

		with patch.object(rules, "is_lao_company", return_value=False):
			rules.apply_lao_withholding_defaults(doc)
		self.assertFalse(doc.get("apply_tds"))

	def test_the_rate_in_force_is_the_one_on_the_posting_date(self):
		"""Dated rows exist so a pre-July-2026 invoice withholds at the old rate.

		Services moved 5% → 10% under Law No. 88/NA on 1 July 2026. An invoice dated
		before that must still withhold 5%, which is the whole reason a rate change
		is a new row rather than an edit.
		"""
		doc = self._purchase_invoice(posting_date="2026-03-15", due_date="2026-04-15")
		self.assertAlmostEqual(
			self._withheld(doc),
			flt(self.NET * 5.0 / 100.0, 2),
			places=1,
			msg="an invoice dated before 1 July 2026 withheld at the post-88/NA rate",
		)

	def test_the_repair_is_idempotent_and_reports_what_it_changed(self):
		from berp_lao.setup.tax_templates import (
			NO_DE_MINIMIS_THRESHOLD,
			repair_withholding_thresholds,
		)

		doc = frappe.get_doc("Tax Withholding Category", self.CATEGORY)
		for row in doc.rates:
			row.single_threshold = 0
		doc.save(ignore_permissions=True)

		first = repair_withholding_thresholds()
		self.assertTrue(any(self.CATEGORY in entry for entry in first), f"repair reported {first}")

		doc.reload()
		for row in doc.rates:
			self.assertEqual(flt(row.single_threshold), float(NO_DE_MINIMIS_THRESHOLD))

		self.assertEqual(
			[entry for entry in repair_withholding_thresholds() if self.CATEGORY in entry],
			[],
			"a second run reported work it did not need to do",
		)
