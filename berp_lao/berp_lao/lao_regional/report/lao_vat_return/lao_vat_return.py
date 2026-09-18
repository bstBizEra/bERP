# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Lao Monthly VAT Return (ອາກອນ 10%).

Output and input VAT are read from the tax tables of submitted invoices, not
from `base_total_taxes_and_charges` on the invoice header — that header field is
the sum of *every* tax and charge row, so freight, handling and any non-VAT levy
would otherwise be declared as VAT. Only rows whose rate is the Lao standard rate
count, and input VAT excludes rows added to item valuation, which are capitalised
into stock rather than reclaimed.

Submitted credit notes (is_return = 1) carry negative amounts and are included,
so the return nets off returns within the period.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt, getdate

from berp_lao.lao_regional.country import is_lao_country

VAT_STANDARD_RATE = 10.0
EXPORT_TYPE = "Export (0%)"
EXEMPT_TYPE = "VAT Exempt"
DOMESTIC_TYPES = ("Standard", "Simplified")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	_validate_filters(filters)

	currency = frappe.get_cached_value("Company", filters.company, "default_currency")
	output_vat = _output_vat(filters)
	input_vat = _input_vat(filters)

	data = get_data(filters, currency, output_vat, input_vat)
	summary = _report_summary(currency, output_vat, input_vat)
	return get_columns(), data, None, None, summary, True


def _validate_filters(filters):
	for field, label in (("company", _("Company")), ("from_date", _("From Date")), ("to_date", _("To Date"))):
		if not filters.get(field):
			frappe.throw(_("{0} is required.").format(label))

	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date must be on or before To Date."))

	country = frappe.get_cached_value("Company", filters.company, "country")
	if not is_lao_country(country):
		frappe.throw(
			_("{0} is registered in {1}. The Lao VAT Return applies to Lao companies only.").format(
				filters.company, country or _("an unknown country")
			)
		)


