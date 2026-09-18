# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Withholding tax certificate — roadmap 2.3.

A Lao supplier who has had tax withheld is paid net, and needs a statement from
the withholding agent saying so. Without it the supplier cannot evidence the
credit: the money has left them and the paperwork that proves where it went sits
in someone else's ledger.

WHERE THE NUMBERS COME FROM
    ERPNext already ships ``Tax Withholding Details``, and measured against Lao
    data it is correct — right party, right rate, right amounts, right invoices.
    So this module does not re-query the ledger. It calls that report and shapes
    the result into a document, for the same reason ``e_filing/vat_return.py``
    reuses the VAT report's own queries: one representation cannot drift from
    itself, and two can.

    What this adds is everything the report is not: both tax identification
    numbers, the statutory citation, the total in Lao words, and a form a
    supplier can be handed.

ONE UPSTREAM DEFECT THIS WORKS AROUND
    ``Tax Withholding Details`` raises a SQL syntax error when ``party`` is a
    list — which is exactly what its own MultiSelectList filter sends from the
    Desk. Measured on ERPNext v15, one supplier, everything else identical:

        party="_Probe Lao Consultant"    2 rows, rates and amounts correct
        party=["_Probe Lao Consultant"]  ProgrammingError 1064, IN ([%(param)s])

    So :func:`_report_rows` passes a scalar, always, and a test pins that. This
    is a workaround for somebody else's bug, not a preference — if a future
    ERPNext fixes it, the scalar still works and the test still passes.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate

from berp_lao.lao_regional.country import is_lao_company
from berp_lao.lao_regional.lao_numbers import lao_money_in_words

SCHEMA_VERSION = "berp_lao.withholding_certificate.v1"

#: The governing statute, printed on the certificate so the recipient can cite it.
STATUTE = "Law on Income Tax No. 88/NA"

#: Rounding tolerance when the line amounts are reconciled against the total, in
#: the company's currency. ERPNext rounds per row; a kip either way on a
#: many-invoice certificate is arithmetic, not a discrepancy.
RECONCILIATION_TOLERANCE = 1.0

TEMPLATE = "berp_lao/lao_regional/certificates/templates/lao_withholding_certificate.html"


@dataclasses.dataclass(frozen=True)
class WithholdingLine:
	"""One withholding event, as the supplier needs to see it."""

	voucher_type: str
	voucher_no: str
	posting_date: str
	supplier_invoice_no: str | None
	category: str | None
	net_amount: float
	rate: float
	tax_amount: float

	def as_dict(self) -> dict[str, Any]:
		return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class WithholdingCertificate:
	"""What one supplier had withheld by one company over one period."""

	schema: str
	statute: str

	company: str
	agent_tax_id: str | None
	agent_registration: str | None

	supplier: str
	supplier_name: str
	supplier_tax_id: str | None

	period_from: str
	period_to: str
	currency: str

	lines: tuple[WithholdingLine, ...]
	total_net: float
	total_withheld: float
	total_withheld_in_words: str | None

	def as_dict(self) -> dict[str, Any]:
		data = dataclasses.asdict(self)
		data["lines"] = [line.as_dict() for line in self.lines]
		return data

	def check(self) -> list[str]:
		"""Reasons this certificate is not fit to issue. Empty is not a guarantee."""
		problems = []

		if not self.agent_tax_id:
			problems.append(_("The withholding agent ({0}) has no Lao Tax ID recorded.").format(self.company))

		if not self.supplier_tax_id:
			problems.append(
				_(
					"Supplier {0} has no Lao Tax ID. The supplier cannot claim the credit "
					"without one on the certificate."
				).format(self.supplier_name)
			)

		if not self.lines:
			problems.append(
				_("Nothing was withheld from this supplier between {0} and {1}.").format(
					self.period_from, self.period_to
				)
			)

		if self.period_from and self.period_to and getdate(self.period_from) > getdate(self.period_to):
			problems.append(_("Period start is after period end."))

		summed = flt(sum(line.tax_amount for line in self.lines), 2)
		if abs(summed - flt(self.total_withheld, 2)) > RECONCILIATION_TOLERANCE:
			problems.append(
				_("The lines total {0} but the certificate states {1}.").format(summed, self.total_withheld)
			)

		for line in self.lines:
			if flt(line.tax_amount) and not flt(line.rate):
				problems.append(
					_("{0} withholds {1} at no stated rate.").format(line.voucher_no, line.tax_amount)
				)

		return problems


