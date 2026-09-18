# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
The form scripts, asked of the server they call — the Desk half of Phase 0.4.

WHY THIS FILE EXISTS
    `BERP-LAO-VERIFY-001` step 0.4 is still open because the three Desk surfaces —
    the two form scripts and the print format — have been checked by **reading**,
    not by clicking. Nobody has opened a Company form in a browser.

    A human still has to. But a large part of what a human would find is
    mechanically checkable, and this is the part that breaks silently:

        a form script calls the server by DOTTED STRING.

    `frappe.call({ method: "berp_lao.lao_regional.chart_of_accounts..." })` is a
    string. Rename the module and nothing fails at import, nothing fails a test,
    `bench migrate` is clean — and the button does nothing when a user presses it.
    The same is true of a method that exists but is not whitelisted: the call
    returns a permission error the developer never sees.

    This app renamed a whole package two commits before this file was written
    (`taxris` → `e_filing`, ADR-A3). That rename happened to touch no JavaScript.
    Nothing would have told us if it had.

    `hooks.py` has had `test_every_hooked_method_resolves` since early on. The form
    scripts had no equivalent. This is it.

WHAT THIS CANNOT DO
    It does not prove a button renders, is placed sensibly, or is reachable by a
    user with the right role. Step 0.4 stays open for a person. This closes the
    failure mode that a person would be least likely to attribute correctly —
    pressing a button and getting nothing.
