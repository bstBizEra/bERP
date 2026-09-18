// Copyright (c) 2026, BizEra / BSTBizEra and contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Sales Invoice", {
	company: function (frm) {
		set_lao_flag(frm);
	},

	refresh: function (frm) {
		set_lao_flag(frm);
	},

	lao_invoice_type: function (frm) {
		if (!frm.doc.__lao_company) {
			return;
		}
		// Export and exempt invoices carry no output VAT; nudge before submit
		// rather than after, when the taxes table is already wrong.
		show_vat_hint(frm);
	},

	validate: function (frm) {
		// Server-side validate_lao_sales_invoice is the authority. This only
		// surfaces the same hint earlier, without a round trip.
		if (frm.doc.__lao_company) {
			show_vat_hint(frm);
		}
	},
});

function set_lao_flag(frm) {
	if (!frm.doc.company) {
		frm.doc.__lao_company = false;
		return;
	}

	// See lao_company.js: the Lao country record is not named "Laos".
	const lao_country = (frappe.boot && frappe.boot.berp_lao_country) || null;
	if (!lao_country) {
		frm.doc.__lao_company = false;
		return;
	}

	frappe.db.get_value("Company", frm.doc.company, "country").then((r) => {
		frm.doc.__lao_company = Boolean(r && r.message && r.message.country === lao_country);
		if (frm.doc.__lao_company && !frm.doc.__islocal) {
			frm.add_custom_button(
				__("Lao VAT Compliance Check"),
				() => show_vat_hint(frm, true),
				__("Lao Tools")
			);
		}
	});
}

function show_vat_hint(frm, always_confirm) {
	const invoice_type = frm.doc.lao_invoice_type || "Standard";
	const exempt = ["Export (0%)", "VAT Exempt"].includes(invoice_type);
	const has_vat = (frm.doc.taxes || []).some((tax) => flt(tax.rate) === 10.0);

	if (exempt && has_vat) {
		frappe.show_alert(
			{
				message: __("Invoice Type is {0} but a 10% VAT row is present.", [invoice_type]),
				indicator: "orange",
			},
			7
		);
	} else if (!exempt && !has_vat) {
		frappe.show_alert(
			{
				message: __("Lao {0} invoices require VAT 10% (ອາກອນ 10%).", [invoice_type]),
				indicator: "orange",
			},
			7
		);
	} else if (always_confirm) {
		frappe.show_alert(
			{ message: __("Lao VAT treatment looks correct (ອາກອນ 10% ຖືກຕ້ອງ)."), indicator: "green" },
			5
		);
	}
}
