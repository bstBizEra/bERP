# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""Lao rules on the Company."""

import frappe
from frappe import _

from berp_lao.lao_regional.country import is_lao_country


def update_company_lao_defaults(doc, method=None):
	"""doc_events → Company → on_update"""
	if not is_lao_country(doc.country):
		return

	if doc.default_currency != "LAK":
		frappe.msgprint(
			_("Lao companies should use LAK (Lao Kip ₭) as the default currency."),
			indicator="orange",
			title=_("Lao Currency Notice"),
		)