def get_columns():
	return [
		{
			"label": _("Section (ລາຍການ)"),
			"fieldname": "section",
			"fieldtype": "Data",
			"width": 320,
		},
		{
			"label": _("Net Amount"),
			"fieldname": "base_amount",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 180,
		},
		{"label": _("VAT Rate"), "fieldname": "vat_rate", "fieldtype": "Percent", "width": 100},
		{
			"label": _("VAT Amount"),
			"fieldname": "vat_amount",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 180,
		},
		{"label": _("Invoices"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 90},
	]


# ─── Data ─────────────────────────────────────────────────────────────────────


def _has_invoice_type_field() -> bool:
	return frappe.db.has_column("Sales Invoice", "lao_invoice_type")


def _sales_net_by_type(filters) -> dict:
	"""Net sales and invoice count per Lao VAT treatment, classified PER LINE.

	THE DEFECT THIS REPLACES
	    This used to group by ``Sales Invoice.lao_invoice_type`` and sum
	    ``base_net_total`` — the whole invoice, under one header label. A mixed
	    invoice was therefore declared entirely at its header's treatment.
	    Measured on this stack, one invoice of 1,000,000 taxable + 500,000 exempt,
	    header "Standard":

	        standard-rated net declared   1,500,000
	        output VAT declared             100,000   (ERPNext charged it correctly)
	        net that actually bore VAT    1,000,000

	    A return declaring a 1,500,000 standard-rated base against 100,000 of VAT
	    **does not reconcile with itself** — at 10% that base implies 150,000. The
	    Revenue Department sees a 50,000 shortfall on a return the system called
	    correct. ERPNext was right throughout; only this report was wrong.

	HOW A LINE IS CLASSIFIED
	    ERPNext records the rate it actually applied to each line in
	    ``Sales Invoice Item.item_tax_rate`` — ``{account: rate}`` when an Item Tax
	    Template governs the line, and ``{}`` when none does. That is the
	    authoritative per-line fact, so it is what this reads.

	        no entry for the VAT account  → the line inherits the invoice's type
	        rate > 0                      → standard-rated (or Simplified)
	        rate == 0                     → Export if the invoice is an export,
	                                        otherwise VAT Exempt

	    The invoice type remains the default for every line; an Item Tax Template
	    overrides it for the line it is on.

	INVOICE COUNTS
	    Counted as DISTINCT invoices contributing to each treatment. A mixed
	    invoice appears under more than one, so the counts can sum to more than the
	    number of invoices in the period. That is the honest reading — the
	    alternative is to attribute a mixed invoice arbitrarily to one treatment.
	"""
	if not _has_invoice_type_field():
		rows = frappe.db.sql(
			"""
			SELECT 'Standard' AS invoice_type,
			       SUM(si.base_net_total) AS net_total,
			       COUNT(si.name)         AS invoice_count
			FROM `tabSales Invoice` si
			WHERE si.company = %(company)s
			  AND si.docstatus = 1
			  AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
			""",
			filters,
			as_dict=True,
		)
		return {r.invoice_type: r for r in rows if r.invoice_type}

	lines = frappe.db.sql(
		"""
		SELECT si.name                                                   AS invoice,
		       COALESCE(NULLIF(si.lao_invoice_type, ''), 'Standard')     AS invoice_type,
		       sii.base_net_amount                                       AS net_amount,
		       sii.item_tax_rate                                         AS item_tax_rate
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.company = %(company)s
		  AND si.docstatus = 1
		  AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
		""",
		filters,
		as_dict=True,
	)

	vat_accounts = _output_vat_accounts(filters.get("company"))

	totals: dict[str, float] = {}
	invoices: dict[str, set] = {}
	for line in lines:
		treatment = _line_treatment(line.invoice_type, _line_vat_rate(line.item_tax_rate, vat_accounts))
		totals[treatment] = flt(totals.get(treatment)) + flt(line.net_amount)
		invoices.setdefault(treatment, set()).add(line.invoice)

	return {
		treatment: frappe._dict(
			{
				"invoice_type": treatment,
				"net_total": flt(total, 2),
				"invoice_count": len(invoices[treatment]),
			}
		)
		for treatment, total in totals.items()
	}


def _output_vat_accounts(company: str | None) -> set:
	"""Accounts that carry output VAT for this company.

	Resolved from the chart rather than named here: the PCG account name carries
	Lao script and a company abbreviation, so it cannot be a constant.
	"""
	if not company:
		return set()
	return set(
		frappe.get_all(
			"Account",
			filters={"company": company, "account_type": "Tax", "is_group": 0},
			pluck="name",
		)
	)


def _line_vat_rate(item_tax_rate, vat_accounts: set) -> float | None:
	"""The VAT rate ERPNext applied to this line, or None when no template governed it.

	None is not zero. A line with no Item Tax Template inherits the invoice's
	treatment; a line with a template at 0% is deliberately zero-rated. Collapsing
	the two would reclassify every ordinary line as exempt.
	"""
	if not item_tax_rate:
		return None
	try:
		rates = json.loads(item_tax_rate)
	except (TypeError, ValueError):
		return None
	if not isinstance(rates, dict):
		return None
	for account, rate in rates.items():
		if account in vat_accounts:
			return flt(rate)
	return None


def _line_treatment(invoice_type: str, line_rate: float | None) -> str:
	"""Which VAT treatment one line falls under."""
	if line_rate is None:
		return invoice_type
	if line_rate > 0:
		# A taxed line is standard-rated whatever the header says. "Simplified" is a
		# documentation concession at the same rate, so it survives as a label.
		return "Simplified" if invoice_type == "Simplified" else "Standard"
	return "Export (0%)" if invoice_type == "Export (0%)" else "VAT Exempt"


def _output_vat(filters) -> float:
	"""Sum of 10% VAT rows on submitted Sales Invoices."""
	value = frappe.db.sql(
		"""
		SELECT SUM(stc.base_tax_amount)
		FROM `tabSales Taxes and Charges` stc
		INNER JOIN `tabSales Invoice` si ON si.name = stc.parent
		WHERE stc.parenttype = 'Sales Invoice'
		  AND stc.rate = %(vat_rate)s
		  AND si.company = %(company)s
		  AND si.docstatus = 1
		  AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
		""",
		dict(filters, vat_rate=VAT_STANDARD_RATE),
	)
	return flt(value[0][0]) if value else 0.0


def _input_vat(filters) -> float:
	"""
	Sum of 10% VAT rows on submitted Purchase Invoices.

	Rows whose category is 'Valuation' are capitalised into item cost and are not
	reclaimable, and deducted rows (add_deduct_tax = 'Deduct') reduce the claim.
	"""
	value = frappe.db.sql(
		"""
		SELECT SUM(CASE WHEN ptc.add_deduct_tax = 'Deduct'
		                THEN -ptc.base_tax_amount
		                ELSE ptc.base_tax_amount END)
		FROM `tabPurchase Taxes and Charges` ptc
		INNER JOIN `tabPurchase Invoice` pi ON pi.name = ptc.parent
		WHERE ptc.parenttype = 'Purchase Invoice'
		  AND ptc.rate = %(vat_rate)s
		  AND ptc.category != 'Valuation'
		  AND pi.company = %(company)s
		  AND pi.docstatus = 1
		  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
		""",
		dict(filters, vat_rate=VAT_STANDARD_RATE),
	)
	return flt(value[0][0]) if value else 0.0


def _purchases_net(filters) -> dict:
	row = frappe.db.sql(
		"""
		SELECT SUM(pi.base_net_total) AS net_total, COUNT(pi.name) AS invoice_count
		FROM `tabPurchase Invoice` pi
		WHERE pi.company = %(company)s
		  AND pi.docstatus = 1
		  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
		""",
		filters,
		as_dict=True,
	)
	return row[0] if row else frappe._dict({"net_total": 0, "invoice_count": 0})


def get_data(filters, currency, output_vat, input_vat):
	sales = _sales_net_by_type(filters)
	purchases = _purchases_net(filters)

	domestic_net = sum(flt(sales.get(t, {}).get("net_total")) for t in DOMESTIC_TYPES)
	domestic_count = sum(flt(sales.get(t, {}).get("invoice_count")) for t in DOMESTIC_TYPES)
	export = sales.get(EXPORT_TYPE) or frappe._dict()
	exempt = sales.get(EXEMPT_TYPE) or frappe._dict()

	net_vat = output_vat - input_vat

	def row(section, base_amount=None, vat_rate=None, vat_amount=None, invoice_count=None, bold=False):
		return {
			"section": f"<b>{section}</b>" if bold else section,
			"base_amount": base_amount,
			"vat_rate": vat_rate,
			"vat_amount": vat_amount,
			"invoice_count": int(invoice_count) if invoice_count else None,
			"currency": currency,
		}

	return [
		row(_("OUTPUT VAT — SALES (ອາກອນຂາຍ)"), bold=True),
		row(
			_("1. Standard domestic sales (ຂາຍພາຍໃນ 10%)"),
			domestic_net,
			VAT_STANDARD_RATE,
			output_vat,
			domestic_count,
		),
		row(
			_("2. Export sales, zero-rated (\u0e82\u0eb2\u0e8d\u0ead\u0ead\u0e81 0%)"),
			flt(export.get("net_total")),
			0.0,
			0.0,
			export.get("invoice_count"),
		),
		row(
			_("3. VAT-exempt sales (ຂາຍປອດອາກອນ)"),
			flt(exempt.get("net_total")),
			None,
			0.0,
			exempt.get("invoice_count"),
		),
		row(_("4. Total output VAT (ລວມອາກອນຂາຍ)"), None, None, output_vat, bold=True),
		row(_("INPUT VAT — PURCHASES (ອາກອນຊື້)"), bold=True),
		row(
			_("5. Purchases eligible for input VAT (ຊື້ພາຍໃນ 10%)"),
			flt(purchases.get("net_total")),
			VAT_STANDARD_RATE,
			input_vat,
			purchases.get("invoice_count"),
		),
		row(_("6. Total input VAT (ລວມອາກອນຊື້)"), None, None, input_vat, bold=True),
		row(
			_("7. Net VAT payable / (claimable) (ອາກອນຕ້ອງມອບສຸດທິ)"),
			None,
			None,
			net_vat,
			bold=True,
		),
	]


def _report_summary(currency, output_vat, input_vat):
	net_vat = output_vat - input_vat
	return [
		{"label": _("Output VAT"), "value": output_vat, "datatype": "Currency", "currency": currency},
		{"label": _("Input VAT"), "value": input_vat, "datatype": "Currency", "currency": currency},
		{
			"label": _("Net VAT Payable") if net_vat >= 0 else _("Net VAT Claimable"),
			"value": abs(net_vat),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Red" if net_vat > 0 else "Green",
		},
	]
