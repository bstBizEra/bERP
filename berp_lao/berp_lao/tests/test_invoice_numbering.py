# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Per-company invoice numbering — mirrors `rules/sales_invoice.set_lao_invoice_series`.

THE FACT THIS IS BUILT ON, MEASURED RATHER THAN ASSUMED
    Frappe keeps one counter per naming-series prefix **per site**. `tabSeries`
    holds a single row `ACC-SINV-2026-` and the company appears nowhere in the key,
    so two companies on one site interleave and neither has a contiguous sequence.
    `test_the_shared_counter_is_still_how_frappe_works` asserts that directly — if
    Frappe ever keys the counter by company, this whole feature is unnecessary and
    that test says so.

WHAT THIS DOES NOT DEPEND ON
    Any answer to BERP-LAO-QUESTIONS-001 Q9. Whether or not Laos controls invoice
    numbers, a company's own sequence being contiguous is never worse. If Q9 comes
    back "the authority issues the numbers", this becomes moot rather than wrong.
"""

import frappe
from frappe.utils import add_days, flt

from berp_lao.lao_regional.rules.sales_invoice import (
	PER_COMPANY_NUMBERING_FIELD,
	lao_invoice_series,
	set_lao_invoice_series,
)
from berp_lao.tests.fixtures import (
	COMPANY,
	CUSTOMER,
	ITEM,
	PRICE_LIST_SELLING,
	LaoVatReturnFixture,
)


class TestPerCompanyInvoiceNumbering(LaoVatReturnFixture):
	def tearDown(self):
		frappe.db.set_value("Company", COMPANY, PER_COMPANY_NUMBERING_FIELD, 0)
		frappe.clear_document_cache("Company", COMPANY)
		super().tearDown()

	def _enable(self, on=1):
		frappe.db.set_value("Company", COMPANY, PER_COMPANY_NUMBERING_FIELD, on)
		frappe.clear_document_cache("Company", COMPANY)

	def _invoice(self, **overrides):
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
				"debit_to": self.receivable,
				"items": [
					{
						"item_code": ITEM,
						"qty": 1,
						"rate": 1_000,
						"income_account": self.income,
						"cost_center": self.cost_center,
					}
				],
				**overrides,
			}
		)
		doc.insert()
		return doc

	# ── the premise ─────────────────────────────────────────────────────────

	def test_the_shared_counter_is_still_how_frappe_works(self):
		"""The measurement this feature rests on, pinned.

		If a future Frappe keys the series counter by company, this feature is
		unnecessary — and this test failing is how we would find out, rather than
		carrying a workaround forever.
		"""
		self._invoice()
		rows = frappe.db.sql("SELECT name FROM `tabSeries` WHERE name LIKE %s", ("%SINV%",), as_dict=True)
		self.assertTrue(rows, "no Sales Invoice series counter exists at all")
		abbr = frappe.get_cached_value("Company", COMPANY, "abbr")
		default_rows = [r.name for r in rows if r.name.startswith("ACC-SINV")]
		self.assertTrue(default_rows, "the default series has no counter row")
		for name in default_rows:
			self.assertNotIn(
				abbr, name, f"{name} names a company — Frappe may now key the counter per company"
			)

	# ── off by default ──────────────────────────────────────────────────────

	def test_it_is_off_by_default_and_changes_nothing(self):
		"""An app upgrade must not renumber somebody's live invoices."""
		self._enable(0)
		doc = self._invoice()
		self.assertTrue(
			doc.name.startswith("ACC-SINV"),
			f"numbering changed with the flag off: {doc.name}",
		)

	def test_the_field_defaults_to_off_on_the_doctype(self):
		field = frappe.get_meta("Company").get_field(PER_COMPANY_NUMBERING_FIELD)
		self.assertIsNotNone(field, "the opt-in field was not installed")
		self.assertEqual(field.fieldtype, "Check")
		self.assertIn(flt(field.default or 0), (0.0,), "the field defaults to ON")

	# ── on ──────────────────────────────────────────────────────────────────

	def test_it_gives_the_company_its_own_prefix(self):
		self._enable()
		abbr = frappe.get_cached_value("Company", COMPANY, "abbr")
		slug = "".join(ch for ch in abbr if ch.isalnum()).upper()

		doc = self._invoice()
		self.assertTrue(
			doc.name.startswith(f"SINV-{slug}-"),
			f"expected a per-company prefix, got {doc.name}",
		)

	def _second_company(self) -> str:
		"""A second Lao company on the same site — the configuration the defect needs.

		One company never interleaves with itself, so a single-company test of
		"is the sequence contiguous" passes whether the feature works or not. It
		took two companies to make the defect observable, so it takes two to test it.
		"""
		name = "_Test Lao Co Two"
		if not frappe.db.exists("Warehouse Type", "Transit"):
			frappe.get_doc({"doctype": "Warehouse Type", "name": "Transit"}).insert(ignore_permissions=True)
		if not frappe.db.exists("Company", name):
			frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": name,
					"abbr": "_TLC2",
					"default_currency": "LAK",
					"country": frappe.db.get_value("Company", COMPANY, "country"),
				}
			).insert(ignore_permissions=True)
		return name

	def _invoice_for(self, company):
		doc = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": company,
				"customer": CUSTOMER,
				"currency": "LAK",
				"conversion_rate": 1,
				"set_posting_time": 1,
				"posting_date": self.posting_date,
				"debit_to": frappe.db.get_value(
					"Account", {"company": company, "account_type": "Receivable", "is_group": 0}, "name"
				),
				"items": [
					{
						"item_code": ITEM,
						"qty": 1,
						"rate": 1_000,
						"income_account": frappe.db.get_value(
							"Account", {"company": company, "root_type": "Income", "is_group": 0}, "name"
						),
						"cost_center": frappe.db.get_value(
							"Cost Center", {"company": company, "is_group": 0}, "name"
						),
					}
				],
			}
		)
		doc.insert()
		return doc

	@staticmethod
	def _counter(name):
		return int(name.rsplit("-", 1)[-1])

	def test_two_companies_interleave_without_this(self):
		"""The defect itself, reproduced. This is what the feature exists to stop.

		With the flag OFF, Company A's own invoice numbers are not consecutive —
		the gap between them belongs to a different legal entity.
		"""
		other = self._second_company()
		self._enable(0)

		a1 = self._invoice_for(COMPANY)
		self._invoice_for(other)
		a2 = self._invoice_for(COMPANY)

		self.assertTrue(a1.name.startswith("ACC-SINV") and a2.name.startswith("ACC-SINV"))
		self.assertEqual(
			self._counter(a2.name) - self._counter(a1.name),
			2,
			f"expected the other company to take a number in between: {a1.name}, {a2.name}",
		)

	def test_the_company_sequence_is_contiguous_with_this(self):
		"""The fix, against the same interleaving that breaks it without."""
		other = self._second_company()
		self._enable(1)

		a1 = self._invoice_for(COMPANY)
		self._invoice_for(other)  # the other company takes a number from its own pot
		a2 = self._invoice_for(COMPANY)

		self.assertEqual(
			self._counter(a2.name) - self._counter(a1.name),
			1,
			f"{a1.name} then {a2.name} — another company still took a number in between",
		)

	def test_it_opens_a_counter_of_its_own(self):
		"""Per-company means a separate row in tabSeries, not a filtered view."""
		self._enable()
		doc = self._invoice()
		prefix = doc.name.rsplit("-", 1)[0] + "-"
		self.assertTrue(
			frappe.db.exists("Series", prefix),
			f"no counter row for {prefix}; the sequence is not really its own",
		)

	def test_the_default_series_is_left_alone(self):
		"""Turning it on for one company must not disturb anyone else's numbering."""
		self._enable(0)
		before = self._invoice().name
		self._enable(1)
		self._invoice()
		self._enable(0)
		after = self._invoice().name

		self.assertTrue(before.startswith("ACC-SINV") and after.startswith("ACC-SINV"))
		self.assertEqual(
			int(after.rsplit("-", 1)[-1]) - int(before.rsplit("-", 1)[-1]),
			1,
			f"the shared counter moved while the flag was on: {before} then {after}",
		)

	# ── what it must not touch ──────────────────────────────────────────────

	def test_a_credit_note_gets_its_own_sequence(self):
		"""Returns must not merge into the invoice numbering.

		ERPNext separates them with -RET-; so do we, for the same reason an auditor
		wants them separate.
		"""
		abbr = frappe.get_cached_value("Company", COMPANY, "abbr")
		slug = "".join(ch for ch in abbr if ch.isalnum()).upper()
		self.assertEqual(lao_invoice_series(COMPANY, is_return=True), f"SINV-{slug}-RET-.YYYY.-")
		self.assertEqual(lao_invoice_series(COMPANY, is_return=False), f"SINV-{slug}-.YYYY.-")

	def test_an_amendment_keeps_erpnexts_naming(self):
		"""An amendment's name is derived from the document it amends.

		Rewriting it would break that link, so the hook returns early. Asserted on
		the hook directly, because building a real amendment needs a cancelled
		submitted invoice and this is the whole behaviour.
		"""
		self._enable()
		doc = frappe.get_doc(
			{"doctype": "Sales Invoice", "company": COMPANY, "amended_from": "ACC-SINV-2026-00001"}
		)
		doc.naming_series = "ACC-SINV-.YYYY.-"
		set_lao_invoice_series(doc)
		self.assertEqual(doc.naming_series, "ACC-SINV-.YYYY.-", "an amendment was renumbered")

	def test_a_non_lao_company_is_left_alone(self):
		from unittest.mock import patch

		import berp_lao.lao_regional.rules.sales_invoice as rules

		doc = frappe.get_doc({"doctype": "Sales Invoice", "company": COMPANY})
		doc.naming_series = "ACC-SINV-.YYYY.-"
		with patch.object(rules, "is_lao_company", return_value=False):
			rules.set_lao_invoice_series(doc)
		self.assertEqual(doc.naming_series, "ACC-SINV-.YYYY.-")

	def test_a_company_with_no_usable_abbreviation_gets_no_prefix(self):
		"""None rather than a prefix that would collide with another company's."""
		from unittest.mock import patch

		import berp_lao.lao_regional.rules.sales_invoice as rules

		with patch.object(rules.frappe, "get_cached_value", return_value="!!!"):
			self.assertIsNone(rules.lao_invoice_series(COMPANY))