"""

import os
import re

import frappe

try:  # Frappe v16+
	from frappe.tests import IntegrationTestCase as _TestCase
except ImportError:  # Frappe v15
	from frappe.tests.utils import FrappeTestCase as _TestCase

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: A dotted path into this app, as a form script writes it in a string.
DOTTED_CALL_RE = re.compile(r"[\"']((?:berp_lao)(?:\.[A-Za-z_][A-Za-z0-9_]*)+)[\"']")
#: `frappe.ui.form.on("Sales Invoice", {`
FORM_ON_RE = re.compile(r"frappe\.ui\.form\.on\(\s*[\"']([^\"']+)[\"']")
#: Anything the script reads off the boot payload.
BOOT_KEY_RE = re.compile(r"frappe\.boot\.([A-Za-z_][A-Za-z0-9_]*)")
#: Fields the script names on a document it is bound to.
DOC_FIELD_RE = re.compile(r"(?:frm\.doc|doc)\.(lao_[a-z0-9_]+)")


def _script_paths() -> dict[str, str]:
	"""Every form script this app registers, by the DocType it is bound to."""
	from berp_lao import hooks

	return {
		doctype: os.path.join(APP_DIR, relative)
		for doctype, relative in (getattr(hooks, "doctype_js", None) or {}).items()
	}


class TestClientScripts(_TestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.scripts = {}
		for doctype, path in _script_paths().items():
			with open(path, encoding="utf-8") as handle:
				cls.scripts[doctype] = (path, handle.read())

	def test_the_app_registers_form_scripts_at_all(self):
		"""A loader that silently found nothing would pass every test below."""
		self.assertTrue(self.scripts, "hooks.doctype_js registers no form scripts")

	def test_every_registered_script_file_exists(self):
		"""Only THIS app's hooks.

		The first cut read `frappe.get_hooks("doctype_js")`, which is the merged map
		from every installed app, and duly asserted that Frappe's own
		`public/js/event.js` lives inside berp_lao. Ask the module, not the site.
		"""
		for doctype, path in _script_paths().items():
			with self.subTest(doctype=doctype, path=os.path.relpath(path, APP_DIR)):
				self.assertTrue(
					os.path.exists(path),
					f"{doctype} is bound to {os.path.relpath(path, APP_DIR)}, which is not shipped",
				)

	def test_every_script_binds_to_the_doctype_it_is_registered_for(self):
		"""A script registered for Company that calls frappe.ui.form.on("Customer") never runs."""
		for doctype, (path, source) in self.scripts.items():
			with self.subTest(doctype=doctype):
				bound = set(FORM_ON_RE.findall(source))
				self.assertIn(
					doctype,
					bound,
					f"{os.path.basename(path)} is registered for {doctype} but binds to {bound or 'nothing'}",
				)

	def test_every_doctype_it_binds_to_exists(self):
		for _doctype, (path, source) in self.scripts.items():
			for bound in set(FORM_ON_RE.findall(source)):
				with self.subTest(script=os.path.basename(path), bound=bound):
					self.assertTrue(frappe.db.exists("DocType", bound), f"no DocType {bound}")

	def test_every_server_method_a_script_calls_resolves(self):
		"""The rename defect. A dotted string does not fail at import.

		This is the one that matters: the module can be renamed, the method can be
		moved, and nothing anywhere reports it until a user presses the button.
		"""
		checked = 0
		for _doctype, (path, source) in self.scripts.items():
			for dotted in sorted(set(DOTTED_CALL_RE.findall(source))):
				checked += 1
				with self.subTest(script=os.path.basename(path), method=dotted):
					try:
						resolved = frappe.get_attr(dotted)
					except Exception as exc:
						self.fail(
							f"{os.path.basename(path)} calls {dotted}, which does not resolve: "
							f"{type(exc).__name__}: {exc}"
						)
					self.assertTrue(callable(resolved), f"{dotted} is not callable")
		self.assertGreater(checked, 0, "no server calls found — has the pattern drifted?")

	def test_every_server_method_a_script_calls_is_whitelisted(self):
		"""A method that exists but is not whitelisted fails at the user, not at us.

		`frappe.call` on a non-whitelisted method returns a permission error. The
		button appears to do nothing, and nothing server-side looks wrong.
		"""
		for _doctype, (path, source) in self.scripts.items():
			for dotted in sorted(set(DOTTED_CALL_RE.findall(source))):
				with self.subTest(script=os.path.basename(path), method=dotted):
					method = frappe.get_attr(dotted)
					self.assertTrue(
						getattr(method, "whitelisted", False)
						or dotted in getattr(frappe, "whitelisted", {})
						or method in getattr(frappe, "whitelisted", {}),
						f"{dotted} is called from {os.path.basename(path)} but is not "
						"@frappe.whitelist()'d — the button will fail with a permission error",
					)

	def test_every_document_field_a_script_reads_exists_on_that_doctype(self):
		"""`frm.doc.lao_invoice_type` on a DocType without the field is silently undefined."""
		for doctype, (path, source) in self.scripts.items():
			meta = frappe.get_meta(doctype)
			known = {field.fieldname for field in meta.fields}
			for fieldname in sorted(set(DOC_FIELD_RE.findall(source))):
				with self.subTest(script=os.path.basename(path), field=fieldname):
					self.assertIn(
						fieldname,
						known,
						f"{os.path.basename(path)} reads {fieldname}, which {doctype} does not have",
					)

	def test_every_boot_key_a_script_reads_is_actually_published(self):
		"""The country fix depends on this, and it is the reason it exists.

		The scripts must not hardcode a country name — Frappe's record is
		"Lao Peoples Democratic Republic", not "Laos" — so `extend_bootinfo`
		publishes the resolved name. If that hook stopped populating the key, the
		scripts would read `undefined` and quietly compare against nothing.
		"""
		from berp_lao.lao_regional.country import extend_bootinfo

		published = frappe._dict()
		extend_bootinfo(published)

		for _doctype, (path, source) in self.scripts.items():
			for key in sorted(set(BOOT_KEY_RE.findall(source))):
				if not key.startswith("berp_lao"):
					continue  # a Frappe-owned boot key is not ours to assert
				with self.subTest(script=os.path.basename(path), key=key):
					self.assertIn(
						key,
						published,
						f"{os.path.basename(path)} reads frappe.boot.{key}, which "
						"extend_bootinfo does not publish",
					)

	def test_the_country_boot_key_resolves_to_a_real_country(self):
		"""End to end: the key is published AND it names a Country that exists."""
		from berp_lao.lao_regional.country import LAO_COUNTRY_CODE, extend_bootinfo

		published = frappe._dict()
		extend_bootinfo(published)
		name = published.get("berp_lao_country")

		self.assertTrue(name, "extend_bootinfo published no country name")
		self.assertNotEqual(name, "Laos", "the defect this whole mechanism exists to prevent")
		self.assertEqual((frappe.db.get_value("Country", name, "code") or "").lower(), LAO_COUNTRY_CODE)

	def test_no_script_hardcodes_a_country_name(self):
		"""The guard in test_lao_regional covers .py and .js across the app.

		Repeated here against the registered scripts specifically, because these are
		the files where the original defect lived and where it would hurt most: a
		client-side comparison fails silently, with no server log at all.
		"""
		offenders = []
		for _doctype, (path, source) in self.scripts.items():
			for number, line in enumerate(source.splitlines(), 1):
				if line.strip().startswith(("//", "*", "/*")):
					continue
				if '"Laos"' in line or "'Laos'" in line:
					offenders.append(f"{os.path.basename(path)}:{number}")
		self.assertEqual(offenders, [], "compare on frappe.boot.berp_lao_country: " + ", ".join(offenders))
