# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""Lao rules on the Purchase Invoice.

Two of the three below are about money the business loses *later* — a
non-deductible expense, a refused input-VAT claim — which ERPNext posts happily and
nobody discovers until the return is assessed. That is the reason they exist here
rather than in a report.
"""

import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate

from berp_lao.lao_regional.country import is_lao_company, is_vat_registered
from berp_lao.lao_regional.rules import (
	BANK_SETTLEMENT_THRESHOLD_LAK,
	CASH_MODE_TYPES,
	INPUT_VAT_CLAIM_WINDOW_MONTHS,
	VAT_STANDARD_RATE,
)


def apply_lao_withholding_defaults(doc, method=None):
	"""doc_events → Purchase Invoice → before_validate

	Reproduce ERPNext's own withholding default on the path where it does not run.

	`PurchaseInvoice.set_missing_values(for_validate=False)` sets `apply_tds = 1` and
	copies the supplier's `tax_withholding_category` onto the invoice. That call
	happens on the **form** path, which is why `purchase_invoice.js` can read
	`__onload.supplier_tds`. A scripted insert — an integration, an import, a test —
	goes through `validate()`, which calls `set_missing_values(for_validate=True)`,
	and the withholding block is skipped. Measured on this stack, 2026-09-16: a
	Purchase Invoice inserted for a supplier carrying a category came back with
	`apply_tds = 0`, `tax_withholding_category = None`, no tax row and no WHT ledger
	entry.

	So this runs `before_validate`, which is before ERPNext's `set_tax_withholding`,
	and only on a **new** document. Not on later saves: unticking `apply_tds` in the
	Desk clears `tax_withholding_category` too (`purchase_invoice.js`), so a rule
	that fired on every save would put both back and fight the user.
	"""
	if not doc.is_new():
		return
	if not is_lao_company(doc.get("company")):
		return
	if doc.get("apply_tds") or doc.get("tax_withholding_category"):
		return  # the Desk, or a caller who has already decided
	if not doc.get("supplier"):
		return

	category = frappe.db.get_value("Supplier", doc.supplier, "tax_withholding_category")
	if not category:
		return

	doc.apply_tds = 1
	doc.tax_withholding_category = category


def validate_lao_purchase_invoice(doc, method=None):
	"""doc_events → Purchase Invoice → validate"""
	if not is_lao_company(doc.company):
		return

	_warn_if_wht_missing(doc)
	_warn_if_cash_settled_above_threshold(doc)
	_warn_if_input_vat_claim_window_missed(doc)


def _warn_if_wht_missing(doc):
	"""Service purchases from Lao residents usually attract 10% WHT.

	By the time this runs, `apply_lao_withholding_defaults` has already copied the
	supplier's category onto a new invoice, so reaching this message means the
	*supplier* carries no category — which is the thing to fix, and the message now
	says so.
	"""
	if doc.get("apply_tds") or doc.get("tax_withholding_category"):
		return

	if not _has_service_items(doc):
		return

	frappe.msgprint(
		_(
			"No Withholding Tax category is set on this Purchase Invoice. If this is a "
			"service purchase from a Lao resident, WHT 10% "
			"(ອາກອນຫັກ ທີ່ແຫຼ່ງ 10%) may apply. Set a Withholding Tax Category on "
			"supplier {0} and it will be applied automatically from then on."
		).format(doc.get("supplier") or ""),
		indicator="blue",
		title=_("Lao WHT Notice"),
	)


def _warn_if_cash_settled_above_threshold(doc):
	"""Expenses over 1,000,000 LAK per invoice must be paid through a Lao bank.

	Law on Income Tax No. 88/NA, in force 1 July 2026. Cash settlement above the
	threshold does not invalidate the invoice — it makes the expense
	non-deductible for corporate income tax, which nothing in ERPNext would
	otherwise surface until the tax return is prepared.
	"""
	if not doc.get("is_paid"):
		return

	base_total = flt(doc.get("base_grand_total")) or flt(doc.get("base_net_total"))
	if base_total < BANK_SETTLEMENT_THRESHOLD_LAK:
		return

	mode = doc.get("mode_of_payment")
	if not mode:
		return
	if frappe.get_cached_value("Mode of Payment", mode, "type") not in CASH_MODE_TYPES:
		return

	frappe.msgprint(
		_(
			"This invoice is settled in cash for {0}, above the "
			"{1} LAK threshold. Under the Income Tax Law (No. 88/NA) an expense "
			"above that amount is deductible only if it is paid through a Lao "
			"commercial bank account."
		).format(
			frappe.format_value(base_total, {"fieldtype": "Currency"}),
			f"{BANK_SETTLEMENT_THRESHOLD_LAK:,}",
		),
		indicator="orange",
		title=_("Lao Deductibility Notice"),
	)


def _warn_if_input_vat_claim_window_missed(doc):
	"""Input VAT is claimable only within three months of the date incurred.

	The date incurred is the supplier's invoice date (`bill_date`), not the date
	this document is posted — a purchase booked late is exactly the case that
	misses the window. ERPNext will happily post the claim; the Revenue Department
	simply refuses it, and nobody finds out until the return is assessed.
	"""
	if not is_vat_registered(doc.company):
		return

	incurred = doc.get("bill_date")
	if not incurred:
		return  # nothing to measure against; the posting date is not the same thing

	incurred = getdate(incurred)
	posting = getdate(doc.get("posting_date"))
	if not posting or posting <= add_months(incurred, INPUT_VAT_CLAIM_WINDOW_MONTHS):
		return

	if not _has_input_vat(doc):
		return

	frappe.msgprint(
		_(
			"This invoice claims input VAT incurred on {0} but is posted on {1}, more "
			"than {2} months later. Lao input VAT is claimable only within {2} months "
			"of the date incurred, so this claim is likely to be refused."
		).format(
			frappe.format_value(incurred, {"fieldtype": "Date"}),
			frappe.format_value(posting, {"fieldtype": "Date"}),
			INPUT_VAT_CLAIM_WINDOW_MONTHS,
		),
		indicator="red",
		title=_("Lao Input VAT Window"),
	)


def _has_input_vat(doc) -> bool:
	"""True when any tax row is standard-rate VAT that is not capitalised."""
	for tax in doc.get("taxes") or []:
		if flt(tax.rate) != VAT_STANDARD_RATE:
			continue
		if tax.get("category") == "Valuation":
			continue  # capitalised into the item cost, never claimed back
		if tax.get("add_deduct_tax") == "Deduct":
			continue
		return True
	return False


def _has_service_items(doc) -> bool:
	"""True when any line is a non-stock item, which stands in for 'a service'."""
	for row in doc.get("items") or []:
		if not row.item_code:
			continue
		if not frappe.get_cached_value("Item", row.item_code, "is_stock_item"):
			return True
	return False
