# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Tests for the berp_lao localisation.

The data-integrity tests (chart, fixtures, tax templates) touch no database and
are the ones that catch the failure mode this app is most exposed to: a JSON file
drifting out of step with the code that reads it.
"""

import itertools
import json
import os
import pathlib

import frappe

try:  # Frappe v16+
	from frappe.tests import IntegrationTestCase as _TestCase
except ImportError:  # Frappe v15
	from frappe.tests.utils import FrappeTestCase as _TestCase

from berp_lao.lao_regional.chart_of_accounts.lao_pcg import get_chart
from berp_lao.lao_regional.country import is_lao_company
from berp_lao.lao_regional.report.lao_vat_return.lao_vat_return import get_columns

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META_KEYS = {
	"account_number",
	"account_type",
	"root_type",
	"is_group",
	"account_name",
	"tax_rate",
	"account_currency",
}
VALID_ROOT_TYPES = {"Asset", "Liability", "Equity", "Income", "Expense"}


def _walk(node, out):
	for key, value in node.items():
		if key in META_KEYS or not isinstance(value, dict):
			continue
		out.append((key, value))
		_walk(value, out)


def _load(*parts):
	with open(os.path.join(APP_DIR, *parts), encoding="utf-8") as f:
		return json.load(f)


class TestLaoChartOfAccounts(_TestCase):
	def setUp(self):
		self.tree = get_chart()
		self.nodes = []
		_walk(self.tree, self.nodes)

	def test_every_root_declares_a_valid_root_type(self):
		for name, node in self.tree.items():
			self.assertIn("root_type", node, f"root {name!r} has no root_type")
			self.assertIn(node["root_type"], VALID_ROOT_TYPES, f"root {name!r}: {node['root_type']}")
			self.assertTrue(node.get("is_group"), f"root {name!r} must be a group")

	def test_no_nested_root_type_overrides(self):
		"""ERPNext applies the root's root_type to the whole subtree, so a
		root_type on a non-root node would silently do nothing."""
		roots = {id(node) for node in self.tree.values()}
		for name, node in self.nodes:
			if id(node) in roots:
				continue
			self.assertNotIn("root_type", node, f"{name!r} declares root_type below a root")

	def test_every_postable_account_has_a_number(self):
		"""Leaves carry the statutory PCG number. Groups may not be able to.

		ERPNext validates `account_number` uniqueness per *company*, not per root,
		and this chart splits class 1 and class 4 across root types and splits
		groups 44 and 48 within class 4 — so four numbers would appear twice.
		ERPNext's own French PCG solves this by carrying the class digit in the
		account *name* and setting no `account_number` anywhere, and this chart
		does the same for exactly the nodes that would collide. Every postable
		account keeps its number, which is what the statute and the tax templates
		depend on.
		"""
		for name, node in self.nodes:
			if node.get("is_group"):
				continue
			self.assertTrue(node.get("account_number"), f"{name!r} has no account_number")

	def test_account_numbers_are_unique_across_the_whole_chart(self):
		"""The regression a real bench found: ERPNext enforces this per company.

		`Account.validate_account_number` refuses a number already used by any
		other account in the same company, so a duplicate anywhere in this file
		aborts chart installation partway through and leaves a half-built tree.
		"""
		numbers = [node["account_number"] for _n, node in self.nodes if node.get("account_number")]
		duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
		self.assertEqual(duplicates, [], f"duplicate account numbers: {duplicates}")

	def test_unnumbered_groups_carry_their_class_digit_in_the_name(self):
		"""A group without a number must still show the reader where it sits."""
		for name, node in self.nodes:
			if node.get("account_number"):
				continue
			self.assertTrue(node.get("is_group"), f"{name!r} is postable but unnumbered")
			self.assertRegex(name, r"^\d+ ", f"{name!r} has no account_number and no class digit in its name")

	def test_every_account_type_is_valid_in_this_erpnext(self):
		"""The other regression a real bench found.

		"Stock In Hand" was a valid Account Type in ERPNext v13/v14 and is not in
		v15. Nothing in a JSON audit can know that — the allowed values live in the
		Account doctype's own select options, so read them from the installed
		ERPNext rather than from a list copied into this file.
		"""
		allowed = set(frappe.get_meta("Account").get_field("account_type").options.split("\n"))
		for name, node in self.nodes:
			account_type = node.get("account_type")
			if not account_type:
				continue
			with self.subTest(account=name):
				self.assertIn(
					account_type, allowed, f"{name!r}: {account_type!r} is not a valid Account Type"
				)

	def test_receivable_and_payable_leaves_exist(self):
		leaf_types = {node.get("account_type") for _n, node in self.nodes if not node.get("is_group")}
		self.assertIn("Receivable", leaf_types)
		self.assertIn("Payable", leaf_types)

	def test_all_five_root_types_are_represented(self):
		self.assertEqual({node["root_type"] for node in self.tree.values()}, VALID_ROOT_TYPES)


class TestLaoTaxTemplateData(_TestCase):
	def setUp(self):
		self.data = _load("lao_regional", "data", "lao_tax_templates.json")
		nodes = []
		_walk(get_chart(), nodes)
		self.leaf_numbers = {node["account_number"] for _n, node in nodes if not node.get("is_group")}

	def test_every_referenced_account_number_is_a_chart_leaf(self):
		referenced = set()
		for key in ("sales_taxes_and_charges_templates", "purchase_taxes_and_charges_templates"):
			for template in self.data[key]:
				referenced.update(tax["account_number"] for tax in template["taxes"])
		referenced.update(c["account_number"] for c in self.data["tax_withholding_categories"])

		missing = sorted(referenced - self.leaf_numbers)
		self.assertEqual(missing, [], f"tax templates reference accounts not in the chart: {missing}")

	def test_withholding_categories_are_uniquely_named(self):
		names = [c["name"] for c in self.data["tax_withholding_categories"]]
		self.assertEqual(len(names), len(set(names)))

	def test_withholding_accounts_are_not_shared_between_categories(self):
		numbers = [c["account_number"] for c in self.data["tax_withholding_categories"]]
		self.assertEqual(len(numbers), len(set(numbers)))

	def test_every_withholding_rate_window_is_well_formed(self):
		"""Rates must be dated, ordered, and must not overlap within a category."""
		for category in self.data["tax_withholding_categories"]:
			rows = category["rates"]
			with self.subTest(category=category["name"]):
				self.assertTrue(rows, "at least one rate row is required")
				for row in rows:
					self.assertLess(row["from_date"], row["to_date"])
					self.assertGreater(row["rate"], 0)

				ordered = sorted(rows, key=lambda r: r["from_date"])
				for earlier, later in itertools.pairwise(ordered):
					self.assertLess(
						earlier["to_date"],
						later["from_date"],
						f"{category['name']}: rate windows overlap",
					)

	def test_law_88_na_rate_changes_are_carried_as_dated_rows(self):
		"""Law No. 88/NA moved four rates on 1 July 2026.

		Each of these carried the wrong rate at some point in development, and the
		failure mode is silent: an invoice dated either side of the boundary simply
		withholds the wrong amount. Pin them.
		"""
		expected = {
			"Services": (5.0, 10.0),
			"Construction": (2.0, 5.0),
			"E-commerce": (2.0, 10.0),
			"Sports & Performing Arts": (10.0, 5.0),
		}
		by_category = {c["category_name"]: c for c in self.data["tax_withholding_categories"]}

		for name, (before, after) in expected.items():
			with self.subTest(category=name):
				self.assertIn(name, by_category, f"{name} is missing from the tax templates")
				rows = sorted(by_category[name]["rates"], key=lambda r: r["from_date"])
				self.assertEqual(len(rows), 2, "expected a rate row either side of 88/NA")
				self.assertEqual(rows[0]["rate"], before)
				self.assertEqual(rows[0]["to_date"], "2026-06-30")
				self.assertEqual(rows[1]["from_date"], "2026-07-01")
				self.assertEqual(rows[1]["rate"], after)

	def test_unchanged_withholding_rates_stay_single_rowed(self):
		"""The four rates 88/NA left alone should not have grown a boundary."""
		expected = {
			"Dividends": 10.0,
			"Rental": 10.0,
			"Teaching": 5.0,
			"Royalties": 5.0,
			"Share Transfer": 2.0,
		}
		by_category = {c["category_name"]: c for c in self.data["tax_withholding_categories"]}
		for name, rate in expected.items():
			with self.subTest(category=name):
				rows = by_category[name]["rates"]
				self.assertEqual(len(rows), 1)
				self.assertEqual(rows[0]["rate"], rate)

	def test_exactly_one_default_per_template_type(self):
		for key in ("sales_taxes_and_charges_templates", "purchase_taxes_and_charges_templates"):
			defaults = [t for t in self.data[key] if t.get("is_default")]
			self.assertEqual(len(defaults), 1, f"{key} must have exactly one default")


class TestGeographyFixtures(_TestCase):
	def test_eighteen_provinces(self):
		provinces = _load("fixtures", "lao_province.json")
		self.assertEqual(len(provinces), 18)

	def test_every_district_links_to_a_known_province(self):
		provinces = {p["name"] for p in _load("fixtures", "lao_province.json")}
		orphans = sorted(
			d["name"] for d in _load("fixtures", "lao_district.json") if d.get("province") not in provinces
		)
		self.assertEqual(orphans, [], f"districts with an unknown province: {orphans}")

	def test_every_record_declares_its_doctype(self):
		for filename, doctype in (
			("lao_province.json", "Lao Province"),
			("lao_district.json", "Lao District"),
		):
			for record in _load("fixtures", filename):
				self.assertEqual(record.get("doctype"), doctype)
				self.assertTrue(record.get("name"))


class TestHooksWiring(_TestCase):
	def test_every_hooked_method_resolves(self):
		"""A dotted path in hooks.py that does not import is an install-time crash."""
		from berp_lao import hooks

		# A hook value is either one dotted path or a list of them — both
		# after_migrate and a doc_event can be either.
		def flatten(value):
			return [value] if isinstance(value, str) else list(value)

		paths = []
		for hook in (
			hooks.after_install,
			hooks.after_migrate,
			hooks.before_uninstall,
			hooks.extend_bootinfo,
		):
			paths.extend(flatten(hook))
		for events in hooks.doc_events.values():
			for value in events.values():
				paths.extend(flatten(value))

		for path in paths:
			with self.subTest(path=path):
				self.assertTrue(callable(frappe.get_attr(path)), f"{path} is not callable")

	def test_the_lao_country_record_resolves(self):
		"""The regression that made every doc_event in this app dead code.

		Until a bench run proved otherwise, `is_lao_company` compared the company's
		country to the literal string "Laos". Frappe seeds the record as "Lao
		Peoples Democratic Republic", so the comparison was never true on a real
		site and not one validation, warning or in-words override could ever fire.
		Match on the ISO code; assert here that it resolves and that the old
		spelling is *not* what comes back.
		"""
		from berp_lao.lao_regional.country import (
			LAO_COUNTRY_CODE,
			is_lao_country,
			lao_country_name,
		)

		name = lao_country_name()
		self.assertTrue(name, "no Country record with ISO code 'la' on this site")
		self.assertEqual(frappe.db.get_value("Country", name, "code").lower(), LAO_COUNTRY_CODE)
		self.assertTrue(is_lao_country(name))
		self.assertFalse(is_lao_country("Laos"))
		self.assertFalse(is_lao_country(None))
		self.assertFalse(is_lao_country("Thailand"))

	def test_no_source_file_hardcodes_the_country_name(self):
		"""Guards the fix above from being undone one file at a time.

		The question is *does any code compare against a country name*, not *does
		the text appear anywhere*. The first version of this check asked the second
		and flagged the docstring that explains the defect — a false positive from a
		test that had encoded a proxy for its own question. Python is parsed and
		only real string literals are inspected; docstrings and comments are not
		literals-in-code and are allowed to name the thing. JavaScript has no parser
		here, so it keeps the line scan with a comment skip.

		See docs/REVIEW-METHOD.md rule 9 — prove the proxy matches the question.
		"""
		import ast

		forbidden = {"Laos", "LAOS", "laos"}
		offenders = []

		def scan_python(path):
			source = pathlib.Path(path).read_text(encoding="utf-8")
			tree = ast.parse(source, filename=path)
			docstrings = {
				id(node.body[0].value)
				for node in ast.walk(tree)
				if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
				and node.body
				and isinstance(node.body[0], ast.Expr)
				and isinstance(node.body[0].value, ast.Constant)
				and isinstance(node.body[0].value.value, str)
			}
			for node in ast.walk(tree):
				if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
					continue
				if id(node) in docstrings:
					continue  # prose explaining the defect is not the defect
				if node.value in forbidden:
					offenders.append(f"{os.path.relpath(path, APP_DIR)}:{node.lineno}")

		def scan_javascript(path):
			with open(path, encoding="utf-8") as handle:
				for number, line in enumerate(handle, 1):
					if line.strip().startswith(("//", "*", "/*")):
						continue
					if '"Laos"' in line or "'Laos'" in line:
						offenders.append(f"{os.path.relpath(path, APP_DIR)}:{number}")

		for root, dirs, files in os.walk(APP_DIR):
			# `tests` names the old spelling on purpose, to assert it is *not* matched.
			dirs[:] = [d for d in dirs if d not in {"geo", "__pycache__", "node_modules", "tests"}]
			for filename in files:
				path = os.path.join(root, filename)
				if filename.endswith(".py"):
					scan_python(path)
				elif filename.endswith(".js"):
					scan_javascript(path)

		self.assertEqual(
			offenders,
			[],
			"match on the ISO code via lao_regional.country, not on a country name: " + ", ".join(offenders),
		)

	def test_the_country_name_guard_can_actually_fail(self):
		"""Known-bad case for the check above — REVIEW-METHOD rule 8.

		A guard that has only ever been run against passing input has not been shown
		to distinguish the cases. Feed it a file that does what it forbids, and a
		file that only talks about it, and require it to tell them apart.
		"""
		import ast
		import tempfile

		offends = 'if country == "Laos":\n\tpass\n'
		explains = '"""The first cut compared against "Laos". Do not."""\n'

		def literal_hits(source):
			tree = ast.parse(source)
			docstrings = {
				id(node.body[0].value)
				for node in ast.walk(tree)
				if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
				and node.body
				and isinstance(node.body[0], ast.Expr)
				and isinstance(node.body[0].value, ast.Constant)
				and isinstance(node.body[0].value.value, str)
			}
			return [
				node.lineno
				for node in ast.walk(tree)
				if isinstance(node, ast.Constant)
				and isinstance(node.value, str)
				and id(node) not in docstrings
				and node.value == "Laos"
			]

		with tempfile.TemporaryDirectory():
			self.assertEqual(literal_hits(offends), [1], "the guard cannot see a real match")
			self.assertEqual(literal_hits(explains), [], "the guard flags prose about the defect")

	def test_app_name_matches_the_package_directory(self):
		from berp_lao import hooks

		self.assertEqual(hooks.app_name, os.path.basename(APP_DIR))

	def test_css_bundle_referenced_by_hooks_exists(self):
		from berp_lao import hooks

		bundle = os.path.join(APP_DIR, "public", "css", hooks.app_include_css)
		self.assertTrue(os.path.exists(bundle), f"{hooks.app_include_css} is missing from public/css/")


class TestVatReport(_TestCase):
	def test_columns(self):
		fieldnames = [c["fieldname"] for c in get_columns()]
		self.assertEqual(fieldnames, ["section", "base_amount", "vat_rate", "vat_amount", "invoice_count"])

	def test_report_definition_does_not_add_a_total_row(self):
		"""The report ends with a computed 'net VAT payable' line; summing the
		column on top of it would double-count."""
		definition = _load("lao_regional", "report", "lao_vat_return", "lao_vat_return.json")
		self.assertEqual(definition["add_total_row"], 0)
		self.assertEqual(definition["ref_doctype"], "Sales Invoice")


class TestCompanyGuards(_TestCase):
	def test_is_lao_company_is_false_without_a_company(self):
		self.assertFalse(is_lao_company(None))
		self.assertFalse(is_lao_company(""))
