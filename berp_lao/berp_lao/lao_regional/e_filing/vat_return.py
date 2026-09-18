# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
The internal representation of a Lao periodic VAT filing.

The taxpayer-facing surface for this is **DTax**, the Tax Department's registration
and filing portal — not TaxRIS, which is the administration's own internal system
and was never going to accept taxpayer submissions. That mistake is why this file
used to be called ``payload.py`` in a package called ``taxris``.

Deliberately *not* modelled on a wire format, because none is published. It is
modelled on what the Lao VAT return itself requires, which is stable: the taxpayer,
the period, and the split between standard-rated, zero-rated and exempt supplies,
against reclaimable input VAT.

Mapping this onto whatever is eventually accepted is a serialiser's job. Keeping
the two apart means a wire-format change never reaches the accounting code.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate

SCHEMA_VERSION = "berp_lao.vat_return.v1"


@dataclasses.dataclass(frozen=True)
class VatReturnPayload:
	"""One company's VAT position for one period."""

	schema: str
	company: str
	tax_id: str | None
	period_from: str
	period_to: str
	currency: str

	standard_sales_net: float
	standard_sales_vat: float
	export_sales_net: float
	exempt_sales_net: float
	total_output_vat: float

	purchases_net: float
	total_input_vat: float
	net_vat_payable: float

	sales_invoice_count: int
	purchase_invoice_count: int

	def as_dict(self) -> dict[str, Any]:
		return dataclasses.asdict(self)

	def check(self) -> list[str]:
		"""
		Return the reasons this payload is not fit to file, newest concern first.

		An empty list does not mean the return is correct — only that it is
		internally consistent and carries the identifiers a filing needs.
		"""
		problems = []

		if not self.tax_id:
			problems.append(_("The company has no Lao Tax ID (TIN) recorded."))

		if getdate(self.period_from) > getdate(self.period_to):
			problems.append(_("Period start is after period end."))

		expected_net = flt(self.total_output_vat - self.total_input_vat, 2)
		if flt(self.net_vat_payable, 2) != expected_net:
			problems.append(
				_("Net VAT ({0}) does not equal output VAT minus input VAT ({1}).").format(
					self.net_vat_payable, expected_net
				)
			)

		if self.export_sales_net and flt(self.standard_sales_vat) and not self.standard_sales_net:
			problems.append(_("Output VAT is present with no standard-rated sales behind it."))

		for label, value in (
			(_("Standard sales"), self.standard_sales_net),
			(_("Export sales"), self.export_sales_net),
			(_("Exempt sales"), self.exempt_sales_net),
			(_("Purchases"), self.purchases_net),
		):
			if flt(value) < 0:
				problems.append(_("{0} is negative ({1}).").format(label, value))

		return problems


def build_vat_return_payload(company: str, from_date: str, to_date: str) -> VatReturnPayload:
	"""
	Build a filing payload from the same query the Lao Monthly VAT Return uses.

	Reusing the report is the point: the numbers that would be filed are exactly
	the numbers a human reviewed on screen, rather than a second implementation
	that can drift from it.
	"""
	from berp_lao.lao_regional.report.lao_vat_return.lao_vat_return import (
		_input_vat,
		_output_vat,
		_purchases_net,
		_sales_net_by_type,
	)

	filters = frappe._dict({"company": company, "from_date": from_date, "to_date": to_date})

	sales = _sales_net_by_type(filters)
	purchases = _purchases_net(filters)
	output_vat = _output_vat(filters)
	input_vat = _input_vat(filters)

	def net(invoice_type):
		return flt((sales.get(invoice_type) or {}).get("net_total"))

	def count(invoice_type):
		return int(flt((sales.get(invoice_type) or {}).get("invoice_count")))

	standard_net = net("Standard") + net("Simplified")
	standard_count = count("Standard") + count("Simplified")

	return VatReturnPayload(
		schema=SCHEMA_VERSION,
		company=company,
		tax_id=frappe.db.get_value("Company", company, "lao_tax_id"),
		period_from=str(getdate(from_date)),
		period_to=str(getdate(to_date)),
		currency=frappe.get_cached_value("Company", company, "default_currency"),
		standard_sales_net=standard_net,
		standard_sales_vat=output_vat,
		export_sales_net=net("Export (0%)"),
		exempt_sales_net=net("VAT Exempt"),
		total_output_vat=output_vat,
		purchases_net=flt(purchases.get("net_total")),
		total_input_vat=input_vat,
		net_vat_payable=flt(output_vat - input_vat),
		sales_invoice_count=standard_count + count("Export (0%)") + count("VAT Exempt"),
		purchase_invoice_count=int(flt(purchases.get("invoice_count"))),
	)