def _report_rows(company: str, supplier: str, from_date: str, to_date: str) -> list[dict]:
	"""ERPNext's own withholding query, with `party` as a scalar.

	A list here raises ProgrammingError 1064 upstream — see the module docstring.
	"""
	from erpnext.accounts.report.tax_withholding_details.tax_withholding_details import execute

	filters = frappe._dict(
		{
			"company": company,
			"party_type": "Supplier",
			"party": supplier,  # scalar, deliberately — a list breaks upstream
			"from_date": from_date,
			"to_date": to_date,
		}
	)
	_columns, data = execute(filters)
	return list(data or [])


def build_withholding_certificate(
	company: str, supplier: str, from_date: str, to_date: str
) -> WithholdingCertificate:
	"""Build the certificate for one supplier over one period."""
	if not is_lao_company(company):
		frappe.throw(
			_("{0} is not registered in Lao PDR, so a Lao withholding certificate does not apply.").format(
				company
			)
		)

	company_doc = frappe.get_cached_doc("Company", company)
	supplier_doc = frappe.get_cached_doc("Supplier", supplier)
	currency = company_doc.default_currency

	lines = []
	for row in _report_rows(company, supplier, from_date, to_date):
		if not flt(row.get("tax_amount")):
			continue
		lines.append(
			WithholdingLine(
				voucher_type=row.get("transaction_type") or "",
				voucher_no=row.get("ref_no") or "",
				posting_date=str(row.get("transaction_date") or ""),
				supplier_invoice_no=row.get("supplier_invoice_no"),
				category=row.get("tax_withholding_category"),
				net_amount=flt(row.get("base_tax_withholding_net_total") or row.get("total_amount")),
				rate=flt(row.get("rate")),
				tax_amount=flt(row.get("tax_amount")),
			)
		)

	total_withheld = flt(sum(line.tax_amount for line in lines), 2)
	total_net = flt(sum(line.net_amount for line in lines), 2)

	return WithholdingCertificate(
		schema=SCHEMA_VERSION,
		statute=STATUTE,
		company=company,
		agent_tax_id=company_doc.get("lao_tax_id") or company_doc.get("tax_id"),
		agent_registration=company_doc.get("lao_business_registration"),
		supplier=supplier,
		supplier_name=supplier_doc.supplier_name or supplier,
		supplier_tax_id=supplier_doc.get("lao_tax_id") or supplier_doc.get("tax_id"),
		period_from=str(getdate(from_date)),
		period_to=str(getdate(to_date)),
		currency=currency,
		lines=tuple(lines),
		total_net=total_net,
		total_withheld=total_withheld,
		total_withheld_in_words=(
			lao_money_in_words(total_withheld, currency) if currency == "LAK" and total_withheld else None
		),
	)


@frappe.whitelist()
def withholding_certificate(company: str, supplier: str, from_date: str, to_date: str) -> dict:
	"""Machine-readable certificate plus the reasons it is not fit to issue."""
	frappe.only_for(("System Manager", "Accounts Manager", "Accounts User"))

	certificate = build_withholding_certificate(company, supplier, from_date, to_date)
	return {"certificate": certificate.as_dict(), "problems": certificate.check()}


@frappe.whitelist()
def withholding_certificate_html(company: str, supplier: str, from_date: str, to_date: str) -> str:
	"""The printable certificate.

	Rendered rather than returned as data because this is the artifact that leaves
	the building. The template names the Lao font families and declares no
	``@font-face`` — see BERP-LAO-ARCH-001 ADR-A4; on the supported wkhtmltopdf
	stack an ``@font-face`` here would destroy the Lao text rather than fix it.
	"""
	frappe.only_for(("System Manager", "Accounts Manager", "Accounts User"))

	certificate = build_withholding_certificate(company, supplier, from_date, to_date)
	return frappe.render_template(
		TEMPLATE,
		{
			"c": certificate,
			"problems": certificate.check(),
			"printed_on": frappe.utils.formatdate(frappe.utils.nowdate(), "dd/MM/yyyy"),
		},
	)
