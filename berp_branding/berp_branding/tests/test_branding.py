# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Tests for per-tenant branding.

The asset tests matter more than they look: these values come from a hand-edited
site_config.json and land in `src` attributes, so a bad value has to be dropped
rather than rendered.
"""

from contextlib import contextmanager

import frappe

try:  # Frappe v16+
	from frappe.tests import IntegrationTestCase as _TestCase
except ImportError:  # Frappe v15
	from frappe.tests.utils import FrappeTestCase as _TestCase

from berp_branding.brand import (
	BRAND_FIELDS,
	DEFAULT_BRAND,
	MAX_BRAND_LENGTH,
	PLATFORM_DEFAULTS,
	_brand_asset,
	apply_branding,
	boot_session,
	brand_name,
	branding,
	branding_status,
	shipped_assets,
	update_website_context,
)


@contextmanager
def site_config(**values):
	"""Temporarily override frappe.conf keys."""
	previous = {k: frappe.conf.get(k) for k in values}
	frappe.conf.update(values)
	try:
		yield
	finally:
		for key, old in previous.items():
			if old is None:
				frappe.conf.pop(key, None)
			else:
				frappe.conf[key] = old


class TestBrandName(_TestCase):
	def test_falls_back_when_unset(self):
		with site_config(berp_brand_name=None):
			frappe.conf.pop("berp_brand_name", None)
			self.assertEqual(brand_name(), DEFAULT_BRAND)

	def test_blank_and_whitespace_fall_back(self):
		for value in ("", "   ", "\t\n"):
			with self.subTest(value=repr(value)), site_config(berp_brand_name=value):
				self.assertEqual(brand_name(), DEFAULT_BRAND)

	def test_non_string_falls_back(self):
		for value in (42, [], {}, True):
			with self.subTest(value=value), site_config(berp_brand_name=value):
				self.assertEqual(brand_name(), DEFAULT_BRAND)

	def test_is_trimmed_and_capped(self):
		with site_config(berp_brand_name="  LaoCap ERP  "):
			self.assertEqual(brand_name(), "LaoCap ERP")
		with site_config(berp_brand_name="x" * 500):
			self.assertEqual(len(brand_name()), MAX_BRAND_LENGTH)


class TestBrandAssets(_TestCase):
	def test_site_relative_paths_are_accepted(self):
		with site_config(berp_brand_logo="/files/laocap-logo.svg"):
			self.assertEqual(_brand_asset("berp_brand_logo"), "/files/laocap-logo.svg")

	def test_https_urls_are_accepted(self):
		with site_config(berp_brand_logo="https://cdn.bizera.la/logo.svg"):
			self.assertEqual(_brand_asset("berp_brand_logo"), "https://cdn.bizera.la/logo.svg")

	def test_unsafe_and_malformed_values_are_dropped(self):
		for value in (
			"javascript:alert(1)",
			"http://cdn.bizera.la/logo.svg",  # plain http
			"//cdn.bizera.la/logo.svg",  # protocol-relative
			"data:image/svg+xml;base64,AAAA",
			"logo.svg",  # not rooted
			"",
			"   ",
			7,
			None,
		):
			with self.subTest(value=repr(value)), site_config(berp_brand_logo=value):
				self.assertIsNone(_brand_asset("berp_brand_logo"))

	def test_branding_always_carries_the_platform_identity(self):
		"""Unconfigured means bERP, not empty.

		This assertion was inverted when the app began shipping platform assets. It
		used to require that app_logo be ABSENT when nothing was configured, which
		is what left a fresh install showing ERPNext's logo.
		"""
		with site_config(berp_brand_name=None, berp_brand_logo=None):
			frappe.conf.pop("berp_brand_name", None)
			frappe.conf.pop("berp_brand_logo", None)
			values = branding()
			self.assertEqual(values["app_name"], DEFAULT_BRAND)
			self.assertEqual(values["app_logo"], PLATFORM_DEFAULTS["app_logo"])
			self.assertEqual(values["favicon"], PLATFORM_DEFAULTS["favicon"])
			# banner_image has no platform default, so it stays absent
			self.assertNotIn("banner_image", values)

	def test_branding_maps_every_configured_key(self):
		with site_config(
			berp_brand_name="LaoCap ERP",
			berp_brand_logo="/files/l.svg",
			berp_brand_favicon="/files/f.png",
			berp_brand_splash="/files/b.png",
		):
			values = branding()
			self.assertEqual(set(values), set(BRAND_FIELDS.values()))
			self.assertEqual(values["favicon"], "/files/f.png")
			self.assertEqual(values["banner_image"], "/files/b.png")


class TestWebsiteContext(_TestCase):
	def test_label_is_html_escaped(self):
		context = {}
		with site_config(berp_brand_name='LaoCap "ERP" & <script>'):
			update_website_context(context)
		self.assertNotIn("<script>", context["brand_html"])
		self.assertIn("&lt;script&gt;", context["brand_html"])
		self.assertIn("&amp;", context["brand_html"])
		self.assertIn("&quot;", context["brand_html"])

	def test_assets_are_only_set_when_configured(self):
		context = {}
		with site_config(berp_brand_logo=None, berp_brand_favicon=None):
			frappe.conf.pop("berp_brand_logo", None)
			frappe.conf.pop("berp_brand_favicon", None)
			update_website_context(context)
		self.assertNotIn("app_logo", context)
		self.assertNotIn("favicon", context)

	def test_boot_session_exposes_the_brand(self):
		bootinfo = frappe._dict()
		with site_config(berp_brand_name="LaoCap ERP"):
			boot_session(bootinfo)
		self.assertEqual(bootinfo.berp_brand["name"], "LaoCap ERP")
		self.assertEqual(bootinfo.berp_brand["site"], frappe.local.site)


class TestApplyBranding(_TestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_writes_the_label_into_website_settings(self):
		frappe.db.set_single_value("Website Settings", "app_name", "")
		with site_config(berp_brand_name="LaoCap ERP"):
			result = apply_branding(force=1)
		self.assertEqual(result["applied"].get("app_name"), "LaoCap ERP")
		self.assertEqual(frappe.db.get_single_value("Website Settings", "app_name"), "LaoCap ERP")

	def test_does_not_overwrite_an_existing_value_without_force(self):
		frappe.db.set_single_value("Website Settings", "app_name", "Set By Hand")
		with site_config(berp_brand_name="LaoCap ERP"):
			result = apply_branding()
		self.assertNotIn("app_name", result["applied"])
		self.assertEqual(frappe.db.get_single_value("Website Settings", "app_name"), "Set By Hand")

	def test_force_overwrites(self):
		frappe.db.set_single_value("Website Settings", "app_name", "Set By Hand")
		with site_config(berp_brand_name="LaoCap ERP"):
			apply_branding(force=1)
		self.assertEqual(frappe.db.get_single_value("Website Settings", "app_name"), "LaoCap ERP")

	def test_is_idempotent(self):
		frappe.db.set_single_value("Website Settings", "app_name", "")
		with site_config(berp_brand_name="LaoCap ERP"):
			apply_branding(force=1)
			second = apply_branding(force=1)
		self.assertEqual(second["applied"], {})

	def test_never_blanks_a_field(self):
		"""No path through apply_branding may leave a brand field empty.

		Narrowed deliberately from an earlier "never CHANGES an unconfigured field".
		That is no longer true and should not be: with a platform default in place,
		force=1 asserts the bERP identity over an unconfigured field. What must
		never happen is a field ending up blank, which is what would actually break
		a site. The two cases below pin the new semantics explicitly.
		"""
		frappe.db.set_single_value("Website Settings", "app_logo", "/files/kept.svg")
		with site_config(berp_brand_logo=None):
			frappe.conf.pop("berp_brand_logo", None)
			apply_branding(force=1)
		self.assertTrue(frappe.db.get_single_value("Website Settings", "app_logo"))

	def test_force_resets_an_unconfigured_field_to_the_platform_default(self):
		"""force=1 means "assert the bERP identity" — this is what after_install does."""
		frappe.db.set_single_value("Website Settings", "app_logo", "/files/old.svg")
		with site_config(berp_brand_logo=None):
			frappe.conf.pop("berp_brand_logo", None)
			apply_branding(force=1)
		self.assertEqual(
			frappe.db.get_single_value("Website Settings", "app_logo"),
			PLATFORM_DEFAULTS["app_logo"],
		)

	def test_without_force_an_operator_value_survives_the_platform_default(self):
		"""after_migrate must not undo a logo an operator set by hand."""
		frappe.db.set_single_value("Website Settings", "app_logo", "/files/operator.svg")
		with site_config(berp_brand_logo=None):
			frappe.conf.pop("berp_brand_logo", None)
			apply_branding()
		self.assertEqual(frappe.db.get_single_value("Website Settings", "app_logo"), "/files/operator.svg")


class TestBrandingStatus(_TestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_reports_where_the_logo_resolves_from(self):
		frappe.db.set_single_value("Website Settings", "app_logo", "/files/laocap.svg")
		status = branding_status()
		self.assertEqual(status["resolved_from"], "Website Settings")
		self.assertEqual(status["resolved_logo"], "/files/laocap.svg")
		self.assertEqual(status["site"], frappe.local.site)


class TestLogoResolution(_TestCase):
	"""Frappe's get_app_logo() makes the app_logo_url hook a trap for this app.

	navbar_settings.get_app_logo() takes hooks("app_logo_url")[0] — Frappe's own —
	unless exactly two apps declare it, in which case it takes [1]. So on a
	frappe + erpnext + berp_branding site the hook never wins, and on a
	frappe + berp_branding site it wins. Which of those happens depends on how many
	OTHER apps declare the hook — not something a branding app may rest on. Website
	Settings is checked first and is where branding actually goes.

	(The original reason for omitting the hook was that it would serve an asset the
	app did not ship. That reason expired when public/images/ was added; the
	positional one above is why it stays absent.)
	"""

	def test_the_app_declares_no_app_logo_url(self):
		from berp_branding import hooks

		self.assertFalse(
			getattr(hooks, "app_logo_url", None),
			"declaring app_logo_url either loses to Frappe or serves a missing asset; "
			"write branding to Website Settings instead",
		)

	def test_website_settings_is_what_get_app_logo_checks_first(self):
		from frappe.core.doctype.navbar_settings.navbar_settings import get_app_logo

		original = frappe.db.get_single_value("Website Settings", "app_logo")
		try:
			frappe.db.set_single_value("Website Settings", "app_logo", "/files/_probe_logo.svg")
			frappe.clear_cache()
			self.assertEqual(get_app_logo(), "/files/_probe_logo.svg")
		finally:
			frappe.db.set_single_value("Website Settings", "app_logo", original)
			frappe.clear_cache()

	def test_any_asset_the_app_declares_actually_exists(self):
		"""Nothing may point at a file the app does not ship."""
		import os

		app_path = frappe.get_app_path("berp_branding")
		declared = []
		for hook in ("app_logo_url", "app_include_css", "app_include_js"):
			declared += [
				(hook, v)
				for v in (frappe.get_hooks(hook, app_name="berp_branding") or [])
				if isinstance(v, str)
			]
		declared += [("PLATFORM_DEFAULTS", v) for v in PLATFORM_DEFAULTS.values() if isinstance(v, str)]

		for source, value in declared:
			if not value.startswith("/assets/berp_branding/"):
				continue
			relative = value[len("/assets/berp_branding/") :]
			with self.subTest(source=source, asset=value):
				self.assertTrue(
					os.path.exists(os.path.join(app_path, "public", relative)),
					f"{source} points at {value}, which this app does not ship",
				)


class TestPlatformDefaults(_TestCase):
	"""The bERP identity a site gets when it configures nothing.

	This is the difference between a white-label toolkit and a branded product: a
	fresh install must present bERP, not ERPNext.
	"""

	def tearDown(self):
		frappe.db.rollback()

	def test_an_unconfigured_site_resolves_to_berp(self):
		for key in BRAND_FIELDS:
			frappe.conf.pop(key, None)
		resolved = branding()
		self.assertEqual(resolved["app_name"], DEFAULT_BRAND)
		self.assertEqual(resolved["app_logo"], PLATFORM_DEFAULTS["app_logo"])
		self.assertEqual(resolved["favicon"], PLATFORM_DEFAULTS["favicon"])

	def test_a_tenant_override_beats_the_platform_default(self):
		with site_config(berp_brand_name="LaoCap ERP", berp_brand_logo="/files/laocap.svg"):
			resolved = branding()
		self.assertEqual(resolved["app_name"], "LaoCap ERP")
		self.assertEqual(resolved["app_logo"], "/files/laocap.svg")
		# not overridden, so the platform favicon is still inherited
		self.assertEqual(resolved["favicon"], PLATFORM_DEFAULTS["favicon"])

	def test_a_rejected_tenant_asset_falls_back_to_the_platform_default(self):
		"""A hostile value must not leave the site with no logo at all (WL-001 §45)."""
		with site_config(berp_brand_logo="javascript:alert(1)"):
			resolved = branding()
		self.assertEqual(resolved["app_logo"], PLATFORM_DEFAULTS["app_logo"])

	def test_every_platform_default_asset_is_built_and_served(self):
		status = shipped_assets()
		self.assertTrue(status, "no platform default assets declared")
		for field, entry in status.items():
			with self.subTest(field=field):
				self.assertIn(entry["status"], ("READY", "UNKNOWN"))
				self.assertNotEqual(
					entry["status"],
					"MISSING",
					f"{field} points at {entry['path']}, which is not built — "
					f"run: bench build --app berp_branding",
				)
