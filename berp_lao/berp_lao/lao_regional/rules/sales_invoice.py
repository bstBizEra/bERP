# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""Lao rules on the Sales Invoice."""

import json

import frappe
from frappe import _
from frappe.utils import flt

from berp_lao.lao_regional.country import is_lao_company, is_vat_registered
from berp_lao.lao_regional.rules import (
	NON_VATABLE_INVOICE_TYPES,
	TIN_REQUIRED_THRESHOLD_LAK,
	VAT_STANDARD_RATE,
)

#: Company field that opts into a per-company invoice sequence.
PER_COMPANY_NUMBERING_FIELD = "lao_per_company_invoice_numbering"


def set_lao_invoice_series(doc, method=None):
	"""doc_events → Sales Invoice → before_naming

	Give a Lao company its own invoice sequence, when it has asked for one.

	WHY THIS EXISTS
	    Frappe keeps **one counter per naming-series prefix per SITE**. Measured:
	    ``tabSeries`` holds a single row ``ACC-SINV-2026-`` and the company appears
	    nowhere in the key. So two companies on one site take numbers from the same
	    pot and interleave —

	        Company A   ACC-SINV-2026-00001
	        Company B   ACC-SINV-2026-00002
	        Company A   ACC-SINV-2026-00003

	    — and neither has a contiguous sequence of its own. An auditor reading
	    Company A's invoice book sees holes belonging to a different legal entity.
	    That is awkward under any numbering rule, which is why this needs no answer
	    to BERP-LAO-QUESTIONS-001 Q9 before being worth fixing.

	    BizEra.la is one site per tenant, but a tenant may run several companies —
	    ADR-A1's config-placement rule says so explicitly. This is that case.

	OFF BY DEFAULT, AND DELIBERATELY
	    Switching a live company's numbering starts a new sequence at 1 while its
	    existing invoices keep their old numbers. That is a one-off discontinuity an
	    accountant should agree to, not something an app upgrade does to them.

	WHAT IT DOES NOT TOUCH
	    An amendment keeps ERPNext's ``-1`` convention — its name is derived from the
	    document it amends, and rewriting it would break that link. Returns get their
	    own ``-RET-`` sequence, as ERPNext does, so credit notes never merge into the
	    invoice numbering.

	The series set here need not appear in the ``naming_series`` Select: measured,
	Frappe accepts it and opens a counter row for it. The consequence is that for a
	company with this on, the Desk's naming-series dropdown is not the thing that
	decides — this hook is. The field description says so.
	"""
	if doc.get("amended_from"):
		return  # ERPNext derives an amendment's name from its original
	if not is_lao_company(doc.get("company")):
		return
	if not frappe.get_cached_value("Company", doc.company, PER_COMPANY_NUMBERING_FIELD):
		return

	prefix = lao_invoice_series(doc.company, is_return=bool(doc.get("is_return")))
	if prefix:
		doc.naming_series = prefix


def lao_invoice_series(company: str, is_return: bool = False) -> str | None:
	"""``SINV-<ABBR>-.YYYY.-``, or the ``-RET-`` variant for a credit note.

	Derived from the company abbreviation, which is what makes the sequence
	per-company. Non-alphanumerics are stripped because the abbreviation becomes
	part of a series key, and a company with no usable abbreviation gets None
	rather than a prefix that collides with another company's.
	"""
	abbr = frappe.get_cached_value("Company", company, "abbr") or ""
	slug = "".join(ch for ch in abbr if ch.isalnum()).upper()
	if not slug:
		return None
	return f"SINV-{slug}-RET-.YYYY.-" if is_return else f"SINV-{slug}-.YYYY.-"


def validate_lao_sales_invoice(doc, method=None):
	"""doc_events → Sales Invoice → validate"""
	if not is_lao_company(doc.company):
		return

	_warn_if_vat_missing(doc)
	_warn_if_customer_tin_missing(doc)
	_warn_if_lines_contradict_the_invoice_type(doc)


