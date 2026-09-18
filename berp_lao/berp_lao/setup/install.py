# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
berp_lao post-install setup.

Runs once after `bench --site <site> install-app berp_lao`.

What happens here is deliberately limited to things that are true for the whole
site: the LAK currency format and the custom fields. Anything company-scoped —
the PCG Chart of Accounts and the VAT/WHT templates — is applied per company,
either automatically for Lao companies that already exist, or on demand from the
Company form, because a fresh site usually has no company yet.
"""

import json
import os

import frappe
from frappe import _

LAK_NUMBER_FORMAT = "#.###,##"  # CLDR lo-LA: 1.000.000,00


def after_install():
	"""Main post-install entry point."""
	set_lao_currency_format()
	create_lao_custom_fields()
	load_geography_fixtures()
	setup_existing_lao_companies()
	frappe.db.commit()  # nosemgrep — install hook owns its transaction
	frappe.logger("berp_lao").info("berp_lao: installation complete.")


def after_migrate():
	"""hooks.after_migrate — re-apply the custom fields on every migrate.

	`after_install` runs once. A custom field added in a later version of this app
	would never reach a site that installed an earlier one, because `bench migrate`
	syncs DocTypes and fixtures but does not re-run installation. `create_custom_fields`
	updates what exists and creates what does not, so calling it here is idempotent
	and is what makes a field addition actually ship.
	"""
	create_lao_custom_fields()


def before_uninstall():
	"""Remove the custom fields this app added, leaving ERPNext data intact."""
	for name in frappe.get_all("Custom Field", filters={"module": "Lao Regional"}, pluck="name"):
		frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
	frappe.db.commit()  # nosemgrep — uninstall hook owns its transaction
	frappe.logger("berp_lao").info("berp_lao: custom fields removed.")


# ─── Currency Format ──────────────────────────────────────────────────────────


def set_lao_currency_format():
	"""
	Set LAK (Lao Kip) to the CLDR lo-LA convention:
	  - thousands separator: period    1.000.000
	  - decimal separator:   comma     ,00
	  - symbol:              LAK (Kip)
	"""
	if not frappe.db.exists("Currency", "LAK"):
		frappe.logger("berp_lao").warning("berp_lao: LAK currency not found — skipping format setup.")
		return

	lak = frappe.get_doc("Currency", "LAK")
	lak.symbol = "₭"
	lak.fraction = "At"
	lak.fraction_units = 100
	lak.number_format = LAK_NUMBER_FORMAT
	lak.smallest_currency_fraction_value = 0
	lak.enabled = 1
	lak.save(ignore_permissions=True)
	frappe.logger("berp_lao").info("berp_lao: LAK currency format configured (lo-LA CLDR).")


# ─── Custom Fields ────────────────────────────────────────────────────────────


CUSTOM_FIELD_MODULE = "Lao Regional"
#: Keys beginning with this are documentation carried beside the data and are
#: stripped before anything reaches a Custom Field. JSON has no comments, and the
#: reasoning for a field belongs next to the field, not in a distant docstring.
DOC_KEY_PREFIX = "_"


def get_lao_custom_fields() -> dict:
	"""Custom fields added to standard ERPNext DocTypes for Lao compliance.

	Loaded from ``lao_regional/data/custom_fields.json`` rather than written here.
	This used to be a 122-line literal — 41% of this file — which is data wearing a
	function. As JSON it is a reviewable diff, and, more to the point, it can be
	validated against the live DocType meta: see
	``tests/test_company_setup.py::TestCustomFieldDefinitions``, which asserts that
	every ``insert_after`` names a field that exists and every ``Link`` option names
	a real DocType. Two of the six defects the first bench run found were exactly
	this class of mismatch, and nothing was checking for them.
	"""
	import json

	path = frappe.get_app_path("berp_lao", "lao_regional", "data", "custom_fields.json")
	with open(path, encoding="utf-8") as handle:
		raw = json.load(handle)

	return {
		doctype: [
			{
				**{k: v for k, v in row.items() if not k.startswith(DOC_KEY_PREFIX)},
				"module": CUSTOM_FIELD_MODULE,
			}
			for row in rows
		]
		for doctype, rows in raw.items()
	}


def create_lao_custom_fields():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(get_lao_custom_fields(), ignore_validate=True)
	frappe.logger("berp_lao").info("berp_lao: custom fields created.")


# ─── Geography Fixtures ───────────────────────────────────────────────────────
# `bench migrate` also imports everything under berp_lao/fixtures/ via
# frappe.utils.fixtures.sync_fixtures. These loaders exist so that `after_install`
# leaves a usable site on its own, and they insert in dependency order
# (province -> district -> village) rather than relying on filename sort order.


def _fixtures_dir() -> str:
	return os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "fixtures"))


def load_geography_fixtures():
	for filename, doctype in (
		("lao_province.json", "Lao Province"),
		("lao_district.json", "Lao District"),
		("lao_village.json", "Lao Village"),
	):
		path = os.path.join(_fixtures_dir(), filename)
		if os.path.exists(path):
			_import_fixture(path, doctype)
		else:
			frappe.logger("berp_lao").warning(f"berp_lao: fixture not found at {path}")


def _import_fixture(filepath: str, doctype: str):
	with open(filepath, encoding="utf-8") as f:
		records = json.load(f)

	count = 0
	for record in records:
		if record.get("name") and frappe.db.exists(doctype, record["name"]):
			continue
		doc = frappe.get_doc(record)
		doc.insert(ignore_permissions=True)
		count += 1

	frappe.logger("berp_lao").info(f"berp_lao: imported {count} {doctype} record(s).")


# ─── Company Setup ────────────────────────────────────────────────────────────


def setup_existing_lao_companies():
	"""
	Apply the Lao chart and tax templates to Lao companies that already exist and
	have not posted anything yet. A company created later goes through
	the "Lao Tools" buttons on the
	Company form instead.
	"""
	from berp_lao.lao_regional.chart_of_accounts.lao_pcg import (
		company_has_accounts,
		company_has_gl_entries,
		get_chart,
	)
	from berp_lao.lao_regional.country import lao_country_name
	from berp_lao.setup.tax_templates import create_lao_tax_templates

	country = lao_country_name()
	if not country:
		frappe.logger("berp_lao").info(
			"berp_lao: no Lao PDR country record on this site — skipping company setup."
		)
		return

	for company in frappe.get_all("Company", filters={"country": country}, pluck="name"):
		if company_has_gl_entries(company):
			frappe.logger("berp_lao").info(
				f"berp_lao: {company} already has GL entries — leaving its Chart of Accounts alone."
			)
		elif not company_has_accounts(company):
			from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import create_charts

			create_charts(company, custom_chart=get_chart())
			frappe.logger("berp_lao").info(f"berp_lao: Lao PCG Chart of Accounts created for {company}.")

		try:
			create_lao_tax_templates(company)
		except Exception:
			frappe.log_error(
				title="berp_lao: Lao tax template setup failed",
				message=f"Company: {company}\n\n{frappe.get_traceback()}",
			)
