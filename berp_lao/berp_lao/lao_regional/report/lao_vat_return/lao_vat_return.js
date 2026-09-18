// Copyright (c) 2026, BizEra / BSTBizEra and contributors
// License: GNU General Public License v3. See license.txt

frappe.query_reports["Lao Monthly VAT Return"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
			get_query: function () {
				// The return is only meaningful for Lao-registered companies.
				// Resolved from the ISO code server-side; see berp_lao/public/js/lao_company.js.
				return { filters: { country: (frappe.boot && frappe.boot.berp_lao_country) || "" } };
			},
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
			reqd: 1,
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && data.section && data.section.startsWith("<b>")) {
			value = `<span style="font-weight:600">${value}</span>`;
		}
		return value;
	},
};
