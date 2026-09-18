# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Build Lao VAT and WHT tax templates for a company.

Tax templates cannot ship as Frappe fixtures: `Sales Taxes and Charges Template`
and `Purchase Taxes and Charges Template` are company-scoped and their
`account_head` links resolve to company-suffixed account names. `Tax Withholding
Category` is global but requires a per-company row in its `accounts` table. So
the definitions live in lao_regional/data/lao_tax_templates.json keyed by PCG
account number, and this module resolves them against a real company.
"""

import json
import os

import frappe
from frappe import _
from frappe.utils import cint, flt

from berp_lao.lao_regional.country import is_lao_company


def _data() -> dict:
	path = os.path.join(os.path.dirname(__file__), "..", "lao_regional", "data", "lao_tax_templates.json")
	with open(os.path.normpath(path), encoding="utf-8") as f:
		return json.load(f)


#: "No de-minimis" has to be written as one kip, not as zero.
#:
#: ERPNext's ``get_tds_amount`` guards the whole calculation on
#: ``if (threshold and tax_withholding_net_total >= threshold) or cumulative_...``
#: — and ``0`` is falsy. A rate row with ``single_threshold = 0`` therefore means
#: *never withhold*, not *withhold from the first kip*. Lao WHT has no de-minimis:
#: the rates apply to the whole payment.
#:
#: Measured on this stack, 2026-09-16, one invoice, net 1,000,000 LAK, Services at
#: 10%, everything else identical:
#:
#:     single_threshold = 0    withheld 0          grand total 1,000,000
#:     single_threshold = 1    withheld 100,000    grand total   900,000
#:
#: The app seeded 0 and shipped nine categories that could never withhold anything
#: — correct rates, correct PCG accounts, and dead. See `repair_withholding_thresholds`,
#: which fixes sites that already have them.
NO_DE_MINIMIS_THRESHOLD = 1

#: Every Tax Withholding Category this app owns is named with this prefix. It is
#: how the repair below tells ours from a tenant's own.
CATEGORY_NAME_PREFIX = "WHT - "


def _rate_rows(spec: dict) -> list[dict]:
	"""
	Build the Tax Withholding Rate child rows for a category.

	A statutory rate change is a new dated row rather than an edit, so that
	invoices dated before the change keep withholding at the old rate. The Income
	Tax Law 2025 (in force 1 July 2026) is why construction and online sales carry
	two rows each.

	``single_threshold`` comes from the JSON when a category genuinely has a
	statutory floor, and otherwise from `NO_DE_MINIMIS_THRESHOLD` — read its note
	before changing it to 0, which does not mean what it looks like it means.
	"""
	return [
		{
			"from_date": row["from_date"],
			"to_date": row["to_date"],
			"tax_withholding_rate": row["rate"],
			"single_threshold": row.get("single_threshold", NO_DE_MINIMIS_THRESHOLD),
			"cumulative_threshold": row.get("cumulative_threshold", 0),
		}
		for row in spec["rates"]
	]


def _account(company: str, account_number: str) -> str | None:
	"""Resolve a PCG account number to this company's Account name."""
	return frappe.db.get_value(
		"Account", {"company": company, "account_number": account_number, "is_group": 0}, "name"
	)


