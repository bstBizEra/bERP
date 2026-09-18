# Copyright (c) 2026, BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.model.document import Document


class LaoDistrict(Document):
	"""Master record for a Lao administrative district (ເມືອງ)."""

	def validate(self):
		"""Ensure district name is provided in Lao and linked to a province."""
		if not self.district_name_lo:
			frappe.throw(frappe._("District name in Lao (ຊື່ເມືອງ) is required."))
		if not self.province:
			frappe.throw(frappe._("Lao Province is required for a district."))
