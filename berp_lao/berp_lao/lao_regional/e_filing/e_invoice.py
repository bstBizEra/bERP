# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
The internal representation of one Lao e-tax invoice.

The Ministry of Finance launched the E-Tax Invoice system on 29 May 2026 and
publishes no taxpayer-facing specification, so this is deliberately *not* modelled
on a wire format. It is modelled on what Lao statute requires a tax invoice to
carry, which is knowable and stable: who is selling, who is buying, what was sold,
the net, the VAT, and the total.

That is the same content the Lao Tax Invoice print format renders, which is the
point — a document a Lao inspector would accept on paper and a document fit to
transmit are the same document, so they are built from one representation rather
than two that can drift.

WHAT ``check()`` IS FOR
    It reports why this invoice is not fit to *issue*, while the invoice is still
    amendable. The rules it applies are statutory, not stylistic: a missing seller
    TIN, a missing buyer TIN above the 500,000 LAK threshold, VAT on a zero-rated
    export, a VAT amount that does not follow from the net. Each of those is a
    rejection or an assessment later, and each is cheap to fix now.

    An empty list does not mean the invoice is correct. It means it is internally
    consistent and carries the identifiers a Lao tax invoice needs.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate

from berp_lao.lao_regional.country import is_vat_registered
from berp_lao.lao_regional.rules import (
	NON_VATABLE_INVOICE_TYPES,
	TIN_REQUIRED_THRESHOLD_LAK,
	VAT_STANDARD_RATE,
)

SCHEMA_VERSION = "berp_lao.e_invoice.v1"

#: How far the computed VAT may differ from the invoice's own, in the invoice
#: currency, before it is reported. ERPNext rounds per row; a kip or two of
#: divergence on a many-line invoice is arithmetic, not a defect.
VAT_TOLERANCE = 1.0


@dataclasses.dataclass(frozen=True)
class EInvoiceLine:
	"""One line of the invoice, as a tax inspector reads it."""

	item_code: str | None
	description: str
	qty: float
	uom: str | None
	rate: float
	amount: float

	def as_dict(self) -> dict[str, Any]:
		return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class EInvoicePayload:
	"""One Lao tax invoice, ready to be serialised for whatever comes."""

	schema: str

	company: str
	seller_tax_id: str | None
	seller_registration: str | None

	invoice_no: str
	invoice_date: str
	invoice_type: str

	customer: str
	customer_tax_id: str | None

	currency: str
	conversion_rate: float

	lines: tuple[EInvoiceLine, ...]
	net_total: float
	vat_rate: float
	vat_amount: float
	grand_total: float
	base_grand_total: float
	grand_total_in_words: str | None

	is_vat_registered_seller: bool
	is_return: bool

	def as_dict(self) -> dict[str, Any]:
		data = dataclasses.asdict(self)
		data["lines"] = [line.as_dict() for line in self.lines]
		return data

	def check(self) -> list[str]:
		"""Reasons this invoice is not fit to issue. Empty is not a guarantee."""
		problems = []

		if not self.seller_tax_id:
			problems.append(_("The company has no Lao Tax ID (TIN) recorded."))

		if not self.lines:
			problems.append(_("The invoice has no lines."))

		if not self.invoice_date:
			problems.append(_("The invoice has no date."))

		vatable = self.invoice_type not in NON_VATABLE_INVOICE_TYPES

		# The TIN threshold is measured in kip, so on the base total.
		if vatable and not self.customer_tax_id and flt(self.base_grand_total) >= TIN_REQUIRED_THRESHOLD_LAK:
			problems.append(
				_("No customer Tax ID. Lao invoices of {0} LAK or more must record the buyer's TIN.").format(
					f"{TIN_REQUIRED_THRESHOLD_LAK:,}"
				)
			)

		if not vatable and flt(self.vat_amount):
			problems.append(
				_("This is a {0} invoice but it carries VAT of {1}.").format(
					self.invoice_type, self.vat_amount
				)
			)

		if vatable and self.is_vat_registered_seller:
			expected = flt(self.net_total * VAT_STANDARD_RATE / 100.0, 2)
			if abs(flt(self.vat_amount, 2) - expected) > VAT_TOLERANCE:
				problems.append(
					_("VAT of {0} does not follow from a net of {1} at {2}% (expected {3}).").format(
						self.vat_amount, self.net_total, VAT_STANDARD_RATE, expected
					)
				)

		if self.currency != "LAK" and not flt(self.conversion_rate):
			problems.append(_("The invoice is in {0} with no exchange rate to LAK.").format(self.currency))

		for label, value in (
			(_("Net total"), self.net_total),
			(_("VAT"), self.vat_amount),
			(_("Grand total"), self.grand_total),
		):
			# A credit note is negative throughout, and legitimately so.
			if not self.is_return and flt(value) < 0:
				problems.append(_("{0} is negative ({1}).").format(label, value))

		return problems


def build_e_invoice_payload(sales_invoice: str) -> EInvoicePayload:
	"""Build the payload for one Sales Invoice.

	Reads the submitted document rather than re-deriving anything: the numbers that
	would be transmitted are exactly the numbers on the invoice a human approved.
	"""
	doc = frappe.get_doc("Sales Invoice", sales_invoice)

	company = frappe.get_cached_doc("Company", doc.company)
	invoice_type = doc.get("lao_invoice_type") or "Standard"

	lines = tuple(
		EInvoiceLine(
			item_code=row.get("item_code"),
			description=(row.get("item_name") or row.get("description") or "").strip(),
			qty=flt(row.get("qty")),
			uom=row.get("uom"),
			rate=flt(row.get("rate")),
			amount=flt(row.get("amount")),
		)
		for row in (doc.get("items") or [])
	)

	return EInvoicePayload(
		schema=SCHEMA_VERSION,
		company=doc.company,
		seller_tax_id=company.get("lao_tax_id") or company.get("tax_id"),
		seller_registration=company.get("lao_business_registration"),
		invoice_no=doc.name,
		invoice_date=str(getdate(doc.posting_date)) if doc.get("posting_date") else "",
		invoice_type=invoice_type,
		customer=doc.customer,
		customer_tax_id=doc.get("lao_customer_tax_id")
		or frappe.db.get_value("Customer", doc.customer, "lao_tax_id"),
		currency=doc.currency,
		conversion_rate=flt(doc.get("conversion_rate")),
		lines=lines,
		net_total=flt(doc.get("net_total")),
		vat_rate=VAT_STANDARD_RATE,
		vat_amount=_vat_amount(doc),
		grand_total=flt(doc.get("grand_total")),
		base_grand_total=flt(doc.get("base_grand_total")),
		grand_total_in_words=doc.get("in_words"),
		is_vat_registered_seller=is_vat_registered(doc.company),
		is_return=bool(doc.get("is_return")),
	)


def _vat_amount(doc) -> float:
	"""Only standard-rate VAT rows, in invoice currency.

	The defect this avoids is the one the VAT report was fixed for: reading
	``total_taxes_and_charges`` from the header sums *every* row, so a freight line
	would be declared to the Revenue Department as VAT.
	"""
	total = 0.0
	for tax in doc.get("taxes") or []:
		if flt(tax.get("rate")) != VAT_STANDARD_RATE:
			continue
		if tax.get("category") == "Valuation":
			continue
		amount = flt(tax.get("tax_amount"))
		total += -amount if tax.get("add_deduct_tax") == "Deduct" else amount
	return flt(total, 2)
