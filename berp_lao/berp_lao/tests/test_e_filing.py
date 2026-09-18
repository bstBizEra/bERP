# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
The Lao government filing seams — mirrors `lao_regional/e_filing/`.

This package shipped 312 lines with **no tests at all**, which was defensible only
while nobody could reach it. Two of them are worth naming:

`test_an_unconfigured_transport_is_never_live` is the safety property. Anything not
explicitly configured must resolve to the inert recorder, so that a misspelt key
cannot submit to a tax authority. It is the single assertion that makes the rest of
this package safe to build on.

`test_the_check_can_actually_fail` applies REVIEW-METHOD rule 8 to `check()`: a
validator that has only ever been run against valid input has not been shown to
distinguish the cases.
"""

import frappe
from frappe.utils import add_days, flt

from berp_lao.lao_regional.e_filing import (
	EInvoicePayload,
	EInvoiceTransport,
	LaoFilingError,
	LaoFilingNotConfigured,
	RecordingClient,
	VatReturnTransport,
	build_e_invoice_payload,
	build_vat_return_payload,
	get_client,
)
from berp_lao.lao_regional.e_filing.client import CONFIG_KEYS
from berp_lao.lao_regional.rules import TIN_REQUIRED_THRESHOLD_LAK, VAT_STANDARD_RATE
from berp_lao.tests.fixtures import (
	COMPANY,
	EXPECTED_INPUT_VAT,
	EXPECTED_OUTPUT_VAT,
	LaoVatReturnFixture,
)


class TestTransportResolution(LaoVatReturnFixture):
	"""The failure direction is chosen: unconfigured means record, never send."""

	def test_an_unconfigured_transport_is_never_live(self):
		for kind in ("vat_return", "e_invoice"):
			with self.subTest(kind=kind):
				self.assertNotIn(CONFIG_KEYS[kind], frappe.conf, "test site must be unconfigured")
				client = get_client(kind)
				self.assertIsInstance(client, RecordingClient)
				self.assertFalse(client.is_live, "an unconfigured transport must never be live")

	def test_the_two_surfaces_have_separate_keys(self):
		"""DTax and the E-Tax Invoice system are different systems, differently configured."""
		self.assertEqual(len(set(CONFIG_KEYS.values())), len(CONFIG_KEYS))

	def test_an_unknown_surface_is_refused(self):
		with self.assertRaises(LaoFilingNotConfigured):
			get_client("nonexistent_surface")

	def test_a_transport_of_the_wrong_kind_is_refused(self):
		"""A DTax client configured as the e-invoice client must not be accepted."""

		class OnlyVatReturn(VatReturnTransport):
			def submit_vat_return(self, payload):
				return {}

		dotted = f"{__name__}.{OnlyVatReturn.__qualname__}"
		frappe.conf[CONFIG_KEYS["e_invoice"]] = dotted
		try:
			with self.assertRaises(LaoFilingNotConfigured):
				get_client("e_invoice")
		finally:
			frappe.conf.pop(CONFIG_KEYS["e_invoice"], None)

	def test_a_dotted_path_that_does_not_import_raises_rather_than_falling_back(self):
		"""A named-but-broken transport is a misconfiguration, not a default.

		Silently recording here would hide a real mistake behind the same quiet
		success as the intended default.
		"""
		frappe.conf[CONFIG_KEYS["vat_return"]] = "no.such.module.Client"
		try:
			with self.assertRaises(LaoFilingNotConfigured):
				get_client("vat_return")
		finally:
			frappe.conf.pop(CONFIG_KEYS["vat_return"], None)

	def test_the_recorder_satisfies_both_interfaces(self):
		self.assertIsInstance(RecordingClient(), VatReturnTransport)
		self.assertIsInstance(RecordingClient(), EInvoiceTransport)


class TestVatReturnPayload(LaoVatReturnFixture):
	def test_it_carries_the_numbers_the_report_shows(self):
		"""One representation, not two that can drift."""
		payload = build_vat_return_payload(COMPANY, self.posting_date, add_days(self.posting_date, 27))
		self.assertEqual(flt(payload.total_output_vat, 2), flt(EXPECTED_OUTPUT_VAT, 2))
		self.assertEqual(flt(payload.total_input_vat, 2), flt(EXPECTED_INPUT_VAT, 2))
		self.assertEqual(
			flt(payload.net_vat_payable, 2),
			flt(EXPECTED_OUTPUT_VAT - EXPECTED_INPUT_VAT, 2),
		)

	def test_a_consistent_return_reports_no_problems(self):
		payload = build_vat_return_payload(COMPANY, self.posting_date, add_days(self.posting_date, 27))
		self.assertEqual(
			[p for p in payload.check() if "Tax ID" not in p],
			[],
			"a consistent return should report nothing but a missing TIN on the fixture",
		)

	def test_the_recorder_refuses_a_return_that_is_not_fit_to_file(self):
		payload = build_vat_return_payload(COMPANY, add_days(self.posting_date, 27), self.posting_date)
		with self.assertRaises(LaoFilingError):
			RecordingClient().submit_vat_return(payload)


class TestEInvoicePayload(LaoVatReturnFixture):
	def _standard_invoices(self) -> list[str]:
		return frappe.get_all(
			"Sales Invoice",
			filters={"company": COMPANY, "docstatus": 1, "lao_invoice_type": "Standard"},
			pluck="name",
			order_by="name",
		)

	def _payload(self, invoice=None) -> EInvoicePayload:
		"""A standard Lao invoice from the fixture, by name or the first one.

		Resolved from the database rather than from a class attribute: the fixture
		short-circuits `post_invoices` when the invoices already exist for the run,
		so `cls.si_a` is set for the first class through and not for the rest.
		"""
		if not invoice:
			names = self._standard_invoices()
			self.assertTrue(names, "the fixture posts no standard Lao sales invoice")
			invoice = names[0]
		return build_e_invoice_payload(invoice)

	def _invoice_with_a_non_vat_charge(self) -> str:
		"""The fixture's regression invoice: a VAT row *and* a freight row."""
		for name in self._standard_invoices():
			doc = frappe.get_doc("Sales Invoice", name)
			vat = [t for t in doc.taxes if flt(t.rate) == VAT_STANDARD_RATE]
			other = [t for t in doc.taxes if flt(t.rate) != VAT_STANDARD_RATE and flt(t.tax_amount)]
			if vat and other:
				return name
		self.fail(
			"no fixture invoice carries a non-VAT charge beside the VAT row — "
			"the regression this test exists for can no longer be observed"
		)

	def test_it_reads_the_invoice_rather_than_re_deriving_it(self):
		payload = self._payload()
		doc = frappe.get_doc("Sales Invoice", payload.invoice_no)
		self.assertEqual(payload.customer, doc.customer)
		self.assertEqual(flt(payload.grand_total, 2), flt(doc.grand_total, 2))
		self.assertTrue(payload.lines)
		self.assertEqual(len(payload.lines), len(doc.items))

	def test_vat_excludes_non_vat_charges(self):
		"""The regression the VAT report was fixed for, in its second home.

		Reading `total_taxes_and_charges` off the header sums *every* row, so a
		freight line would be transmitted to the Revenue Department as VAT.

		The invoice is found by the property under test — carries a VAT row *and* a
		non-VAT charge — rather than by "the largest one". Picking by size got a
		clean invoice and failed on correct output: a test defect, not a product one,
		and the second time in this repository that an instrument encoded a proxy for
		its own question.
		"""
		payload = self._payload(self._invoice_with_a_non_vat_charge())
		doc = frappe.get_doc("Sales Invoice", payload.invoice_no)

		header_sum = flt(doc.get("total_taxes_and_charges"))
		expected_vat = flt(payload.net_total * VAT_STANDARD_RATE / 100.0, 2)

		self.assertAlmostEqual(flt(payload.vat_amount, 2), expected_vat, places=1)
		self.assertGreater(
			flt(header_sum, 2),
			flt(payload.vat_amount, 2),
			"the header sum should exceed the VAT — that is what makes it a trap",
		)
		self.assertNotEqual(
			flt(payload.vat_amount, 2),
			flt(header_sum, 2),
			"VAT equals the header sum — a non-VAT charge is being declared as VAT",
		)

	def test_the_check_can_actually_fail(self):
		"""Known-bad cases, REVIEW-METHOD rule 8.

		Each mutation below breaks exactly one statutory requirement, and `check()`
		must name it. A validator only ever run against valid input has not been
		shown to distinguish the cases.
		"""
		import dataclasses

		good = self._payload()

		cases = {
			"seller TIN": ({"seller_tax_id": None}, "Tax ID"),
			"no lines": ({"lines": ()}, "no lines"),
			"buyer TIN above threshold": (
				{
					"customer_tax_id": None,
					"base_grand_total": float(TIN_REQUIRED_THRESHOLD_LAK) + 1,
				},
				"Tax ID",
			),
			"VAT on an export": (
				{"invoice_type": "Export (0%)", "vat_amount": 1_000.0},
				"carries VAT",
			),
			"VAT that does not follow from the net": (
				{"net_total": 1_000_000.0, "vat_amount": 7_000.0},
				"does not follow",
			),
			"foreign currency with no rate": (
				{"currency": "USD", "conversion_rate": 0.0},
				"exchange rate",
			),
		}
		for label, (mutation, needle) in cases.items():
			with self.subTest(case=label):
				broken = dataclasses.replace(good, **mutation)
				problems = broken.check()
				self.assertTrue(
					any(needle in p for p in problems),
					f"{label}: check() said {problems!r}, expected something about {needle!r}",
				)

	def test_a_credit_note_may_be_negative(self):
		"""A return is negative throughout, and legitimately so."""
		import dataclasses

		good = self._payload()
		credit = dataclasses.replace(
			good,
			is_return=True,
			net_total=-good.net_total,
			vat_amount=-good.vat_amount,
			grand_total=-good.grand_total,
		)
		self.assertEqual(
			[p for p in credit.check() if "negative" in p],
			[],
			"a credit note must not be rejected for being negative",
		)

	def test_the_recorder_records_and_submits_nothing(self):
		"""The happy path, made happy rather than skipped.

		The fixture company has no TIN — nothing in the test suite needs one — so the
		payload built from it is correctly refused. Filling in the identifiers here
		exercises the path that matters instead of skipping past it.
		"""
		import dataclasses

		fit = dataclasses.replace(
			self._payload(),
			seller_tax_id="1234567890",
			customer_tax_id="0987654321",
		)
		self.assertEqual(fit.check(), [], "the payload is still not fit to issue")

		receipt = RecordingClient().issue_e_invoice(fit)
		self.assertEqual(receipt["status"], "recorded")
		self.assertEqual(receipt["kind"], "e_invoice")
		self.assertEqual(receipt["invoice_no"], fit.invoice_no)
		self.assertFalse(RecordingClient().is_live)

	def test_the_recorder_refuses_an_invoice_that_is_not_fit_to_issue(self):
		import dataclasses

		unfit = dataclasses.replace(self._payload(), seller_tax_id=None)
		with self.assertRaises(LaoFilingError):
			RecordingClient().issue_e_invoice(unfit)

	def test_no_module_in_this_package_ships_an_http_client(self):
		"""Nothing here may reach the network until an interface is published."""
		import os

		package = os.path.dirname(frappe.get_module("berp_lao.lao_regional.e_filing").__file__)
		for filename in sorted(os.listdir(package)):
			if not filename.endswith(".py"):
				continue
			with open(os.path.join(package, filename), encoding="utf-8") as handle:
				source = handle.read()
			with self.subTest(module=filename):
				for forbidden in ("import requests", "urllib.request", "http.client", "httpx"):
					self.assertNotIn(forbidden, source, f"{filename} reaches the network")