def create_lao_tax_templates(company: str, verbose: bool = False) -> dict:
	"""
	Create the Lao VAT/WHT templates for `company`, skipping anything that
	already exists. Returns a summary of what was created and what was skipped.

	Safe to re-run: every document is looked up before it is created, and a
	missing PCG account is reported rather than raised, so a partially set-up
	company still gets whatever it can.
	"""
	if not is_lao_company(company):
		frappe.throw(_("{0} is not a Lao company.").format(company))

	data = _data()
	abbr = frappe.get_cached_value("Company", company, "abbr")
	created, skipped, missing = [], [], []

	for key, doctype in (
		("sales_taxes_and_charges_templates", "Sales Taxes and Charges Template"),
		("purchase_taxes_and_charges_templates", "Purchase Taxes and Charges Template"),
	):
		for spec in data.get(key, []):
			name = f"{spec['title']} - {abbr}"
			if frappe.db.exists(doctype, name):
				skipped.append(name)
				continue

			rows = []
			for tax in spec["taxes"]:
				account = _account(company, tax["account_number"])
				if not account:
					missing.append((name, tax["account_number"]))
					break
				row = {k: v for k, v in tax.items() if k != "account_number"}
				row["account_head"] = account
				rows.append(row)
			else:
				doc = frappe.get_doc(
					{
						"doctype": doctype,
						"title": spec["title"],
						"company": company,
						"is_default": cint(spec.get("is_default")),
						"taxes": rows,
					}
				)
				doc.insert(ignore_permissions=True)
				created.append(doc.name)

	for spec in data.get("tax_withholding_categories", []):
		account = _account(company, spec["account_number"])
		if not account:
			missing.append((spec["name"], spec["account_number"]))
			continue

		if frappe.db.exists("Tax Withholding Category", spec["name"]):
			doc = frappe.get_doc("Tax Withholding Category", spec["name"])
			if any(row.company == company for row in doc.accounts):
				skipped.append(spec["name"])
				continue
			doc.append("accounts", {"company": company, "account": account})
			doc.save(ignore_permissions=True)
			created.append(f"{spec['name']} (account row for {company})")
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Tax Withholding Category",
				"name": spec["name"],
				"category_name": spec["category_name"],
				"rates": _rate_rows(spec),
				"accounts": [{"company": company, "account": account}],
			}
		)
		doc.insert(ignore_permissions=True)
		created.append(doc.name)

	for spec in data.get("item_tax_templates", []):
		# Item Tax Templates are company-scoped and ERPNext suffixes the title with
		# the company abbreviation, so the name has to be resolved rather than assumed.
		existing = frappe.db.get_value(
			"Item Tax Template", {"company": company, "title": spec["title"]}, "name"
		)
		if existing:
			skipped.append(existing)
			continue

		rows = []
		unresolved = False
		for row in spec.get("taxes", []):
			account = _account(company, row["account_number"])
			if not account:
				missing.append((spec["title"], row["account_number"]))
				unresolved = True
				break
			rows.append({"tax_type": account, "tax_rate": flt(row["tax_rate"])})
		if unresolved:
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Item Tax Template",
				"title": spec["title"],
				"company": company,
				"taxes": rows,
			}
		)
		doc.insert(ignore_permissions=True)
		created.append(doc.name)

	summary = {"created": created, "skipped": skipped, "missing_accounts": missing}
	if missing:
		frappe.logger("berp_lao").warning(
			f"berp_lao: tax templates for {company} skipped — PCG accounts not found: {missing}"
		)
	if verbose:
		frappe.logger("berp_lao").info(f"berp_lao: tax templates for {company}: {summary}")
	return summary


@frappe.whitelist()
def install_lao_tax_templates(company: str) -> dict:
	"""Company form action: build the Lao VAT/WHT templates for this company."""
	frappe.only_for(("System Manager", "Accounts Manager"))
	summary = create_lao_tax_templates(company, verbose=True)

	if summary["missing_accounts"]:
		numbers = sorted({number for _name, number in summary["missing_accounts"]})
		frappe.msgprint(
			_(
				"Created {0} tax template(s). These PCG accounts were not found on {1}, "
				"so the templates that use them were skipped: {2}. Install the Lao PCG "
				"Chart of Accounts first."
			).format(len(summary["created"]), company, ", ".join(numbers)),
			indicator="orange",
			title=_("Lao Tax Templates"),
		)
	else:
		frappe.msgprint(
			_("Created {0} tax template(s) for {1}; {2} already existed.").format(
				len(summary["created"]), company, len(summary["skipped"])
			),
			indicator="green",
			title=_("Lao Tax Templates"),
		)
	return summary


def repair_withholding_thresholds() -> list[str]:
	"""hooks.after_migrate — make the categories on an existing site able to withhold.

	`create_lao_tax_templates` skips a category that already exists, so a site that
	installed this app before 2026-09-16 carries nine Tax Withholding Categories with
	`single_threshold = 0`, which ERPNext reads as *never withhold*. Nothing would
	have told anyone: the categories are present, the rates are right, the accounts
	are right, and every purchase invoice quietly withholds nothing.

	Idempotent, and scoped to the categories this app owns — a threshold someone set
	deliberately on their own category is none of our business. Returns what it
	changed, so a migrate log says whether it did anything.
	"""
	repaired = []
	for name in frappe.get_all(
		"Tax Withholding Category", filters={"name": ["like", f"{CATEGORY_NAME_PREFIX}%"]}, pluck="name"
	):
		doc = frappe.get_doc("Tax Withholding Category", name)
		zeroed = [row for row in doc.rates if not flt(row.single_threshold)]
		if not zeroed:
			continue
		for row in zeroed:
			row.single_threshold = NO_DE_MINIMIS_THRESHOLD
		doc.save(ignore_permissions=True)
		repaired.append(f"{name} ({len(zeroed)} rate row(s))")

	if repaired:
		frappe.logger("berp_lao").info(
			"berp_lao: withholding thresholds repaired — these categories could not "
			f"withhold anything until now: {repaired}"
		)
	return repaired
