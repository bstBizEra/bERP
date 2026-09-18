# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
The Lao Monthly VAT Return, against posted invoices.

The case that matters most is `test_output_vat_excludes_non_vat_charges`: the
report used to read `base_total_taxes_and_charges` from the invoice header,
which is the sum of *every* tax and charge row, so a freight line was declared
to the Revenue Department as VAT. The fixture carries such a line specifically
so that regression cannot come back unnoticed.
"""

import frappe
from frappe.utils import add_days, add_months, flt, getdate, nowdate

from berp_lao.lao_regional.report.lao_vat_return.lao_vat_return import (
	_output_vat,
	_sales_net_by_type,
	execute,
)
from berp_lao.setup.tax_templates import create_lao_tax_templates
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
	lao_country_name,
	load_tax_data,
)


class TestLaoVatReturn(LaoVatReturnFixture):
	def test_output_vat_excludes_non_vat_charges(self):
		"""
		The freight row on si_b must not be declared as VAT.

		Reading `base_total_taxes_and_charges` off the invoice headers would give
		170,000 here; only 120,000 of that is VAT.
		"""
		data, _ = self.run_report()
		total_output = self.row(data, "4.")

		self.assertEqual(flt(total_output["vat_amount"]), EXPECTED_OUTPUT_VAT)

		header_sum = sum(
			flt(v)
			for v in frappe.get_all(
				"Sales Invoice",
				filters={"company": COMPANY, "docstatus": 1},
				pluck="base_total_taxes_and_charges",
			)
		)
		self.assertEqual(header_sum, EXPECTED_OUTPUT_VAT + FREIGHT)
		self.assertNotEqual(flt(total_output["vat_amount"]), header_sum)

	def test_domestic_sales_net_and_count(self):
		data, _ = self.run_report()
		domestic = self.row(data, "1.")
		self.assertEqual(flt(domestic["base_amount"]), DOMESTIC_A + DOMESTIC_B)
		self.assertEqual(domestic["invoice_count"], 2)
		self.assertEqual(flt(domestic["vat_rate"]), 10.0)

	def test_export_sales_are_separated_and_zero_rated(self):
		data, _ = self.run_report()
		export = self.row(data, "2.")
		self.assertEqual(flt(export["base_amount"]), EXPORT)
		self.assertEqual(flt(export["vat_amount"]), 0.0)
		self.assertEqual(export["invoice_count"], 1)

		# The export invoice must not have leaked into the domestic line.
		self.assertEqual(flt(self.row(data, "1.")["base_amount"]), DOMESTIC_A + DOMESTIC_B)

	def test_input_vat(self):
		data, _ = self.run_report()
		purchases = self.row(data, "5.")
		self.assertEqual(flt(purchases["base_amount"]), PURCHASE)
		self.assertEqual(flt(self.row(data, "6.")["vat_amount"]), EXPECTED_INPUT_VAT)

	def test_net_vat_payable(self):
		data, summary = self.run_report()
		net = self.row(data, "7.")
		self.assertEqual(flt(net["vat_amount"]), EXPECTED_OUTPUT_VAT - EXPECTED_INPUT_VAT)

		self.assertEqual(flt(summary[0]["value"]), EXPECTED_OUTPUT_VAT)
		self.assertEqual(flt(summary[1]["value"]), EXPECTED_INPUT_VAT)
		self.assertEqual(summary[2]["label"], frappe._("Net VAT Payable"))

	def test_period_filter_excludes_invoices_outside_the_range(self):
		_columns, data, *_rest = execute(
			{
				"company": COMPANY,
				"from_date": add_days(self.posting_date, -60),
				"to_date": add_days(self.posting_date, -31),
			}
		)
		self.assertEqual(flt(self.row(data, "4.")["vat_amount"]), 0.0)
		self.assertEqual(flt(self.row(data, "1.")["base_amount"]), 0.0)

	def test_report_rejects_a_non_lao_company(self):
		other = frappe.db.get_value("Company", {"country": ["!=", lao_country_name()]}, "name")
		if not other:
			self.skipTest("no non-Lao company on this site")
		with self.assertRaises(frappe.ValidationError):
			execute({"company": other, "from_date": self.posting_date, "to_date": nowdate()})

	def test_report_requires_a_date_range(self):
		with self.assertRaises(frappe.ValidationError):
			execute({"company": COMPANY, "from_date": None, "to_date": None})

	def test_from_date_after_to_date_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			execute(
				{
					"company": COMPANY,
					"from_date": add_days(self.posting_date, 10),
					"to_date": self.posting_date,
				}
			)


class TestMixedInvoiceVatTreatment(LaoVatReturnFixture):
	"""Roadmap 2.2 — one invoice, two VAT treatments.

	The defect this suite exists for: `_sales_net_by_type` grouped by the
	invoice-level `lao_invoice_type` and summed `base_net_total`, so a mixed
	invoice was declared entirely under its header's label. Measured before the
	fix, on an invoice of 1,000,000 taxable + 500,000 exempt marked "Standard":

	    standard-rated net declared   1,500,000
	    output VAT declared             100,000
	    net that actually bore VAT    1,000,000

	ERPNext charged the right VAT throughout. Only the return was wrong — and it
	was wrong in the way that matters most, by **not reconciling with itself**: a
	1,500,000 standard-rated base implies 150,000 of VAT at 10%.

	`test_the_return_reconciles_with_itself` is the assertion that would have
	caught it. Every other test here is about how a line is classified; that one is
	about whether the return adds up.
	"""

	TAXABLE = 1_000_000.0
	EXEMPT = 500_000.0

	def setUp(self):
		super().setUp()
		create_lao_tax_templates(COMPANY)
		self.vat_account = account_by_number("4412")
		self.exempt_template = self._template("Lao VAT Exempt (ຍົກເວັ້ນ)")
		self.taxed_template = self._template("Lao VAT 10% (ອາກອນ 10%)")
		self.exempt_item = self._exempt_item()

	def _template(self, title):
		name = frappe.db.get_value("Item Tax Template", {"company": COMPANY, "title": title}, "name")
		self.assertTrue(name, f"{title} was not installed")
		return name

	def _exempt_item(self):
		code = "_Test Lao Exempt Good"
		if not frappe.db.exists("Item", code):
			source = frappe.get_doc("Item", ITEM)
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": code,
					"item_group": source.item_group,
					"stock_uom": source.stock_uom,
					"is_stock_item": 0,
				}
			).insert(ignore_permissions=True)
		return code

	def _mixed_invoice(self, invoice_type="Standard"):
		doc = frappe.get_doc(
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
				"lao_invoice_type": invoice_type,
				"debit_to": self.receivable,
				"items": [
					{
						"item_code": ITEM,
						"qty": 1,
						"rate": self.TAXABLE,
						"income_account": self.income,
						"cost_center": self.cost_center,
						"item_tax_template": self.taxed_template,
					},
					{
						"item_code": self.exempt_item,
						"qty": 1,
						"rate": self.EXEMPT,
						"income_account": self.income,
						"cost_center": self.cost_center,
						"item_tax_template": self.exempt_template,
					},
				],
				"taxes": [
					{
						"charge_type": "On Net Total",
						"account_head": self.vat_account,
						"rate": 10,
						"description": "VAT 10%",
						"cost_center": self.cost_center,
					}
				],
			}
		)
		doc.insert()
		doc.submit()
		return doc

	def _period(self):
		return frappe._dict(
			{
				"company": COMPANY,
				"from_date": self.posting_date,
				"to_date": add_days(self.posting_date, 27),
			}
		)

	def test_erpnext_charges_vat_only_on_the_taxable_line(self):
		"""The framework was never the problem. Pinned so a regression is attributable."""
		doc = self._mixed_invoice()
		self.assertAlmostEqual(flt(doc.net_total, 2), self.TAXABLE + self.EXEMPT, places=1)
		self.assertAlmostEqual(flt(doc.total_taxes_and_charges, 2), flt(self.TAXABLE * 0.10, 2), places=1)

	def test_the_exempt_line_is_not_declared_as_standard_rated(self):
		"""The defect itself."""
		before = _sales_net_by_type(self._period())
		before_standard = flt((before.get("Standard") or {}).get("net_total"))

		self._mixed_invoice()

		after = _sales_net_by_type(self._period())
		after_standard = flt((after.get("Standard") or {}).get("net_total"))
		after_exempt = flt((after.get("VAT Exempt") or {}).get("net_total"))

		self.assertAlmostEqual(
			after_standard - before_standard,
			self.TAXABLE,
			places=1,
			msg="the whole invoice was declared standard-rated, exempt line included",
		)
		self.assertGreaterEqual(after_exempt, self.EXEMPT)

	def test_the_return_reconciles_with_itself(self):
		"""Declared standard-rated base x 10% must equal declared output VAT.

		This is the property the old report broke. It holds for the whole period,
		not just this invoice, which is what makes it worth asserting.
		"""
		self._mixed_invoice()

		period = self._period()
		sales = _sales_net_by_type(period)
		declared_vat = _output_vat(period)

		vatable = flt((sales.get("Standard") or {}).get("net_total")) + flt(
			(sales.get("Simplified") or {}).get("net_total")
		)
		self.assertAlmostEqual(
			flt(vatable * 0.10, 2),
			flt(declared_vat, 2),
			places=0,
			msg=(
				f"the return does not reconcile: a standard-rated base of {vatable:,.0f} "
				f"implies {vatable * 0.10:,.0f} of VAT, but {declared_vat:,.0f} is declared"
			),
		)

	def test_a_mixed_invoice_is_counted_once_under_each_treatment_it_touches(self):
		doc = self._mixed_invoice()
		sales = _sales_net_by_type(self._period())
		self.assertGreaterEqual(int(flt((sales.get("Standard") or {}).get("invoice_count"))), 1)
		self.assertGreaterEqual(int(flt((sales.get("VAT Exempt") or {}).get("invoice_count"))), 1)
		self.assertTrue(doc.name)

	def test_a_zero_rated_line_on_an_export_invoice_is_an_export_not_an_exemption(self):
		"""Same 0% rate, different declaration. The header decides which."""
		from berp_lao.lao_regional.report.lao_vat_return.lao_vat_return import _line_treatment

		self.assertEqual(_line_treatment("Export (0%)", 0.0), "Export (0%)")
		self.assertEqual(_line_treatment("Standard", 0.0), "VAT Exempt")

	def test_a_line_with_no_template_inherits_the_invoice_type(self):
		"""None is not zero — the ordinary case must not be reclassified as exempt."""
		from berp_lao.lao_regional.report.lao_vat_return.lao_vat_return import (
			_line_treatment,
			_line_vat_rate,
		)

		self.assertIsNone(_line_vat_rate("{}", {self.vat_account}))
		self.assertIsNone(_line_vat_rate(None, {self.vat_account}))
		self.assertIsNone(_line_vat_rate('{"Some Other Account": 7}', {self.vat_account}))
		for invoice_type in ("Standard", "Export (0%)", "VAT Exempt", "Simplified"):
			with self.subTest(invoice_type=invoice_type):
				self.assertEqual(_line_treatment(invoice_type, None), invoice_type)

	def test_a_taxed_line_is_standard_rated_whatever_the_header_says(self):
		from berp_lao.lao_regional.report.lao_vat_return.lao_vat_return import _line_treatment

		self.assertEqual(_line_treatment("VAT Exempt", 10.0), "Standard")
		self.assertEqual(_line_treatment("Export (0%)", 10.0), "Standard")
		self.assertEqual(_line_treatment("Simplified", 10.0), "Simplified")

	def test_the_line_totals_agree_with_the_invoice_totals(self):
		"""Two instruments: per-line classification must not lose or invent money."""
		self._mixed_invoice()
		period = self._period()
		sales = _sales_net_by_type(period)
		classified = flt(sum(flt(row.get("net_total")) for row in sales.values()), 2)

		invoice_level = frappe.db.sql(
			"""
			SELECT SUM(base_net_total) FROM `tabSales Invoice`
			WHERE company = %(company)s AND docstatus = 1
			  AND posting_date BETWEEN %(from_date)s AND %(to_date)s
			""",
			period,
		)[0][0]
		self.assertAlmostEqual(
			classified,
			flt(invoice_level, 2),
			places=0,
			msg="the sum of the per-line classification does not equal the invoices' net total",
		)
