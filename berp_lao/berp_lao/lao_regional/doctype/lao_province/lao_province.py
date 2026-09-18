# Copyright (c) 2026, BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.model.document import Document


class LaoProvince(Document):
	"""Master record for a Lao administrative province."""

	def validate(self):
		"""Ensure province name is provided in both languages."""
		if not self.province_name_lo:
			frappe.throw(frappe._("Province name in Lao (ຊື່ແຂວງ) is required."))