def _warn_if_vat_missing(doc):
	"""A Standard or Simplified Lao invoice should carry a 10% VAT row."""
	if not is_vat_registered(doc.company):
		return  # micro-enterprise: no VAT to charge, so no row to miss

	invoice_type = doc.get("lao_invoice_type") or "Standard"
	if invoice_type in NON_VATABLE_INVOICE_TYPES:
		return

	if any(flt(tax.rate) == VAT_STANDARD_RATE for tax in (doc.taxes or [])):
		return

	frappe.msgprint(
		_(
			"This is a Lao {0} invoice but it has no 10% VAT row. Add "
			"'VAT 10% (ອາກອນ 10%)' to the taxes table, or set the Invoice Type to "
			"'Export (0%)' or 'VAT Exempt'."
		).format(invoice_type),
		indicator="orange",
		title=_("Lao VAT Notice"),
	)


def _warn_if_customer_tin_missing(doc):
	"""Invoices at or above the TIN threshold should record the customer's TIN."""
	invoice_type = doc.get("lao_invoice_type") or "Standard"
	if invoice_type in NON_VATABLE_INVOICE_TYPES:
		return

	if flt(doc.get("base_grand_total")) < TIN_REQUIRED_THRESHOLD_LAK:
		return

	if doc.get("lao_customer_tax_id"):
		return

	frappe.msgprint(
		_(
			"For invoices of {0} LAK or more, the customer's Lao Tax ID "
			"(ເລກປະຈຳຕົວ) should be recorded for VAT compliance."
		).format(frappe.format_value(TIN_REQUIRED_THRESHOLD_LAK, {"fieldtype": "Int"})),
		indicator="orange",
		title=_("Lao Tax Compliance"),
	)


def _warn_if_lines_contradict_the_invoice_type(doc):
	"""A zero-rated invoice carrying a taxed line, or the reverse.

	Since the VAT return classifies **per line**, an Item Tax Template on a line
	overrides the invoice type for that line — which is the point, and is how a
	mixed invoice becomes representable. But a header that says "VAT Exempt" over
	a line taxed at 10% is almost always a mistake rather than an intention, and
	the return will quietly declare the two apart.

	Warn, do not block: a genuinely mixed invoice is legitimate, and only the
	person issuing it knows which of the two they meant.
	"""
	invoice_type = doc.get("lao_invoice_type") or "Standard"
	taxed, zero_rated = [], []

	for row in doc.get("items") or []:
		rate = _line_vat_rate(row)
		if rate is None:
			continue
		(taxed if rate > 0 else zero_rated).append(row.item_code or row.idx)

	if invoice_type in NON_VATABLE_INVOICE_TYPES and taxed:
		frappe.msgprint(
			_(
				"This invoice is marked {0} but {1} carries VAT at {2}%. The VAT return "
				"classifies each line on its own, so those lines will be declared as "
				"standard-rated while the rest are not."
			).format(invoice_type, ", ".join(str(i) for i in taxed), VAT_STANDARD_RATE),
			indicator="orange",
			title=_("Lao VAT Notice"),
		)
	elif invoice_type not in NON_VATABLE_INVOICE_TYPES and zero_rated:
		frappe.msgprint(
			_(
				"This is a {0} invoice, but {1} is zero-rated by its Item Tax Template. "
				"Those lines will be declared as exempt rather than standard-rated."
			).format(invoice_type, ", ".join(str(i) for i in zero_rated)),
			indicator="blue",
			title=_("Lao VAT Notice"),
		)


def _line_vat_rate(row):
	"""The VAT rate an Item Tax Template puts on this line, or None if none does."""
	raw = row.get("item_tax_rate")
	if not raw:
		return None
	try:
		rates = json.loads(raw)
	except (TypeError, ValueError):
		return None
	if not isinstance(rates, dict):
		return None
	for account, rate in rates.items():
		if frappe.get_cached_value("Account", account, "account_type") == "Tax":
			return flt(rate)
	return None


def sales_invoice_on_submit(doc, method=None):
	"""doc_events → Sales Invoice → on_submit"""
	if not is_lao_company(doc.company):
		return

	# Future: e-tax-invoice issuance queue (lao_regional.e_filing); bOPEN outbox.
	frappe.logger("berp_lao").info(f"berp_lao: Sales Invoice {doc.name} submitted (Laos).")


def sales_invoice_on_cancel(doc, method=None):
	"""doc_events → Sales Invoice → on_cancel"""
	if not is_lao_company(doc.company):
		return

	frappe.logger("berp_lao").info(f"berp_lao: Sales Invoice {doc.name} cancelled (Laos).")
