# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
bERP platform branding, and per-tenant white-label over it.

Two layers, in the order BERP-WL-001 §4 requires:

    PLATFORM  the bERP identity this app ships in public/images/. A site that
              configures nothing shows bERP — not ERPNext. That is the whole
              point of the app.
    TENANT    site_config.json keys, laid over the platform layer, so one bench
              serves several tenants from the same code with no per-site fork.

    {
      "berp_brand_name":    "LaoCap ERP",
      "berp_brand_logo":    "/files/laocap-logo.svg",
      "berp_brand_favicon": "/files/laocap-favicon.png",
      "berp_brand_splash":  "/files/laocap-banner.png"
    }

Where the values actually have to land is not obvious, and getting it wrong is why
the first cut of this app only changed the portal navbar. Frappe resolves the Desk
and login logo through `get_app_logo()`:

    Website Settings.app_logo  ->  Navbar Settings.app_logo  ->  hooks app_logo_url

and the hook branch takes `logos[0]` unless exactly two apps declare it — with
frappe, erpnext and this app installed there are three, so `logos[0]` is Frappe's
own logo and the hook never wins. The login page reads
`Website Settings.app_name` the same way. So the only dependable place to put
tenant branding is **Website Settings**, which is what `apply_branding` writes.
"""

from html import escape

import frappe
from frappe import _
from frappe.utils import cint

DEFAULT_BRAND = "bERP"
MAX_BRAND_LENGTH = 120

#: Where this app's own assets are served from once `bench build` has run.
ASSET_ROOT = "/assets/berp_branding/images"

#: The bERP platform identity. This is what a site shows when site_config names no
#: tenant branding at all — the point of the app is that a fresh install presents
#: bERP, not ERPNext. Every one of these is overridable per tenant through the
#: site_config keys in BRAND_FIELDS.
#:
#: These paths MUST exist under berp_branding/public/; `bench build --app
#: berp_branding` is what publishes them. A default that points at a missing file
#: is worse than no default, because a broken image becomes the platform identity
#: (BERP-WL-001 §45). shipped_assets() checks them and branding_status() reports it.
PLATFORM_DEFAULTS = {
	"app_name": DEFAULT_BRAND,
	"app_logo": f"{ASSET_ROOT}/berp-logo.svg",
	"favicon": f"{ASSET_ROOT}/berp-favicon.png",
}

#: site_config key -> Website Settings fieldname
BRAND_FIELDS = {
	"berp_brand_name": "app_name",
	"berp_brand_logo": "app_logo",
	"berp_brand_favicon": "favicon",
	"berp_brand_splash": "banner_image",
}


# ─── Reading configuration ────────────────────────────────────────────────────


def brand_name() -> str:
	"""The tenant label, always a usable non-empty string."""
	label = frappe.conf.get("berp_brand_name")
	if not isinstance(label, str):
		return DEFAULT_BRAND
	return label.strip()[:MAX_BRAND_LENGTH] or DEFAULT_BRAND


def _brand_asset(key: str) -> str | None:
	"""
	A configured asset path, or None.

	Only site-relative paths and https URLs are accepted. A value that is neither
	is dropped rather than rendered: these end up in `src` attributes, and
	site_config is edited by hand.
	"""
	value = frappe.conf.get(key)
	if not isinstance(value, str):
		return None

	value = value.strip()
	if not value:
		return None

	if value.startswith("/") and not value.startswith("//"):
		return value
	if value.startswith("https://"):
		return value

	frappe.logger("berp_branding").warning(
		f"berp_branding: ignoring {key} — expected a site-relative path or an https URL, got {value!r}"
	)
	return None


def branding() -> dict:
	"""
	What this site should display: the bERP platform identity, with any tenant
	override laid over it.

	Resolution is PLATFORM_DEFAULTS <- site_config, which is the bottom two rungs
	of the BERP-WL-001 §4 chain (platform -> tenant -> company -> document). A key
	absent from site_config falls back to the platform default, never to ERPNext's.
	"""
	values = dict(PLATFORM_DEFAULTS)
	values["app_name"] = brand_name()
	for key, fieldname in BRAND_FIELDS.items():
		if fieldname == "app_name":
			continue
		asset = _brand_asset(key)
		if asset:
			values[fieldname] = asset
	return values


def shipped_assets() -> dict:
	"""
	Whether each platform default asset is actually on disk and served.

	Reports READY / MISSING / UNKNOWN and never collapses UNKNOWN into MISSING: a
	check that could not run has not found a defect. UNKNOWN here means the bench
	path could not be resolved, which is not the same as the file being absent.
	"""
	import os

	results = {}
	for fieldname, path in PLATFORM_DEFAULTS.items():
		if not path.startswith(ASSET_ROOT):
			continue
		try:
			site_path = frappe.get_site_path("..", "assets")
		except Exception:
			results[fieldname] = {"path": path, "status": "UNKNOWN"}
			continue
		relative = path[len("/assets/") :]
		results[fieldname] = {
			"path": path,
			"status": "READY" if os.path.exists(os.path.join(site_path, relative)) else "MISSING",
		}
	return results


# ─── Applying it ──────────────────────────────────────────────────────────────


@frappe.whitelist()
def apply_branding(force: int = 0) -> dict:
	"""
	Write the configured branding into Website Settings.

	This is what actually reaches the Desk navbar, the browser tab and the login
	page. It is idempotent and safe to re-run; `after_migrate` calls it so a
	site_config change takes effect on the next migrate.

	A value already set in Website Settings is left alone unless `force` is set,
	so an operator who set a logo by hand does not have it overwritten on every
	migrate. Nothing is ever blanked: a key absent from site_config means "leave
	this as it is", not "clear it".
	"""
	frappe.only_for("System Manager")

	settings = frappe.get_single("Website Settings")
	wanted = branding()
	changed = {}

	for fieldname, value in wanted.items():
		current = settings.get(fieldname)
		if current and not cint(force):
			continue
		if current == value:
			continue
		settings.set(fieldname, value)
		changed[fieldname] = value

	if changed:
		settings.flags.ignore_permissions = True
		settings.save()
		frappe.clear_cache()
		frappe.logger("berp_branding").info(f"berp_branding: applied branding {changed}")

	return {"applied": changed, "configured": wanted, "site": frappe.local.site}


def after_install():
	apply_branding(force=1)


def after_migrate():
	# Not forced: a migrate must not undo an operator's manual change.
	apply_branding()


# ─── Render-time context ──────────────────────────────────────────────────────


def update_website_context(context):
	"""Portal pages: navbar brand and application name."""
	label = brand_name()
	context["app_name"] = label
	context["brand_html"] = escape(label, quote=True)

	logo = _brand_asset("berp_brand_logo")
	if logo:
		context["app_logo"] = logo

	favicon = _brand_asset("berp_brand_favicon")
	if favicon:
		context["favicon"] = favicon


def boot_session(bootinfo):
	"""
	Expose the brand to Desk JavaScript.

	Frappe fills `bootinfo.app_logo_url` from Website Settings before this runs,
	so the logo is already correct once `apply_branding` has run. `berp_brand` is
	added for client code that wants the label without re-deriving it.
	"""
	bootinfo.berp_brand = {"name": brand_name(), "site": frappe.local.site}


# ─── Operator helper ──────────────────────────────────────────────────────────


@frappe.whitelist()
def branding_status() -> dict:
	"""
	Report what is configured, what is stored, and where the logo resolves from.

	Read-only. This is the call to run when a tenant says the branding looks wrong
	— it shows which of the three sources Frappe will actually use.
	"""
	frappe.only_for("System Manager")

	from frappe.core.doctype.navbar_settings.navbar_settings import get_app_logo

	settings = frappe.get_single("Website Settings")
	stored = {field: settings.get(field) for field in BRAND_FIELDS.values()}
	navbar_logo = frappe.db.get_single_value("Navbar Settings", "app_logo")

	if stored.get("app_logo"):
		source = "Website Settings"
	elif navbar_logo:
		source = "Navbar Settings"
	else:
		source = _("hooks app_logo_url (first app wins — usually Frappe's own logo)")

	return {
		"site": frappe.local.site,
		"configured": branding(),
		"stored_in_website_settings": stored,
		"navbar_settings_logo": navbar_logo,
		"resolved_logo": get_app_logo(),
		"resolved_from": source,
		"platform_defaults": PLATFORM_DEFAULTS,
		"shipped_assets": shipped_assets(),
	}
