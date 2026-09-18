# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
The withholding certificate — mirrors `lao_regional/certificates/withholding.py`.

Roadmap 2.3, unblocked by 1.2: withholding had to actually happen before there was
anything to certify.

Two of these are worth naming.

`test_a_list_party_still_breaks_the_upstream_report` is a **compatibility
characterization**, not a correctness test, in the sense docs/REVIEW-METHOD.md
sets out. It pins a defect in ERPNext, not in this app: `Tax Withholding Details`
raises a SQL syntax error when `party` is a list, which is what its own
MultiSelectList filter sends. A failure there means *upstream fixed it* — good
news, and a prompt to simplify — never that this app regressed.

`test_the_certificate_declares_no_font_face` carries ADR-A4 into a second
document. The tax invoice learned that lesson the expensive way; a certificate
rendered through the same wkhtmltopdf path would fail identically.
"""

import re

import frappe
from frappe.utils import add_days, flt

try:  # Frappe v16+
	from frappe.tests import IntegrationTestCase as _TestCase
except ImportError:  # Frappe v15
	from frappe.tests.utils import FrappeTestCase as _TestCase

from berp_lao.lao_regional.certificates.withholding import (
	STATUTE,
	WithholdingCertificate,
	build_withholding_certificate,
	withholding_certificate_html,
)
from berp_lao.lao_regional.lao_numbers import lao_money_in_words
from berp_lao.tests.fixtures import (
	COMPANY,
	ITEM,
	PRICE_LIST_BUYING,
	SUPPLIER,
	LaoVatReturnFixture,
)

FONT_FACE_RE = re.compile(r"@font-face\s*\{[^}]*\}")
COMMENT_RE = re.compile(r"/\*.*?\*/|\{#-?.*?-?#\}", re.DOTALL)
CATEGORY = "WHT - Services & Consulting 10% (ຮ.ຕ. ບໍລິການ)"


class TestWithholdingCertificate(LaoVatReturnFixture):
	NET_A = 1_000_000.0
	NET_B = 400_000.0
	RATE = 10.0

	def setUp(self):
		super().setUp()
		if not frappe.db.exists("Tax Withholding Category", CATEGORY):
			self.skipTest("the Lao withholding categories are not installed on this site")

		from berp_lao.setup.tax_templates import repair_withholding_thresholds

		repair_withholding_thresholds()

		# Withholding is period-cumulative per party, so every case gets its own
		# supplier. See the note in test_purchase_rules.
		self.supplier = (
			frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": f"_Test Lao Consultant {frappe.generate_hash(length=8)}",
					"supplier_group": frappe.db.get_value("Supplier", SUPPLIER, "supplier_group"),
					"tax_withholding_category": CATEGORY,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
		frappe.db.set_value("Supplier", self.supplier, "lao_tax_id", "1122334455")
		frappe.db.set_value("Company", COMPANY, "lao_tax_id", "9988776655")

		self.first = self._post(self.NET_A, self.posting_date)
		self.second = self._post(self.NET_B, add_days(self.posting_date, 3))

	def _post(self, amount, date):
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
				"posting_date": date,
				"due_date": add_days(date, 30),
				"credit_to": self.payable,
				"items": [
					{
						"item_code": ITEM,
						"qty": 1,
						"rate": amount,
						"expense_account": self.expense,
						"cost_center": self.cost_center,
					}
				],
			}
		)
		doc.insert()
		doc.submit()
		return doc

	def _certificate(self) -> WithholdingCertificate:
		return build_withholding_certificate(
			COMPANY, self.supplier, self.posting_date, add_days(self.posting_date, 10)
		)

	# ── the document ────────────────────────────────────────────────────────

	def test_it_carries_every_withholding_in_the_period(self):
		cert = self._certificate()
		self.assertEqual(len(cert.lines), 2, f"expected both invoices, got {cert.lines}")
		self.assertCountEqual(
			[flt(line.tax_amount, 2) for line in cert.lines],
			[flt(self.NET_A * self.RATE / 100, 2), flt(self.NET_B * self.RATE / 100, 2)],
		)

	def test_the_total_is_what_the_ledger_withheld(self):
		cert = self._certificate()
		expected = flt((self.NET_A + self.NET_B) * self.RATE / 100, 2)
		self.assertAlmostEqual(flt(cert.total_withheld, 2), expected, places=1)

		wht_account = frappe.db.get_value(
			"Account", {"company": COMPANY, "account_number": "4431", "is_group": 0}, "name"
		)
		posted = frappe.get_all(
			"GL Entry",
			filters={
				"company": COMPANY,
				"account": wht_account,
				"party": self.supplier,
				"is_cancelled": 0,
			},
			fields=["debit", "credit"],
		)
		credited = flt(sum(flt(r.credit) - flt(r.debit) for r in posted), 2)
		if posted:
			self.assertAlmostEqual(
				credited,
				flt(cert.total_withheld, 2),
				places=1,
				msg="the certificate does not agree with the withholding account",
			)

	def test_it_names_both_tax_identification_numbers(self):
		"""Without both, the supplier cannot use it to claim the credit."""
		cert = self._certificate()
		self.assertEqual(cert.agent_tax_id, "9988776655")
		self.assertEqual(cert.supplier_tax_id, "1122334455")

	def test_the_total_is_stated_in_lao_words(self):
		"""A Lao statutory document states the amount in words, and in Lao."""
		cert = self._certificate()
		self.assertEqual(
			cert.total_withheld_in_words,
			lao_money_in_words(cert.total_withheld, "LAK"),
		)
		self.assertTrue(
			any(0x0E80 <= ord(ch) <= 0x0EFF for ch in cert.total_withheld_in_words or ""),
			"the amount in words is not in Lao script",
		)

	def test_a_period_with_nothing_withheld_is_reported_not_invented(self):
		cert = build_withholding_certificate(
			COMPANY, self.supplier, add_days(self.posting_date, 400), add_days(self.posting_date, 430)
		)
		self.assertEqual(cert.lines, ())
		self.assertEqual(flt(cert.total_withheld), 0.0)
		self.assertTrue(any("Nothing was withheld" in p for p in cert.check()))

	def test_a_non_lao_company_is_refused(self):
		from unittest.mock import patch

		import berp_lao.lao_regional.certificates.withholding as mod

		with patch.object(mod, "is_lao_company", return_value=False):
			with self.assertRaises(frappe.ValidationError):
				self._certificate()

	# ── check() against known-bad input ─────────────────────────────────────

	def test_the_check_can_actually_fail(self):
		"""REVIEW-METHOD rule 8: run the validator where the answer must be no."""
		import dataclasses

		good = self._certificate()
		self.assertEqual(good.check(), [], f"the fixture certificate is not clean: {good.check()}")

		cases = {
			"no agent TIN": ({"agent_tax_id": None}, "withholding agent"),
			"no supplier TIN": ({"supplier_tax_id": None}, "no Lao Tax ID"),
			"period inverted": (
				{"period_from": good.period_to, "period_to": good.period_from},
				"after period end",
			),
			"total does not reconcile": (
				{"total_withheld": good.total_withheld + 5_000},
				"but the certificate states",
			),
			"no lines": ({"lines": ()}, "Nothing was withheld"),
		}
		for label, (mutation, needle) in cases.items():
			with self.subTest(case=label):
				problems = dataclasses.replace(good, **mutation).check()
				self.assertTrue(
					any(needle in p for p in problems),
					f"{label}: check() said {problems!r}, expected something about {needle!r}",
				)

	def test_a_rate_free_withholding_is_reported(self):
		"""An amount with no rate behind it cannot be evidenced by the recipient."""
		import dataclasses

		good = self._certificate()
		broken_lines = (dataclasses.replace(good.lines[0], rate=0.0), *good.lines[1:])
		problems = dataclasses.replace(good, lines=broken_lines).check()
		self.assertTrue(any("no stated rate" in p for p in problems), problems)

	# ── the rendered document ───────────────────────────────────────────────

	def test_the_certificate_declares_no_font_face(self):
		"""ADR-A4, carried into the second Lao document this app prints.

		On the supported wkhtmltopdf stack an @font-face rule overrides the
		fontconfig lookup, fails, and destroys the Lao text. The tax invoice
		learned this the expensive way; nothing else may repeat it.
		"""
		html = withholding_certificate_html(
			COMPANY, self.supplier, self.posting_date, add_days(self.posting_date, 10)
		)
		declarations = COMMENT_RE.sub("", html)
		self.assertEqual(FONT_FACE_RE.findall(declarations), [])
		self.assertNotIn("fonts.googleapis.com", declarations)
		self.assertNotIn("@import", declarations)

	def test_it_asks_for_the_lao_families_by_name(self):
		html = withholding_certificate_html(
			COMPANY, self.supplier, self.posting_date, add_days(self.posting_date, 10)
		)
		for family in ("Phetsarath", "Noto Sans Lao"):
			with self.subTest(family=family):
				self.assertIn(family, html)

	def test_the_rendered_document_carries_the_numbers_and_the_statute(self):
		html = withholding_certificate_html(
			COMPANY, self.supplier, self.posting_date, add_days(self.posting_date, 10)
		)
		cert = self._certificate()
		self.assertIn(STATUTE, html)
		self.assertIn("9988776655", html)
		self.assertIn("1122334455", html)
		self.assertIn(f"{cert.total_withheld:,.0f}", html)
		self.assertIn(cert.total_withheld_in_words, html)
		self.assertIn("ໃບຢັ້ງຢືນການຫັກພາສີ", html)

	def test_an_unfit_certificate_says_so_on_its_face(self):
		"""A document that should not be handed over must not look finished."""
		frappe.db.set_value("Supplier", self.supplier, "lao_tax_id", None)
		frappe.db.set_value("Supplier", self.supplier, "tax_id", None)
		frappe.clear_document_cache("Supplier", self.supplier)
		html = withholding_certificate_html(
			COMPANY, self.supplier, self.posting_date, add_days(self.posting_date, 10)
		)
		self.assertIn("NOT FIT TO ISSUE", html)

	# ── upstream characterization ───────────────────────────────────────────

	def test_a_list_party_still_breaks_the_upstream_report(self):
		"""Compatibility characterization — the defect is ERPNext's, not ours.

		`Tax Withholding Details` builds `IN ([%(param)s])` when `party` is a list,
		which is what its own MultiSelectList filter sends. A failure here means
		upstream fixed it, and `_report_rows` can stop working around it. It does
		NOT mean this app regressed.

		This test prints a MariaDB 1064 error to the log on a passing run. That is
		the defect being demonstrated, not a problem with the run — do not chase it.
		"""
		from erpnext.accounts.report.tax_withholding_details.tax_withholding_details import execute

		filters = frappe._dict(
			{
				"company": COMPANY,
				"party_type": "Supplier",
				"party": [self.supplier],
				"from_date": self.posting_date,
				"to_date": add_days(self.posting_date, 10),
			}
		)
		try:
			execute(filters)
		except Exception:
			return  # still broken upstream, as the workaround assumes
		self.fail(
			"ERPNext now accepts a list for `party` — the scalar workaround in "
			"certificates/withholding.py:_report_rows can be revisited, and this "
			"characterization updated to match what was measured."
		)

	def test_the_scalar_call_is_what_this_app_makes(self):
		"""Pins the workaround itself, so it cannot be 'tidied' into a list."""
		from unittest.mock import patch

		import berp_lao.lao_regional.certificates.withholding as mod

		seen = {}

		def spy(filters=None):
			seen["party"] = filters.get("party")
			return [], []

		with patch(
			"erpnext.accounts.report.tax_withholding_details.tax_withholding_details.execute",
			side_effect=spy,
		):
			mod._report_rows(COMPANY, self.supplier, self.posting_date, self.posting_date)

		self.assertIsInstance(seen["party"], str, "party must be a scalar; a list breaks upstream")
