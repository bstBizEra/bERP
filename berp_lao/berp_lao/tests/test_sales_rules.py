# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Lao rules on the Sales Invoice — mirrors `lao_regional/rules/sales_invoice.py`.

Every rule here warns and lets the document through, so the assertions are about
*which message appears*, not about whether the save succeeded. A rule that stops
firing is invisible otherwise: that is exactly how the country-matching defect
survived — the hooks ran, returned immediately, and nothing failed.
"""

import frappe
from frappe.utils import add_days, add_months, flt, getdate, nowdate

from berp_lao.lao_regional.country import NOT_VAT_REGISTERED_FIELD, is_vat_registered
from berp_lao.tests.fixtures import (
	COMPANY,
	CUSTOMER,
	DOMESTIC_A,
	DOMESTIC_B,
	EXPECTED_INPUT_VAT,
	EXPECTED_OUTPUT_VAT,
	EXPORT,
	FREIGHT,
	ITEM,
	PRICE_LIST_SELLING,
	PURCHASE,
	SUPPLIER,
	LaoVatReturnFixture,
	account_by_number,
	load_tax_data,
)


class TestLaoInvoiceHooks(LaoVatReturnFixture):
	def test_standard_invoice_without_vat_warns(self):
		frappe.clear_messages()
		doc = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": COMPANY,
				"customer": CUSTOMER,
				"currency": "LAK",
				"conversion_rate": 1,
				"set_posting_time": 1,
				"posting_date": self.posting_date,
				"due_date": add_days(self.posting_date, 30),
				"debit_to": self.receivable,
				"lao_invoice_type": "Standard",
				"items": [
					{
						"item_code": ITEM,
						"qty": 1,
						"rate": DOMESTIC_A,
						"income_account": self.income,
						"cost_center": self.cost_center,
					}
				],
			}
		)
		doc.insert()

		messages = " ".join(str(m) for m in frappe.get_message_log())
		self.assertIn("no 10% VAT row", messages)

	def test_export_invoice_without_vat_does_not_warn_about_vat(self):
		frappe.clear_messages()
		doc = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": COMPANY,
				"customer": CUSTOMER,
				"currency": "LAK",
				"conversion_rate": 1,
				"set_posting_time": 1,
				"posting_date": self.posting_date,
				"due_date": add_days(self.posting_date, 30),
				"debit_to": self.receivable,
				"lao_invoice_type": "Export (0%)",
				"items": [
					{
						"item_code": ITEM,
						"qty": 1,
						"rate": EXPORT,
						"income_account": self.income,
						"cost_center": self.cost_center,
					}
				],
			}
		)
		doc.insert()

		messages = " ".join([str(m) for m in frappe.get_message_log()])
		self.assertNotIn("no 10% VAT row", messages)


class TestLaoMicroEnterprise(LaoVatReturnFixture):
	"""A micro-enterprise is not VAT registered, so the VAT prompts are wrong."""

	def tearDown(self):
		frappe.db.set_value("Company", COMPANY, NOT_VAT_REGISTERED_FIELD, 0)
		frappe.clear_cache(doctype="Company")

	def _flag_micro(self):
		frappe.db.set_value("Company", COMPANY, NOT_VAT_REGISTERED_FIELD, 1)
		frappe.clear_cache(doctype="Company")

	def test_is_vat_registered_defaults_to_true(self):
		self.assertTrue(is_vat_registered(COMPANY))

	def test_flagging_the_company_clears_it(self):
		self._flag_micro()
		self.assertFalse(is_vat_registered(COMPANY))

	def test_a_micro_enterprise_invoice_without_vat_is_not_warned_about(self):
		self._flag_micro()
		frappe.clear_messages()
		frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": COMPANY,
				"customer": CUSTOMER,
				"currency": "LAK",
				"conversion_rate": 1,
				"selling_price_list": PRICE_LIST_SELLING,
				"price_list_currency": "LAK",
				"plc_conversion_rate": 1,
				"set_posting_time": 1,
				"posting_date": self.posting_date,
				"due_date": add_days(self.posting_date, 30),
				"debit_to": self.receivable,
				"lao_invoice_type": "Standard",
				"items": [
					{
						"item_code": ITEM,
						"qty": 1,
						"rate": 900000,
						"income_account": self.income,
						"cost_center": self.cost_center,
					}
				],
			}
		).insert()
		messages = " ".join(str(m) for m in frappe.get_message_log())
		self.assertNotIn("no 10% VAT row", messages)
