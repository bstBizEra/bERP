// Copyright (c) 2026, BizEra / BSTBizEra and contributors
// License: GNU General Public License v3. See license.txt

// The Country record for Lao PDR is named "Lao Peoples Democratic Republic" on a
// stock site, not "Laos", and it is editable — so the name is resolved server-side
// from the ISO code and published to frappe.boot by hooks.extend_bootinfo.
function lao_country() {
	return (frappe.boot && frappe.boot.berp_lao_country) || null;
}

function is_lao(frm) {
	const country = lao_country();
	return Boolean(country) && frm.doc.country === country;
}

frappe.ui.form.on("Company", {
	refresh: function (frm) {
		if (!is_lao(frm) || frm.is_new()) {
			return;
		}

		frm.set_df_property("lao_tax_id", "reqd", 1);
		frm.dashboard.add_indicator(__("Lao Localisation Active (ພາສາລາວ)"), "blue");

		frm.add_custom_button(
			__("Install Lao PCG Chart of Accounts"),
			() => install_chart_of_accounts(frm),
			__("Lao Tools")
		);

		frm.add_custom_button(
			__("Create Lao VAT / WHT Templates"),
			() => create_tax_templates(frm),
			__("Lao Tools")
		);
	},

	country: function (frm) {
		if (!is_lao(frm)) {
			return;
		}

		frm.set_value("default_currency", "LAK");
		frm.set_df_property("lao_tax_id", "reqd", 1);
		frappe.show_alert(
			{
				message: __("Default currency set to LAK (₭). Use Lao Tools to install the PCG Chart of Accounts."),
				indicator: "blue",
			},
			7
		);
	},
});

function install_chart_of_accounts(frm) {
	// Replacing a chart destroys the existing account tree, so make the user say so
	// explicitly. The server refuses outright once GL entries exist.
	frappe.confirm(
		__(
			"This replaces the Chart of Accounts for {0} with the Lao PCG (8-class) chart. Any existing accounts that have never been posted to will be removed. Continue?",
			[frm.doc.name.bold()]
		),
		() => {
			frappe.call({
				method: "berp_lao.lao_regional.chart_of_accounts.lao_pcg.install_lao_chart_of_accounts",
				args: { company: frm.doc.name, force: 1 },
				freeze: true,
				freeze_message: __("Creating Lao PCG Chart of Accounts…"),
				callback: () => frm.reload_doc(),
			});
		}
	);
}

function create_tax_templates(frm) {
	frappe.call({
		method: "berp_lao.setup.tax_templates.install_lao_tax_templates",
		args: { company: frm.doc.name },
		freeze: true,
		freeze_message: __("Creating Lao VAT / WHT templates…"),
	});
}
