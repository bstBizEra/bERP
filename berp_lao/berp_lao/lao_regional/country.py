# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Is this document Lao? — the one question the rest of the app asks first.

This module is infrastructure. It depends on nothing else in ``berp_lao``, which is
the point: ``lao_numbers.py`` used to import the old ``utils`` module *inside a
function* to dodge a circular dependency, and a deferred import is a module
boundary telling you something is in the wrong place. Country resolution has no
business living beside invoice rules.

THE DEFECT THIS MODULE EXISTS TO PREVENT
    The first cut compared against the literal ``"Laos"``. Frappe seeds the Country
    record as ``Lao Peoples Democratic Republic``; nothing on a stock site is named
    ``Laos``. Every ``doc_event`` in the app was therefore dead code, and the VAT
    report's guard rejected every real Lao company — for a day, until a bench run
    found it. Match on the ISO 3166-1 alpha-2 code. Never on a name.
"""

import frappe

#: ISO 3166-1 alpha-2 for Lao PDR. The app matches on this, never on a name.
LAO_COUNTRY_CODE = "la"

#: A Lao company below the VAT registration threshold. Micro-enterprises are
#: excluded from automatic VAT registration and pay a flat 5% CIT on net profit
#: under Law No. 88/NA, so the VAT prompts are wrong for them — and they are
#: 94.2% of Lao enterprises by count.
NOT_VAT_REGISTERED_FIELD = "lao_not_vat_registered"

_COUNTRY_CACHE_KEY = "berp_lao:country_name"


def lao_country_name() -> str | None:
	"""The name the Country doctype uses for Lao PDR on *this* site.

	Do not hardcode it. Frappe seeds the record as ``Lao Peoples Democratic
	Republic`` — not ``Laos`` — the spelling has varied across versions, and the
	record is editable, so any site may have renamed it. The ISO code is the
	stable identifier, so resolve the name from that and cache the result.

	Returns None on a site with no Lao PDR country record at all, in which case
	every check in this app is correctly inert.
	"""
	cached = frappe.cache().get_value(_COUNTRY_CACHE_KEY)
	if cached is not None:
		return cached or None

	name = frappe.db.get_value("Country", {"code": LAO_COUNTRY_CODE}, "name")
	frappe.cache().set_value(_COUNTRY_CACHE_KEY, name or "")
	return name


def is_lao_country(country: str | None) -> bool:
	"""True when `country` is the Country record for Lao PDR."""
	if not country:
		return False
	code = frappe.get_cached_value("Country", country, "code")
	return (code or "").lower() == LAO_COUNTRY_CODE


def is_lao_company(company: str | None) -> bool:
	"""True when `company` is registered in Lao PDR."""
	if not company:
		return False
	return is_lao_country(frappe.get_cached_value("Company", company, "country"))


def is_vat_registered(company: str | None) -> bool:
	"""True unless the company is flagged as below the VAT threshold.

	Defaults to True: a company that has not been marked is treated as registered,
	which is what ERPNext's own automatic VAT registration assumes.
	"""
	if not company:
		return False
	return not frappe.get_cached_value("Company", company, NOT_VAT_REGISTERED_FIELD)


def extend_bootinfo(bootinfo):
	"""hooks.extend_bootinfo — publish the resolved country name to the client.

	Form scripts need it synchronously in `refresh`, and they must not hardcode a
	spelling for the same reason this module does not.
	"""
	bootinfo.berp_lao_country = lao_country_name()
