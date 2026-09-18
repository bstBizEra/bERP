# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Installing a Lao company: the PCG chart, the company defaults, the tax templates.

Mirrors `chart_of_accounts/` and `setup/`. Three of the six defects the first
bench run found were here — the chart aborting on a duplicate account number,
`default_receivable_account` landing on the wrong side of a two-account type,
and a Company field ERPNext does not have surfacing as a raw SQL error.
"""

import frappe
from frappe.utils import add_days, add_months, flt, getdate, nowdate

try:  # Frappe v16+
	from frappe.tests import IntegrationTestCase as _TestCase
except ImportError:  # Frappe v15
	from frappe.tests.utils import FrappeTestCase as _TestCase

from berp_lao.lao_regional.chart_of_accounts.lao_pcg import (
	install_lao_chart_of_accounts,
)
from berp_lao.setup.tax_templates import create_lao_tax_templates
from berp_lao.tests.fixtures import (
	ABBR,
	COMPANY,
	DOMESTIC_A,
	DOMESTIC_B,
	EXPECTED_INPUT_VAT,
	EXPECTED_OUTPUT_VAT,
	EXPORT,
	FREIGHT,
	ITEM,
	PURCHASE,
	SUPPLIER,
	LaoVatReturnFixture,
	account_by_number,
	load_tax_data,
)


class TestLaoCompanySetup(LaoVatReturnFixture):
	def test_chart_installed_with_both_sides_of_class_four(self):
		"""Classes 1 and 4 each land as two roots with different root types.

		Roots carry no `account_number` — ERPNext enforces number uniqueness per
		company, so the class digit lives in the name instead, as in ERPNext's own
		French PCG. Match on that leading digit.
		"""
		roots = frappe.get_all(
			"Account",
			filters={"company": COMPANY, "parent_account": ["in", ["", None]]},
			fields=["account_name", "account_number", "root_type"],
		)
		self.assertTrue(roots, "no root accounts were created")

		by_class = {}
		for r in roots:
			self.assertFalse(r.account_number, f"root {r.account_name!r} carries an account_number")
			by_class.setdefault(r.account_name.split(" ", 1)[0], set()).add(r.root_type)

		self.assertEqual(by_class.get("4"), {"Asset", "Liability"})
		self.assertEqual(by_class.get("1"), {"Equity", "Liability"})
		self.assertEqual(len(roots), 10)

	def test_company_defaults_point_at_pcg_accounts(self):
		"""Each default must be the account the PCG names, not whichever row came first.

		A bench run caught `default_receivable_account` landing on 4112 Trade
		Debtors - Foreign: the lookup was by `account_type`, and two accounts share
		it, so the winner was row order.
		"""
		company = frappe.get_doc("Company", COMPANY)
		expected = {
			"default_receivable_account": "4111",
			"default_payable_account": "4011",
			"default_income_account": "7011",
			"default_expense_account": "6011",
			"default_cash_account": "5401",
			"default_bank_account": "5111",
			"stock_received_but_not_billed": "4013",
		}
		for fieldname, number in expected.items():
			with self.subTest(field=fieldname):
				self.assertEqual(company.get(fieldname), account_by_number(number))

	def test_company_defaults_are_stable_when_reapplied(self):
		"""Re-running the resolver must not move a default to a sibling account."""
		from berp_lao.lao_regional.chart_of_accounts.lao_pcg import set_company_default_accounts

		first = set_company_default_accounts(COMPANY)
		second = set_company_default_accounts(COMPANY)
		self.assertEqual(first, second)
		self.assertTrue(first, "no defaults resolved at all")

	def test_tax_templates_resolve_to_the_right_accounts(self):
		template = frappe.get_doc("Sales Taxes and Charges Template", f"VAT 10% (ອາກອນ 10%) - {ABBR}")
		self.assertEqual(len(template.taxes), 1)
		self.assertEqual(template.taxes[0].account_head, account_by_number("4412"))
		self.assertEqual(flt(template.taxes[0].rate), 10.0)
		self.assertTrue(template.is_default)

		purchase = frappe.get_doc(
			"Purchase Taxes and Charges Template", f"VAT 10% Input (ອາກອນ VAT ຊື້) - {ABBR}"
		)
		self.assertEqual(purchase.taxes[0].account_head, account_by_number("4411"))

	def test_withholding_categories_have_a_company_account_row(self):
		"""Every category in the data file must exist and point at its PCG account."""
		for spec in load_tax_data()["tax_withholding_categories"]:
			with self.subTest(category=spec["name"]):
				doc = frappe.get_doc("Tax Withholding Category", spec["name"])
				rows = [r for r in doc.accounts if r.company == COMPANY]
				self.assertEqual(len(rows), 1, f"{spec['name']} has no account row for {COMPANY}")
				self.assertEqual(rows[0].account, account_by_number(spec["account_number"]))

	def test_withholding_rate_history_is_preserved(self):
		"""
		A statutory rate change is a new dated row, not an edit.

		Construction and repair went from 2% to 5% under the Income Tax Law 2025,
		in force 1 July 2026. An invoice dated before that must still withhold 2%,
		so both rows have to reach the database.
		"""
		for spec in load_tax_data()["tax_withholding_categories"]:
			doc = frappe.get_doc("Tax Withholding Category", spec["name"])
			expected = sorted((r["from_date"], flt(r["rate"])) for r in spec["rates"])
			actual = sorted((str(getdate(r.from_date)), flt(r.tax_withholding_rate)) for r in doc.rates)
			with self.subTest(category=spec["name"]):
				self.assertEqual(actual, expected)

	def test_tax_template_creation_is_idempotent(self):
		"""Call it twice; the second call must create nothing.

		This used to assert that a *single* call created nothing, which quietly
		depended on the fixture having already made every kind of template. Adding
		Item Tax Templates broke that assumption and the test failed — correctly,
		but for the wrong reason: the assertion was about the fixture's state, not
		about idempotence. Running it twice tests the property directly.
		"""
		first = create_lao_tax_templates(COMPANY)
		self.assertEqual(first["missing_accounts"], [], f"unresolved accounts: {first['missing_accounts']}")

		second = create_lao_tax_templates(COMPANY)
		self.assertEqual(second["created"], [], "a second run created templates again")
		self.assertEqual(second["missing_accounts"], [])
		self.assertTrue(second["skipped"], "a second run skipped nothing, so it saw nothing")

	def test_the_item_tax_templates_ship_and_resolve_to_the_vat_account(self):
		"""Per-line VAT is only representable if these exist."""
		create_lao_tax_templates(COMPANY)
		vat_account = account_by_number("4412")

		for spec in load_tax_data().get("item_tax_templates", []):
			with self.subTest(template=spec["title"]):
				name = frappe.db.get_value(
					"Item Tax Template", {"company": COMPANY, "title": spec["title"]}, "name"
				)
				self.assertTrue(name, f"{spec['title']} was not created")
				doc = frappe.get_doc("Item Tax Template", name)
				self.assertEqual([row.tax_type for row in doc.taxes], [vat_account])
				self.assertEqual(
					[flt(row.tax_rate) for row in doc.taxes],
					[flt(spec["taxes"][0]["tax_rate"])],
				)


class TestCustomFieldDefinitions(_TestCase):
	"""The custom field JSON, asked of the live DocType meta — ADR-A2.

	These 13 definitions used to be a Python literal, and nothing checked them
	against the framework. Two of the six defects the first bench run found were
	that class of mismatch: `Stock In Hand` and `Bank Charge` were valid account
	types in v13/v14 and are not in v15. A typo in `insert_after` is the same shape
	of bug and is silent — the field simply lands somewhere else, or nowhere.

	The list of valid field types is read from `DocField.fieldtype`'s own options
	rather than hardcoded here, for the same reason: a hardcoded copy is a claim
	about the framework that stops being true without telling anyone.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from berp_lao.setup.install import get_lao_custom_fields

		cls.definitions = get_lao_custom_fields()
		cls.valid_fieldtypes = set(
			(frappe.get_meta("DocField").get_field("fieldtype").options or "").split("\n")
		)

	def test_the_definitions_are_not_empty(self):
		"""A loader that silently returns nothing would pass every test below."""
		self.assertTrue(self.definitions, "no custom field definitions loaded")
		self.assertTrue(
			sum(len(rows) for rows in self.definitions.values()) >= 13,
			"fewer fields than the app is known to define — did the JSON fail to load?",
		)

	def test_every_target_doctype_exists(self):
		for doctype in self.definitions:
			with self.subTest(doctype=doctype):
				self.assertTrue(frappe.db.exists("DocType", doctype), f"no DocType {doctype}")

	def test_every_fieldtype_is_real_in_this_frappe(self):
		for doctype, rows in self.definitions.items():
			for row in rows:
				with self.subTest(field=f"{doctype}.{row['fieldname']}"):
					self.assertIn(
						row["fieldtype"],
						self.valid_fieldtypes,
						f"{row['fieldtype']} is not a field type in this Frappe",
					)

	def test_every_link_option_names_a_real_doctype(self):
		for doctype, rows in self.definitions.items():
			for row in rows:
				if row["fieldtype"] != "Link":
					continue
				with self.subTest(field=f"{doctype}.{row['fieldname']}"):
					target = row.get("options")
					self.assertTrue(target, "a Link field with no options")
					self.assertTrue(
						frappe.db.exists("DocType", target),
						f"Link target {target} does not exist",
					)

	def test_every_insert_after_names_a_field_that_exists(self):
		"""The silent one. A typo here puts the field somewhere else, or nowhere.

		A field may be anchored to one of this app's own fields, so the fields
		declared earlier in the same list count as existing.
		"""
		for doctype, rows in self.definitions.items():
			meta = frappe.get_meta(doctype)
			known = {field.fieldname for field in meta.fields}
			for row in rows:
				anchor = row.get("insert_after")
				with self.subTest(field=f"{doctype}.{row['fieldname']}"):
					self.assertTrue(anchor, "no insert_after; the field lands at the end")
					self.assertIn(
						anchor,
						known,
						f"insert_after={anchor} names no field on {doctype}",
					)
				known.add(row["fieldname"])

	def test_no_documentation_key_reaches_a_custom_field(self):
		"""`_why` notes live beside the data and must be stripped before use.

		JSON has no comments, so the reasoning for a field is carried in keys the
		loader removes. If one leaked through, `create_custom_fields` would try to
		set an attribute Custom Field does not have.
		"""
		from berp_lao.setup.install import DOC_KEY_PREFIX

		custom_field_fields = {f.fieldname for f in frappe.get_meta("Custom Field").fields}
		for doctype, rows in self.definitions.items():
			for row in rows:
				for key in row:
					with self.subTest(field=f"{doctype}.{row['fieldname']}", key=key):
						self.assertFalse(
							key.startswith(DOC_KEY_PREFIX),
							f"{key} is a documentation key and should have been stripped",
						)
						self.assertIn(
							key,
							custom_field_fields,
							f"{key} is not a Custom Field property",
						)

	def test_the_json_still_carries_its_reasoning(self):
		"""Guards the notes from being dropped the first time someone regenerates it."""
		import json

		path = frappe.get_app_path("berp_lao", "lao_regional", "data", "custom_fields.json")
		with open(path, encoding="utf-8") as handle:
			raw = json.load(handle)

		noted = [
			f"{doctype}.{row['fieldname']}"
			for doctype, rows in raw.items()
			for row in rows
			if row.get("_why")
		]
		self.assertIn("Company.lao_not_vat_registered", noted)
		self.assertGreaterEqual(len(noted), 4, "the explanatory notes have been lost")

	def test_every_defined_field_actually_landed_on_this_site(self):
		"""End to end: after_install/after_migrate applied them, meta can see them."""
		for doctype, rows in self.definitions.items():
			meta = frappe.get_meta(doctype)
			for row in rows:
				with self.subTest(field=f"{doctype}.{row['fieldname']}"):
					field = meta.get_field(row["fieldname"])
					self.assertIsNotNone(field, "defined but not present on this site")
					self.assertEqual(field.fieldtype, row["fieldtype"])
