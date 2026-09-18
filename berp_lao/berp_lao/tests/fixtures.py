# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
The Lao company every integration test posts against.

Extracted from `test_vat_return.py`, where it used to live. While it sat inside a
test module, "I need a Lao company" meant "write your test into that file", and the
file reached 710 lines because the fixture was the gravity well rather than the
subject. A shared fixture belongs where nothing has to be imported *through* a test
to reach it.

`ensure_masters` exists because a bare Frappe site has none of this: no Item Group
below the root, no Territory, no UOM, no Price List, no Fiscal Year. It also creates
*leaf* children of each root group, because ERPNext refuses a group Customer Group
or Territory on a Customer, and a fresh site ships only the roots.
"""

import json

import frappe
from frappe.utils import add_days, add_months, flt, getdate, nowdate

try:  # Frappe v16+
	from frappe.tests import IntegrationTestCase as _TestCase
except ImportError:  # Frappe v15
	from frappe.tests.utils import FrappeTestCase as _TestCase

from berp_lao.lao_regional.chart_of_accounts.lao_pcg import install_lao_chart_of_accounts
from berp_lao.lao_regional.country import (
	NOT_VAT_REGISTERED_FIELD,
	is_vat_registered,
	lao_country_name,
)
from berp_lao.lao_regional.report.lao_vat_return.lao_vat_return import execute
from berp_lao.setup.tax_templates import create_lao_tax_templates

COMPANY = "_Test Lao Co"
ABBR = "_TLC"
ITEM = "_Test Lao Service"
CUSTOMER = "_Test Lao Customer"
SUPPLIER = "_Test Lao Supplier"
#: Non-group children of each root master. ERPNext refuses a group Customer Group
#: or Territory on a Customer, and a fresh site has only the roots.
LEAF_GROUPS = {
	"Item Group": "_Test Lao Item Group",
	"Customer Group": "_Test Lao Customer Group",
	"Supplier Group": "_Test Lao Supplier Group",
	"Territory": "_Test Lao Territory",
}
#: A fresh site has no price lists either.
PRICE_LIST_SELLING = "_Test Lao Selling"
PRICE_LIST_BUYING = "_Test Lao Buying"

# Posting amounts, in LAK.
DOMESTIC_A = 1_000_000
DOMESTIC_B = 200_000
FREIGHT = 50_000
EXPORT = 500_000
PURCHASE = 400_000

EXPECTED_OUTPUT_VAT = (DOMESTIC_A + DOMESTIC_B) * 0.10  # 120,000
EXPECTED_INPUT_VAT = PURCHASE * 0.10  # 40,000


def load_tax_data() -> dict:
	path = frappe.get_app_path("berp_lao", "lao_regional", "data", "lao_tax_templates.json")
	with open(path, encoding="utf-8") as f:
		return json.load(f)


def account_by_number(number: str) -> str:
	name = frappe.db.get_value(
		"Account", {"company": COMPANY, "account_number": number, "is_group": 0}, "name"
	)
	if not name:
		raise AssertionError(f"PCG account {number} not found for {COMPANY}")
	return name


class LaoVatReturnFixture(_TestCase):
	"""Builds one Lao company with the PCG chart, tax templates and four invoices."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.posting_date = getdate(nowdate()).replace(day=1)
		cls.create_company()
		cls.create_masters()
		cls.post_invoices()

	# ─── setup ───────────────────────────────────────────────────────────────

	@classmethod
	def create_company(cls):
		if not frappe.db.exists("Company", COMPANY):
			# Skip ERPNext's own chart so the PCG chart is created cleanly rather
			# than replacing one — replacing commits, which would break rollback.
			frappe.local.flags.ignore_chart_of_accounts = True
			try:
				frappe.get_doc(
					{
						"doctype": "Company",
						"company_name": COMPANY,
						"abbr": ABBR,
						"default_currency": "LAK",
						"country": lao_country_name(),
					}
				).insert()
			finally:
				frappe.local.flags.ignore_chart_of_accounts = False

		if not frappe.db.exists("Account", {"company": COMPANY, "account_number": "4412"}):
			install_lao_chart_of_accounts(COMPANY)
			create_lao_tax_templates(COMPANY)

	@classmethod
	def create_masters(cls):
		cls.receivable = account_by_number("4111")
		cls.payable = account_by_number("4011")
		cls.output_vat = account_by_number("4412")
		cls.input_vat = account_by_number("4411")
		cls.income = account_by_number("7011")
		cls.expense = account_by_number("6011")
		cls.freight_account = account_by_number("6241")
		cls.cost_center = frappe.db.get_value("Cost Center", {"company": COMPANY, "is_group": 0}, "name")

		# A bare site — which is what CI gets — has not run ERPNext's setup wizard,
		# so the group and UOM masters these fixtures link to may not exist yet.
		cls.ensure_masters()

		if not frappe.db.exists("Item", ITEM):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": ITEM,
					"item_name": ITEM,
					"item_group": LEAF_GROUPS["Item Group"],
					"stock_uom": "Nos",
					"is_stock_item": 0,
					"is_purchase_item": 1,
					"is_sales_item": 1,
				}
			).insert()

		for doctype, name, extra in (
			(
				"Customer",
				CUSTOMER,
				{
					"customer_group": LEAF_GROUPS["Customer Group"],
					"territory": LEAF_GROUPS["Territory"],
				},
			),
			("Supplier", SUPPLIER, {"supplier_group": LEAF_GROUPS["Supplier Group"]}),
		):
			if not frappe.db.exists(doctype, name):
				frappe.get_doc({"doctype": doctype, doctype.lower() + "_name": name, **extra}).insert()

	@classmethod
	def ensure_masters(cls):
		"""Create the group, territory and UOM records a fresh site lacks.

		ERPNext refuses a *group* Customer Group or Territory on a Customer, so each
		root gets one leaf child and the fixtures link to the leaf.
		"""
		roots = (
			("Item Group", "item_group_name", "All Item Groups", "parent_item_group"),
			("Customer Group", "customer_group_name", "All Customer Groups", "parent_customer_group"),
			("Supplier Group", "supplier_group_name", "All Supplier Groups", "parent_supplier_group"),
			("Territory", "territory_name", "All Territories", "parent_territory"),
		)
		for doctype, field, root, parent_field in roots:
			if not frappe.db.exists(doctype, root):
				frappe.get_doc({"doctype": doctype, field: root, "is_group": 1}).insert(
					ignore_permissions=True, ignore_mandatory=True
				)
			leaf = LEAF_GROUPS[doctype]
			if not frappe.db.exists(doctype, leaf):
				frappe.get_doc({"doctype": doctype, field: leaf, "is_group": 0, parent_field: root}).insert(
					ignore_permissions=True, ignore_mandatory=True
				)

		if not frappe.db.exists("UOM", "Nos"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "Nos"}).insert(ignore_permissions=True)

		# The Lao fiscal year is the calendar year (Decision 137/VTE, 13 Feb 2024).
		year = getdate(cls.posting_date).year
		if not frappe.db.exists("Fiscal Year", str(year)):
			frappe.get_doc(
				{
					"doctype": "Fiscal Year",
					"year": str(year),
					"year_start_date": f"{year}-01-01",
					"year_end_date": f"{year}-12-31",
				}
			).insert(ignore_permissions=True, ignore_mandatory=True)

		for price_list, selling in ((PRICE_LIST_SELLING, 1), (PRICE_LIST_BUYING, 0)):
			if frappe.db.exists("Price List", price_list):
				continue
			frappe.get_doc(
				{
					"doctype": "Price List",
					"price_list_name": price_list,
					"currency": "LAK",
					"enabled": 1,
					"selling": selling,
					"buying": 0 if selling else 1,
				}
			).insert(ignore_permissions=True, ignore_mandatory=True)

	# ─── invoices ────────────────────────────────────────────────────────────

	@classmethod
	def _sales_invoice(cls, rate, invoice_type, taxes):
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
				"posting_date": cls.posting_date,
				"due_date": add_days(cls.posting_date, 30),
				"debit_to": cls.receivable,
				"lao_invoice_type": invoice_type,
				"items": [
					{
						"item_code": ITEM,
						"qty": 1,
						"rate": rate,
						"income_account": cls.income,
						"cost_center": cls.cost_center,
					}
				],
				"taxes": taxes,
			}
		)
		doc.insert()
		doc.submit()
		return doc

	@classmethod
	def post_invoices(cls):
		if frappe.db.exists("Sales Invoice", {"company": COMPANY, "docstatus": 1}):
			return  # already built for this class run

		vat_row = {
			"charge_type": "On Net Total",
			"account_head": cls.output_vat,
			"rate": 10,
			"description": "VAT 10%",
			"cost_center": cls.cost_center,
		}
		freight_row = {
			"charge_type": "Actual",
			"account_head": cls.freight_account,
			"rate": 0,
			"tax_amount": FREIGHT,
			"description": "Freight & Delivery",
			"cost_center": cls.cost_center,
		}

		cls.si_a = cls._sales_invoice(DOMESTIC_A, "Standard", [dict(vat_row)])
		# Carries a non-VAT charge alongside the VAT row — the regression case.
		cls.si_b = cls._sales_invoice(DOMESTIC_B, "Standard", [dict(vat_row), dict(freight_row)])
		cls.si_export = cls._sales_invoice(
			EXPORT,
			"Export (0%)",
			[{**vat_row, "rate": 0, "description": "VAT 0% - Export"}],
		)

		pi = frappe.get_doc(
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
				"posting_date": cls.posting_date,
				"due_date": add_days(cls.posting_date, 30),
				"credit_to": cls.payable,
				"items": [
					{
						"item_code": ITEM,
						"qty": 1,
						"rate": PURCHASE,
						"expense_account": cls.expense,
						"cost_center": cls.cost_center,
					}
				],
				"taxes": [
					{
						"charge_type": "On Net Total",
						"account_head": cls.input_vat,
						"rate": 10,
						"description": "VAT 10% Input",
						"category": "Total",
						"add_deduct_tax": "Add",
						"cost_center": cls.cost_center,
					}
				],
			}
		)
		pi.insert()
		pi.submit()
		cls.pi = pi

	# ─── helpers ─────────────────────────────────────────────────────────────

	def run_report(self):
		filters = {
			"company": COMPANY,
			"from_date": self.posting_date,
			"to_date": add_days(self.posting_date, 27),
		}
		_columns, data, _message, _chart, summary, _skip_total = execute(filters)
		return data, summary

	@staticmethod
	def row(data, prefix):
		"""Fetch a report row by its leading section number, bold markup aside."""
		for r in data:
			section = r["section"].removeprefix("<b>")
			if section.startswith(prefix):
				return r
		raise AssertionError(f"no report row starting {prefix!r}")
