# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

# ─── App Metadata ─────────────────────────────────────────────────────────────
# NOTE: app_name MUST match the Python package directory name (berp_lao/).
# Every dotted path below is imported by Frappe at runtime, so they all start
# with "berp_lao." — a mismatch here fails at install time, not at import time.
app_name = "berp_lao"
app_title = "bERP Lao"
app_publisher = "BSTBizEra"
app_description = (
	"Lao PDR localisation for ERPNext — PCG Chart of Accounts, VAT 10%, WHT, "
	"provinces/districts/villages, Phetsarath OT typography"
)
app_email = "dev@bstbizera.com"
app_license = "GNU General Public License (v3)"
required_apps = ["frappe/erpnext"]

# ─── Frontend Assets ──────────────────────────────────────────────────────────
# Compiled by Frappe's esbuild pipeline from public/css/berp_lao.bundle.css
app_include_css = "berp_lao.bundle.css"

# ─── Regional Overrides ───────────────────────────────────────────────────────
# ERPNext's regional_overrides is keyed by the Country record's *name*, which on a
# real site is "Lao Peoples Democratic Republic", not "Laos" — and is editable, so no
# static key is reliable. Both ERPNext hook targets for this region are no-op stubs
# upstream anyway, so there is nothing to override and the key is omitted entirely
# rather than left wrong. Everything else in this app matches on the ISO code via
# berp_lao.lao_regional.country.is_lao_country.
#
# Historic note, do not reinstate without reading it: this app matched on the literal
# string "Laos" until a bench run proved no such Country record exists. Every doc_event
# below was dead code.
#
# The two candidates ERPNext exposes here — taxes_and_totals.update_itemised_tax_data
# and accounts_controller.validate_regional — are both no-op stubs upstream, and the
# Lao checks they would carry run from doc_events below, where they are covered by
# tests. Reinstate this hook only alongside an override that is actually needed, and
# resolve the key at runtime rather than writing a country name here.

# Publishes the resolved Lao country name to frappe.boot for the form scripts.
extend_bootinfo = "berp_lao.lao_regional.country.extend_bootinfo"

# ─── Document Event Hooks ─────────────────────────────────────────────────────
# Note on ordering: Frappe composes doc_events to run *after* the document's own
# method, so `set_lao_in_words` overwrites the English wording ERPNext has already
# put in `in_words` — num2words has no Lao and falls back to English.
doc_events = {
	"Sales Invoice": {
		# before_naming, because the name is assigned before validate runs and a
		# company with per-company numbering must not take a number from the shared
		# site-wide counter first.
		"before_naming": "berp_lao.lao_regional.rules.sales_invoice.set_lao_invoice_series",
		"validate": [
			"berp_lao.lao_regional.rules.sales_invoice.validate_lao_sales_invoice",
			"berp_lao.lao_regional.lao_numbers.set_lao_in_words",
		],
		"on_submit": "berp_lao.lao_regional.rules.sales_invoice.sales_invoice_on_submit",
		"on_cancel": "berp_lao.lao_regional.rules.sales_invoice.sales_invoice_on_cancel",
	},
	"Purchase Invoice": {
		# before_validate, because ERPNext computes withholding inside its own
		# validate() and a hook composed after that would be too late.
		"before_validate": "berp_lao.lao_regional.rules.purchase_invoice.apply_lao_withholding_defaults",
		"validate": "berp_lao.lao_regional.rules.purchase_invoice.validate_lao_purchase_invoice",
	},
	"Company": {
		"on_update": "berp_lao.lao_regional.rules.company.update_company_lao_defaults",
	},
}

# ─── Post-Install Hook ────────────────────────────────────────────────────────
after_install = "berp_lao.setup.install.after_install"
# Custom fields are re-applied on every migrate, so a field added in a later
# version reaches sites that installed an earlier one. See setup.install.after_migrate.
after_migrate = [
	"berp_lao.setup.install.after_migrate",
	# Existing sites carry withholding categories that can never withhold: ERPNext
	# reads single_threshold = 0 as "never", not "no threshold". See the note on
	# NO_DE_MINIMIS_THRESHOLD.
	"berp_lao.setup.tax_templates.repair_withholding_thresholds",
	# wkhtmltopdf takes its fonts from fontconfig, not from this app. Say so at
	# migrate time rather than letting it surface as a subtly wrong invoice.
	"berp_lao.lao_regional.fonts.warn_if_fonts_missing",
]
before_uninstall = "berp_lao.setup.install.before_uninstall"

# ─── Fixtures ─────────────────────────────────────────────────────────────────
# Drives `bench export-fixtures`. Note that `bench migrate` imports EVERY .json
# file under berp_lao/fixtures/ regardless of this list, so anything that is not
# a self-contained, company-independent record must live elsewhere — Lao tax
# templates are built per company from lao_regional/data/ instead.
fixtures = [
	{"dt": "Custom Field", "filters": [["module", "=", "Lao Regional"]]},
	{"dt": "Property Setter", "filters": [["module", "=", "Lao Regional"]]},
	{"dt": "Lao Province"},
	{"dt": "Lao District"},
	{"dt": "Lao Village"},
]

# ─── DocType JS Overrides ─────────────────────────────────────────────────────
doctype_js = {
	"Sales Invoice": "public/js/lao_sales_invoice.js",
	"Company": "public/js/lao_company.js",
}

# ─── Global Search ────────────────────────────────────────────────────────────
global_search_doctypes = {
	"Default": [
		{"doctype": "Lao Province", "index": 100},
		{"doctype": "Lao District", "index": 101},
		{"doctype": "Lao Village", "index": 102},
	]
}

# ─── Scheduler (future: VAT return reminders) ─────────────────────────────────
# scheduler_events = {
#     "cron": {
#         # Lao VAT returns are due by the 20th of the following month.
#         "0 8 15 * *": ["berp_lao.lao_regional.rules.reminders.send_vat_deadline_reminder"],
#     },
# }
