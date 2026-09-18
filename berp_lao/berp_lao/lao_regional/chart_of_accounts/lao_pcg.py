# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Lao PCG Chart of Accounts.

ERPNext discovers chart templates only from its own
`erpnext/accounts/doctype/account/chart_of_accounts/{verified,unverified}`
folders — there is no hook that lets a regional app add one to the Setup Wizard
dropdown. So the Lao PCG chart ships as a plain JSON tree here and is applied to
a company explicitly, via `erpnext...create_charts(custom_chart=...)`.

Structure note: the Lao PCG (Law 47/NA 2013, MoF) is class-based, and two of its
classes straddle ERPNext's five root types — class 1 mixes equity with long-term
borrowings, class 4 mixes receivables with payables. ERPNext applies the root
node's `root_type` to the entire subtree, so those two classes are emitted as two
roots each, the same way ERPNext's own French PCG splits class 4 into ACTIF and
PASSIF. Account numbers are preserved throughout.
"""

import json
import os

import frappe
from frappe import _
from frappe.utils import cint

from berp_lao.lao_regional.country import is_lao_country

CHART_NAME = "Lao Standard PCG"


def get_chart() -> dict:
	"""Return the Lao PCG account tree in ERPNext `create_charts` format."""
	path = os.path.join(os.path.dirname(__file__), "lao_pcg_chart_of_accounts.json")
	with open(path, encoding="utf-8") as f:
		return json.load(f)["tree"]


def company_has_accounts(company: str) -> bool:
	return bool(frappe.db.exists("Account", {"company": company}))


def company_has_gl_entries(company: str) -> bool:
	return bool(frappe.db.exists("GL Entry", {"company": company, "is_cancelled": 0}))


@frappe.whitelist()
def install_lao_chart_of_accounts(company: str, force: int = 0) -> str:
	"""
	Create the Lao PCG chart for `company`.

	Refuses to run once the company has posted GL entries — replacing a chart
	under existing ledger entries would orphan them. Existing (but unused)
	accounts are only replaced when `force` is set, which is what the "Install
	Lao PCG Chart of Accounts" button on the Company form passes after the user
	confirms.
	"""
	frappe.only_for(("System Manager", "Accounts Manager"))

	company_doc = frappe.get_doc("Company", company)
	if not is_lao_country(company_doc.country):
		frappe.throw(_("{0} is not a Lao company — its country is {1}.").format(company, company_doc.country))

	if company_has_gl_entries(company):
		frappe.throw(
			_(
				"{0} already has General Ledger entries. The Chart of Accounts cannot be "
				"replaced once transactions have been posted."
			).format(company)
		)

	if company_has_accounts(company) and not cint(force):
		frappe.throw(
			_("{0} already has a Chart of Accounts. Re-run with Force to replace it.").format(company)
		)

	if company_has_accounts(company):
		_clear_account_defaults(company)
		frappe.db.delete("Account", {"company": company})
		frappe.db.commit()  # nosemgrep — create_charts starts a fresh account tree

	from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import create_charts

	frappe.local.flags.ignore_root_company_validation = True
	try:
		create_charts(company, custom_chart=get_chart())
	finally:
		frappe.local.flags.ignore_root_company_validation = False

	frappe.db.set_value("Company", company, "chart_of_accounts", CHART_NAME, update_modified=False)
	set_company_default_accounts(company)

	frappe.msgprint(
		_("Lao PCG Chart of Accounts created for {0}.").format(company),
		indicator="green",
		title=_("Chart of Accounts Installed"),
	)
	return CHART_NAME


#: Company fields filled by PCG account number. Numbers are the primary route
#: because the PCG says which account each default should be, and because several
#: accounts share an account_type — a bench run found `default_receivable_account`
#: resolving to 4112 Trade Debtors - Foreign purely on row order.
DEFAULT_ACCOUNT_NUMBERS = {
	"default_receivable_account": "4111",  # Trade Debtors - Local
	"default_payable_account": "4011",  # Trade Creditors - Local
	"default_cash_account": "5401",  # Head Office Petty Cash
	"default_bank_account": "5111",  # BCEL Current Account (LAK)
	"default_inventory_account": "30",  # Goods for Resale
	"accumulated_depreciation_account": "2811",  # Accum. Depr. Buildings
	"depreciation_expense_account": "6411",  # Depreciation of PP&E
	# ERPNext refuses to validate a Purchase Invoice without this one, whatever the
	# item is — a bench run is the only way to find that out.
	"stock_received_but_not_billed": "4013",  # Goods Received Not Invoiced
	"asset_received_but_not_billed": "4014",  # Assets Received Not Invoiced
	"default_income_account": "7011",  # Product Sales - Local
	"default_expense_account": "6011",  # Cost of Goods Sold
}

#: Fallback route, used only for a field the numbers above did not resolve — for
#: instance after someone edits the chart. Ordered by account number so that a
#: type with several candidates still resolves to the same account every time.
DEFAULT_ACCOUNT_FIELDS = {
	"default_receivable_account": "Receivable",
	"default_payable_account": "Payable",
	"default_cash_account": "Cash",
	"default_bank_account": "Bank",
	"accumulated_depreciation_account": "Accumulated Depreciation",
	"depreciation_expense_account": "Depreciation",
	"default_inventory_account": "Stock",
	"stock_received_but_not_billed": "Stock Received But Not Billed",
	"asset_received_but_not_billed": "Asset Received But Not Billed",
}


def _clear_account_defaults(company: str):
	"""Blank the company's Account links before the old tree is deleted."""
	values = dict.fromkeys(DEFAULT_ACCOUNT_FIELDS, None)
	values.update(dict.fromkeys(DEFAULT_ACCOUNT_NUMBERS, None))
	frappe.db.set_value("Company", company, values, update_modified=False)


def set_company_default_accounts(company: str) -> dict:
	"""
	Point the company's default Account fields at the new PCG accounts.

	Returns the fields that were set, so callers and tests can see what resolved.
	"""
	values = {}

	# ERPNext adds and removes Company default fields between versions, and writing
	# one it does not have is a raw SQL error rather than a clean validation. Ask the
	# doctype what it actually has.
	company_fields = {df.fieldname for df in frappe.get_meta("Company").fields}

	for fieldname, account_number in DEFAULT_ACCOUNT_NUMBERS.items():
		if fieldname not in company_fields:
			continue
		account = frappe.db.get_value(
			"Account", {"company": company, "account_number": account_number, "is_group": 0}, "name"
		)
		if account:
			values[fieldname] = account

	for fieldname, account_type in DEFAULT_ACCOUNT_FIELDS.items():
		if fieldname in values or fieldname not in company_fields:
			continue
		account = frappe.db.get_value(
			"Account",
			{"company": company, "account_type": account_type, "is_group": 0},
			"name",
			order_by="account_number asc",
		)
		if account:
			values[fieldname] = account

	if values:
		frappe.db.set_value("Company", company, values, update_modified=False)

	return values
