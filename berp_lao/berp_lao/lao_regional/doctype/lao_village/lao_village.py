# Copyright (c) 2026, BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.model.document import Document


class LaoVillage(Document):
	"""Master record for a Lao administrative village (ບ້ານ)."""

	def validate(self):
		"""Ensure village name is provided in Lao and linked to a district."""
		if not self.village_name_lo:
			frappe.throw(frappe._("Village name in Lao (ຊື່ບ້ານ) is required."))
		if not self.district:
			frappe.throw(frappe._("Lao District is required for a village."))
