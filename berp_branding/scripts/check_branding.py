#!/usr/bin/env python3
# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
check_branding.py — bench-free preflight for the bERP Branding app.

Why this exists
---------------
The app's real test suite needs a Frappe bench. That makes the cheapest and most
damaging class of defect — an app whose *identifiers* disagree with its *folders*,
so Frappe cannot import a single hook — invisible until someone runs `bench
install-app` on a site. berp_lao hit exactly that on 2026-09-14: the folder was
renamed, hooks.py was not, and nothing imported.

This harness answers one question without a bench:

    If Frappe loaded this app right now, would it work?

It does that by resolving every hook the way Frappe does, and by exercising the
branding logic against a stubbed `frappe` module. It is a preflight, not a
replacement for the bench suite: it cannot prove what Website Settings does on a
real site, only that this app is internally coherent and its pure logic is correct.

Usage
-----
    python3 scripts/check_branding.py
    python3 scripts/check_branding.py --app-root /path/to/app --assets /path/to/Brandkit/Logo
    python3 scripts/check_branding.py --quiet     # only failures

Exit code 0 = all required checks pass. 1 = at least one required check failed.
WARN never fails the run.
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
import types
from pathlib import Path

# This harness imports the app under test. Without this it would leave
# __pycache__ inside the working tree it is only supposed to inspect.
sys.dont_write_bytecode = True

# ─── Tiny result framework ────────────────────────────────────────────────────

PASS, FAIL, WARN, SKIP = "PASS", "FAIL", "WARN", "SKIP"

_RESULTS: list[tuple[str, str, str, str]] = []  # (status, id, title, detail)


def record(status: str, check_id: str, title: str, detail: str = "") -> None:
	_RESULTS.append((status, check_id, title, detail))


def check(check_id: str, title: str, condition: bool, detail_fail: str, detail_pass: str = "") -> bool:
	record(PASS if condition else FAIL, check_id, title, detail_pass if condition else detail_fail)
	return condition


def warn_if(check_id: str, title: str, condition: bool, detail: str, detail_ok: str = "") -> None:
	record(WARN if condition else PASS, check_id, title, detail if condition else detail_ok)


# ─── Minimal TOML reading ─────────────────────────────────────────────────────
# Python 3.10 has no tomllib and this harness takes no dependencies. Only three
# scalar keys are needed, each unambiguous in this file, so targeted regex is
# honest here in a way it would not be for arbitrary TOML.


def toml_scalar(text: str, section: str, key: str) -> str | None:
	"""Read `key = "value"` from within [section]."""
	pattern = re.compile(
		r"^\[" + re.escape(section) + r"\]\s*$(.*?)(?=^\[|\Z)",
		re.MULTILINE | re.DOTALL,
	)
	match = pattern.search(text)
	if not match:
		return None
	body = match.group(1)
	key_match = re.search(rf'^\s*{re.escape(key)}\s*=\s*"([^"]*)"', body, re.MULTILINE)
	return key_match.group(1) if key_match else None


def module_dir_name(module_label: str) -> str:
	"""Frappe's module-label -> folder convention: 'Lao Regional' -> 'lao_regional'."""
	return module_label.strip().lower().replace(" ", "_").replace("-", "_")


# ─── A. Manifest integrity ────────────────────────────────────────────────────


def load_hooks(hooks_path: Path) -> dict:
	"""
	Execute hooks.py in an empty namespace.

	Frappe's hooks.py is by contract a module of plain assignments with no imports,
	so exec is safe here and is more faithful than parsing: it sees exactly what
	Frappe would see.
	"""
	namespace: dict = {}
	exec(compile(hooks_path.read_text(encoding="utf-8"), str(hooks_path), "exec"), namespace)
	return {k: v for k, v in namespace.items() if not k.startswith("__")}


def find_package_dir(app_root: Path) -> Path | None:
	"""The single inner directory holding hooks.py."""
	for child in sorted(app_root.iterdir()):
		if child.is_dir() and (child / "hooks.py").is_file():
			return child
	return None


def check_manifest(app_root: Path) -> tuple[str | None, Path | None, dict]:
	package_dir = find_package_dir(app_root)
	if not check(
		"A0",
		"An app package directory containing hooks.py exists",
		package_dir is not None,
		f"no directory under {app_root} contains hooks.py",
		f"{package_dir.name}/" if package_dir else "",
	):
		return None, None, {}

	package = package_dir.name
	hooks = load_hooks(package_dir / "hooks.py")

	pyproject = app_root / "pyproject.toml"
	if pyproject.is_file():
		text = pyproject.read_text(encoding="utf-8")
		project_name = toml_scalar(text, "project", "name")
		flit_name = toml_scalar(text, "tool.flit.module", "name")
		homepage = re.search(r'Homepage\s*=\s*"([^"]*)"', text)

		check(
			"A1",
			"pyproject [project].name matches the package directory",
			project_name == package,
			f'pyproject says "{project_name}", directory is "{package}/"',
			f'"{package}"',
		)
		check(
			"A2",
			"pyproject [tool.flit.module].name matches the package directory",
			flit_name == package,
			f'flit module is "{flit_name}", directory is "{package}/"',
			f'"{package}"',
		)
		if homepage:
			slug = homepage.group(1).rstrip("/").rsplit("/", 1)[-1]
			warn_if(
				"A6",
				"pyproject Homepage points at a repo named after the app",
				slug.lower().replace("-", "_") != package,
				f'Homepage repo is "{slug}", app is "{package}"',
				f'"{slug}"',
			)
	else:
		record(FAIL, "A1", "pyproject.toml exists", f"not found at {pyproject}")

	app_name = hooks.get("app_name")
	check(
		"A3",
		"hooks.app_name matches the package directory",
		app_name == package,
		f'hooks.py says app_name = "{app_name}", directory is "{package}/"  '
		f"— Frappe resolves every hook under this name, so a mismatch means no hook imports",
		f'"{package}"',
	)

	modules_txt = package_dir / "modules.txt"
	if modules_txt.is_file():
		labels = [ln.strip() for ln in modules_txt.read_text(encoding="utf-8").splitlines() if ln.strip()]
		check(
			"A4",
			"Every module in modules.txt has a matching package folder",
			all((package_dir / module_dir_name(label)).is_dir() for label in labels),
			"; ".join(
				f'module "{label}" expects {package}/{module_dir_name(label)}/ — not found'
				for label in labels
				if not (package_dir / module_dir_name(label)).is_dir()
			),
			", ".join(f'"{label}" -> {module_dir_name(label)}/' for label in labels),
		)
	else:
		record(FAIL, "A4", "modules.txt exists", f"not found at {modules_txt}")

	title = str(hooks.get("app_title", ""))
	warn_if(
		"A7",
		"app_title carries no superseded product name",
		"whitelabel" in title.lower().replace(" ", ""),
		f'app_title = "{title}"',
		f'"{title}"',
	)

	return package, package_dir, hooks


def check_module_shadowing(package_dir: Path) -> None:
	"""
	A Frappe module folder must not share its name with a .py file beside it.

	This is a live trap for this app specifically: the logic lives in branding.py,
	so renaming the module to "Branding" would create branding/ next to branding.py.
	Python resolves the package and the module file becomes unreachable — every hook
	path silently targets an empty __init__.py. It imports cleanly and does nothing.
	"""
	collisions = [
		child.name
		for child in package_dir.iterdir()
		if child.is_dir()
		and (child / "__init__.py").is_file()
		and (package_dir / f"{child.name}.py").is_file()
	]
	check(
		"A5",
		"No module folder shadows a module file of the same name",
		not collisions,
		"; ".join(
			f"{package_dir.name}/{name}/ shadows {package_dir.name}/{name}.py — "
			f"the package wins and {name}.py becomes unreachable"
			for name in collisions
		),
		"no shadowing",
	)


# ─── B. Hook resolution, the way Frappe does it ───────────────────────────────

HOOK_KEYS_WITH_DOTTED_PATHS = (
	"after_install",
	"after_migrate",
	"before_install",
	"boot_session",
	"update_website_context",
	"on_session_creation",
)


def dotted_paths(hooks: dict) -> list[tuple[str, str]]:
	found = []
	for key in HOOK_KEYS_WITH_DOTTED_PATHS:
		value = hooks.get(key)
		if isinstance(value, str) and "." in value:
			found.append((key, value))
		elif isinstance(value, list):
			found.extend((key, v) for v in value if isinstance(v, str) and "." in v)
	return found


def check_hook_resolution(app_root: Path, package: str, hooks: dict) -> None:
	"""
	Resolve each hook target the way frappe.get_attr does: import the module part,
	getattr the last segment. This is the check that catches a half-finished rename.
	"""
	paths = dotted_paths(hooks)
	if not paths:
		record(SKIP, "B0", "Hook targets declared", "no dotted hook paths in hooks.py")
		return

	# The stub must be in place before any import is attempted. Without it every
	# hook fails with "No module named 'frappe'" — an environment fact reported as
	# a product defect, which is precisely the reading error this check exists to
	# prevent. Validated: on a correct tree B goes green only once the stub is here.
	install_frappe_stub()
	sys.path.insert(0, str(app_root))
	try:
		for key, path in paths:
			root = path.split(".", 1)[0]
			if root != package:
				record(
					FAIL,
					f"B:{key}",
					f"Hook {key} resolves",
					f'"{path}" is rooted at "{root}" but the importable package is "{package}"'
					f" — ModuleNotFoundError at boot",
				)
				continue
			module_path, _, attribute = path.rpartition(".")
			try:
				module = importlib.import_module(module_path)
			except Exception as exc:
				record(FAIL, f"B:{key}", f"Hook {key} resolves", f'importing "{module_path}" raised {exc!r}')
				continue
			if not hasattr(module, attribute):
				record(
					FAIL,
					f"B:{key}",
					f"Hook {key} resolves",
					f'"{module_path}" has no attribute "{attribute}"',
				)
				continue
			record(PASS, f"B:{key}", f"Hook {key} resolves", path)
	finally:
		sys.path.remove(str(app_root))
		for name in [
			m for m in sys.modules if m == "frappe" or m.startswith("frappe.") or m.startswith(package)
		]:
			sys.modules.pop(name, None)


def check_no_app_logo_url(hooks: dict) -> None:
	"""
	ADR: this app declares no app_logo_url, deliberately. Frappe's get_app_logo takes
	hooks[0] unless exactly two apps declare it, when it takes hooks[1] — so on a
	frappe + this-app site the hook would win and serve whatever it names. Website
	Settings is written instead. Regression guard.
	"""
	check(
		"B9",
		"hooks declares no app_logo_url",
		"app_logo_url" not in hooks,
		f"app_logo_url = {hooks.get('app_logo_url')!r} — see the ADR note in hooks.py; "
		f"on a two-app site this wins and must therefore point at a shipped asset",
		"absent, as designed",
	)


# ─── C. Branding logic, against a stubbed frappe ──────────────────────────────


class _Doc:
	"""Stands in for a Single doc (Website Settings)."""

	def __init__(self, **fields):
		self._fields = dict(fields)
		self.flags = types.SimpleNamespace(ignore_permissions=False)
		self.saved = 0

	def get(self, field):
		return self._fields.get(field)

	def set(self, field, value):
		self._fields[field] = value

	def save(self):
		self.saved += 1


class _Logger:
	def __init__(self):
		self.messages: list[tuple[str, str]] = []

	def warning(self, message):
		self.messages.append(("warning", str(message)))

	def info(self, message):
		self.messages.append(("info", str(message)))


def install_frappe_stub() -> types.ModuleType:
	"""
	Put a minimal `frappe` into sys.modules so branding.py imports without a bench.

	The stub deliberately implements only what branding.py touches. It is a test
	double for pure-logic checks, NOT a claim about Frappe's real behaviour —
	anything that depends on what a real site does with Website Settings stays the
	bench suite's job.
	"""
	frappe = types.ModuleType("frappe")
	frappe.conf = {}
	frappe.local = types.SimpleNamespace(site="test.localhost")
	frappe.flags = types.SimpleNamespace()
	frappe._logger = _Logger()
	frappe._single = _Doc()
	frappe.cleared = 0

	frappe._ = lambda s, *a, **k: s
	frappe.whitelist = lambda *a, **k: lambda fn: fn
	frappe.only_for = lambda *a, **k: None
	frappe.logger = lambda *a, **k: frappe._logger
	frappe.get_single = lambda doctype: frappe._single

	def _clear_cache(*a, **k):
		frappe.cleared += 1

	frappe.clear_cache = _clear_cache
	frappe.db = types.SimpleNamespace(get_single_value=lambda doctype, field: None)

	utils = types.ModuleType("frappe.utils")

	def cint(value):
		try:
			return int(value)
		except (TypeError, ValueError):
			return 0

	utils.cint = cint
	frappe.utils = utils

	navbar = types.ModuleType("frappe.core.doctype.navbar_settings.navbar_settings")
	navbar.get_app_logo = lambda: (
		frappe._single.get("app_logo") or "/assets/frappe/images/frappe-framework-logo.svg"
	)

	for name, module in {
		"frappe": frappe,
		"frappe.utils": utils,
		"frappe.core": types.ModuleType("frappe.core"),
		"frappe.core.doctype": types.ModuleType("frappe.core.doctype"),
		"frappe.core.doctype.navbar_settings": types.ModuleType("frappe.core.doctype.navbar_settings"),
		"frappe.core.doctype.navbar_settings.navbar_settings": navbar,
	}.items():
		sys.modules[name] = module

	return frappe


REJECTED_ASSETS = [
	("http://cdn.example.la/logo.svg", "plain http"),
	("//cdn.example.la/logo.svg", "protocol-relative"),
	("data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=", "data URI"),
	("javascript:alert(1)", "javascript URI"),
	("logo.svg", "bare filename"),
	("  ", "whitespace"),
	(42, "non-string"),
]


def logic_module_path(hooks: dict, package: str) -> str | None:
	"""
	Where the branding logic actually lives, according to hooks.py.

	Never assume it is `<package>.branding`: this app's module folder and its logic
	file have collided under that name before. hooks.py is the only honest source —
	it is what Frappe itself reads.
	"""
	for _key, path in dotted_paths(hooks):
		module_path, _, _attr = path.rpartition(".")
		if module_path.split(".", 1)[0] == package:
			return module_path
	return None


def check_branding_logic(app_root: Path, package: str, hooks: dict) -> None:
	module_path = logic_module_path(hooks, package)
	if not module_path:
		record(SKIP, "C0", "branding module imports", "no resolvable hook path to locate the logic module")
		return

	frappe = install_frappe_stub()
	sys.path.insert(0, str(app_root))
	try:
		try:
			branding = importlib.import_module(module_path)
		except Exception as exc:
			record(FAIL, "C0", "branding module imports", f"importing {module_path}: {exc!r}")
			return
		missing = [
			name
			for name in (
				"DEFAULT_BRAND",
				"MAX_BRAND_LENGTH",
				"brand_name",
				"_brand_asset",
				"apply_branding",
				"update_website_context",
				"boot_session",
			)
			if not hasattr(branding, name)
		]
		if missing:
			record(
				FAIL,
				"C0",
				"branding module imports",
				f"{module_path} imported but is missing: {', '.join(missing)} "
				f"— hooks point at a module that does not carry the branding logic",
			)
			return
		record(PASS, "C0", "branding module imports", module_path)

		check(
			"C1",
			"DEFAULT_BRAND is the platform name",
			branding.DEFAULT_BRAND == "bERP",
			f'DEFAULT_BRAND = "{branding.DEFAULT_BRAND}", expected "bERP"',
			'"bERP"',
		)

		# brand_name fallbacks
		bad_names = []
		for value in (None, "", "   ", "\t\n", 42, [], {}):
			frappe.conf = {} if value is None else {"berp_brand_name": value}
			if branding.brand_name() != branding.DEFAULT_BRAND:
				bad_names.append(repr(value))
		check(
			"C2",
			"brand_name falls back for unset, blank and non-string values",
			not bad_names,
			f"did not fall back for: {', '.join(bad_names)}",
			"7 inputs fall back to DEFAULT_BRAND",
		)

		frappe.conf = {"berp_brand_name": "  LaoCap ERP  "}
		check(
			"C3",
			"brand_name is trimmed",
			branding.brand_name() == "LaoCap ERP",
			f'got "{branding.brand_name()}"',
			'"LaoCap ERP"',
		)

		frappe.conf = {"berp_brand_name": "x" * 500}
		check(
			"C4",
			"brand_name is capped at MAX_BRAND_LENGTH",
			len(branding.brand_name()) == branding.MAX_BRAND_LENGTH,
			f"got {len(branding.brand_name())} chars, cap is {branding.MAX_BRAND_LENGTH}",
			f"{branding.MAX_BRAND_LENGTH} chars",
		)

		# asset validation — the security-relevant part
		frappe.conf = {"berp_brand_logo": "/files/laocap-logo.svg"}
		check(
			"C5",
			"A site-relative asset path is accepted",
			branding._brand_asset("berp_brand_logo") == "/files/laocap-logo.svg",
			f"got {branding._brand_asset('berp_brand_logo')!r}",
			"/files/laocap-logo.svg",
		)

		frappe.conf = {"berp_brand_logo": "https://cdn.bizera.la/logo.svg"}
		check(
			"C6",
			"An https asset URL is accepted",
			branding._brand_asset("berp_brand_logo") == "https://cdn.bizera.la/logo.svg",
			f"got {branding._brand_asset('berp_brand_logo')!r}",
			"https://cdn.bizera.la/logo.svg",
		)

		leaked = []
		for value, label in REJECTED_ASSETS:
			frappe.conf = {"berp_brand_logo": value}
			if branding._brand_asset("berp_brand_logo") is not None:
				leaked.append(label)
		check(
			"C7",
			"Hostile and malformed asset values are dropped, not rendered",
			not leaked,
			f"these reached the template: {', '.join(leaked)}",
			f"{len(REJECTED_ASSETS)} hostile inputs dropped (incl. javascript:, data:, protocol-relative)",
		)

		# apply_branding semantics
		frappe.conf = {"berp_brand_name": "LaoCap ERP", "berp_brand_logo": "/files/l.svg"}
		frappe._single = _Doc()
		result = branding.apply_branding()
		check(
			"C8",
			"apply_branding writes into an empty Website Settings",
			frappe._single.get("app_name") == "LaoCap ERP"
			and frappe._single.get("app_logo") == "/files/l.svg",
			f"stored {frappe._single._fields}",
			f"applied {sorted(result['applied'])}",
		)

		frappe._single = _Doc(app_name="Set By Operator")
		branding.apply_branding()
		check(
			"C9",
			"apply_branding does not overwrite an operator's value without force",
			frappe._single.get("app_name") == "Set By Operator",
			f'operator value became "{frappe._single.get("app_name")}"',
			'"Set By Operator" preserved',
		)

		frappe._single = _Doc(app_name="Set By Operator")
		branding.apply_branding(force=1)
		check(
			"C10",
			"apply_branding with force=1 overwrites",
			frappe._single.get("app_name") == "LaoCap ERP",
			f'got "{frappe._single.get("app_name")}"',
			'"LaoCap ERP"',
		)

		frappe.conf = {}  # every key removed from site_config
		frappe._single = _Doc(app_name="LaoCap ERP", app_logo="/files/l.svg", favicon="/files/f.png")
		branding.apply_branding()
		check(
			"C11",
			"Removing a site_config key never blanks the stored value",
			frappe._single.get("app_logo") == "/files/l.svg"
			and frappe._single.get("favicon") == "/files/f.png",
			f"stored became {frappe._single._fields}",
			"logo and favicon untouched",
		)

		# force + platform default. The bench suite caught this interaction when the
		# preflight did not: C11 only ever exercised the force=0 path.
		if hasattr(branding, "PLATFORM_DEFAULTS"):
			frappe.conf = {}
			frappe._single = _Doc(app_logo="/files/operator.svg")
			branding.apply_branding(force=1)
			check(
				"C16",
				"force=1 asserts the platform default over an unconfigured field",
				frappe._single.get("app_logo") == branding.PLATFORM_DEFAULTS["app_logo"],
				f"got {frappe._single.get('app_logo')!r}",
				branding.PLATFORM_DEFAULTS["app_logo"],
			)
			frappe._single = _Doc(app_logo="/files/operator.svg")
			branding.apply_branding()
			check(
				"C17",
				"Without force, an operator value survives the platform default",
				frappe._single.get("app_logo") == "/files/operator.svg",
				f"operator value became {frappe._single.get('app_logo')!r}",
				"preserved",
			)

		# render-time escaping
		frappe.conf = {"berp_brand_name": '<script>alert("xss")</script>'}
		context = {}
		branding.update_website_context(context)
		brand_html = context.get("brand_html", "")
		check(
			"C12",
			"The brand label is HTML-escaped before reaching the portal navbar",
			"<script>" not in brand_html and "&lt;script&gt;" in brand_html,
			f"brand_html = {brand_html!r}",
			"escaped",
		)

		# Platform default layer — the reason this app exists
		if hasattr(branding, "PLATFORM_DEFAULTS"):
			frappe.conf = {}
			resolved = branding.branding()
			check(
				"C14",
				"An unconfigured site resolves to the bERP platform identity",
				resolved.get("app_name") == "bERP" and resolved.get("app_logo", "").startswith("/assets/"),
				f"unconfigured site resolved to {resolved} — it would keep ERPNext's identity",
				f'app_name "bERP", app_logo {resolved.get("app_logo")}',
			)
			frappe.conf = {"berp_brand_name": "LaoCap ERP", "berp_brand_logo": "/files/laocap.svg"}
			resolved = branding.branding()
			check(
				"C15",
				"A tenant override beats the platform default",
				resolved.get("app_name") == "LaoCap ERP" and resolved.get("app_logo") == "/files/laocap.svg",
				f"tenant override did not win: {resolved}",
				"tenant values win, platform favicon still inherited",
			)
		else:
			record(
				SKIP,
				"C14",
				"An unconfigured site resolves to the bERP platform identity",
				"module declares no PLATFORM_DEFAULTS",
			)

		frappe.conf = {"berp_brand_name": "LaoCap ERP"}
		boot = types.SimpleNamespace()
		branding.boot_session(boot)
		check(
			"C13",
			"boot_session exposes the brand to Desk JavaScript",
			getattr(boot, "berp_brand", {}).get("name") == "LaoCap ERP",
			f"boot.berp_brand = {getattr(boot, 'berp_brand', None)!r}",
			"frappe.boot.berp_brand.name",
		)

	except Exception as exc:
		record(FAIL, "C99", "Branding logic checks ran to completion", f"{type(exc).__name__}: {exc}")
	finally:
		sys.path.remove(str(app_root))
		for name in [
			m for m in sys.modules if m == "frappe" or m.startswith("frappe.") or m.startswith(package)
		]:
			sys.modules.pop(name, None)


# ─── D. Brand asset contract (BERP-WL-001 §17–19) ─────────────────────────────

REQUIRED_ASSETS = ("logo.primary", "logo.compact", "logo.inverse", "favicon", "app-icon")

#: Which source file, if any, satisfies each required asset.
ASSET_SOURCES = {
	"logo.primary": ("bERP_Logo_hText.svg",),
	"logo.compact": ("bERP_Logo_Icon.svg",),
	"logo.inverse": ("bERP_Logo_Inverse.svg", "bERP_Logo_hText_Inverse.svg"),
	"favicon": ("favicon.ico", "favicon.svg", "favicon.png"),
	"app-icon": ("app-icon.png", "bERP_Logo_Icon_512.png"),
}

UNSAFE_SVG = (
	(r"<script", "embedded <script>"),
	(r"<foreignObject", "<foreignObject>"),
	(r"\son\w+\s*=", "inline event handler"),
	(r'(?:xlink:)?href\s*=\s*"\s*https?://', "external resource reference"),
	(r"<!ENTITY", "XML entity declaration"),
)


def check_assets(assets_root: Path | None, app_root: Path, package: str | None) -> None:
	# D0 — what the app itself ships
	public = (app_root / package / "public") if package else None
	ships = public.is_dir() and any(public.rglob("*")) if public else False
	record(
		PASS if ships else WARN,
		"D0",
		"The app ships a default brand asset set",
		f"{package}/public/ present"
		if ships
		else f"no {package}/public/ — a fresh install therefore shows ERPNext's identity, not bERP's",
	)

	if assets_root is None or not assets_root.is_dir():
		record(SKIP, "D1", "Brand asset source available", "pass --assets to check the brand kit")
		return

	svgs = sorted(assets_root.rglob("*.svg"))
	record(PASS, "D1", "Brand asset source available", f"{len(svgs)} SVG under {assets_root.name}/")

	# D2 — required set per WL-001 §17
	present = {p.name for p in assets_root.rglob("*")}
	missing = [
		asset
		for asset in REQUIRED_ASSETS
		if not any(candidate in present for candidate in ASSET_SOURCES.get(asset, ()))
	]
	check(
		"D2",
		"The WL-001 §17 required asset set is complete",
		not missing,
		f"missing: {', '.join(missing)}",
		"all five present",
	)

	# D3 — SVG safety
	unsafe = []
	for svg in svgs:
		text = svg.read_text(encoding="utf-8", errors="replace")
		for pattern, label in UNSAFE_SVG:
			if re.search(pattern, text, re.IGNORECASE):
				unsafe.append(f"{svg.name}: {label}")
	check(
		"D3",
		"No SVG carries script, external references or entities",
		not unsafe,
		"; ".join(unsafe),
		f"{len(svgs)} SVG clean",
	)

	# D4 — live text. A logo with a live <text> element renders in whatever face
	# the host resolves. Same failure shape as the Lao font incident: it does not
	# break, it renders wrong on output that still looks finished.
	with_text = []
	for svg in svgs:
		text = svg.read_text(encoding="utf-8", errors="replace")
		if re.search(r"<text[\s>]", text):
			families = set(re.findall(r"font-family:\s*([^;}\n]+)", text))
			with_text.append(f"{svg.name} (font-family: {', '.join(sorted(families)) or 'unspecified'})")
	check(
		"D4",
		"Logo artwork contains no live text",
		not with_text,
		"; ".join(with_text) + " — outline the text, or the wordmark renders in a fallback face "
		"anywhere the named font is not resolvable (wkhtmltopdf, most servers)",
		f"{len(svgs)} SVG fully outlined",
	)

	# D5 — id / class collision. Safe as <img src>; breaks when two are inlined.
	generic = []
	for svg in svgs:
		text = svg.read_text(encoding="utf-8", errors="replace")
		ids = set(re.findall(r'id="([^"]+)"', text))
		classes = set(re.findall(r"\.(cls-\d+)\s*\{", text))
		risky = {i for i in ids if re.fullmatch(r"(linear-gradient(-\d+)?|Layer_\d+(-\d+)?)", i)}
		if risky or classes:
			generic.append(f"{svg.name}: {len(risky)} generic id, {len(classes)} .cls-N class")
	record(
		WARN if generic else PASS,
		"D5",
		"SVG ids and classes are namespaced",
		"; ".join(generic) + " — safe as <img src>, collides if two are inlined on one page"
		if generic
		else f"{len(svgs)} SVG namespaced",
	)


def check_declared_assets(app_root: Path, package: str, hooks: dict) -> None:
	"""
	Every /assets/<app>/ path the app declares must exist under public/.

	A default that points at a missing file is worse than shipping no default: a
	broken image becomes the platform identity, on precisely the fresh install a
	new tenant sees first (BERP-WL-001 §45).
	"""
	module_path = logic_module_path(hooks, package)
	if not module_path:
		record(SKIP, "D6", "Declared /assets/ paths exist on disk", "logic module not resolvable")
		return

	install_frappe_stub()
	sys.path.insert(0, str(app_root))
	try:
		module = importlib.import_module(module_path)
		declared = getattr(module, "PLATFORM_DEFAULTS", {})
		prefix = f"/assets/{package}/"
		paths = [v for v in declared.values() if isinstance(v, str) and v.startswith(prefix)]
		if not paths:
			record(SKIP, "D6", "Declared /assets/ paths exist on disk", "no /assets/ paths declared")
			return
		missing = [
			path for path in paths if not (app_root / package / "public" / path[len(prefix) :]).is_file()
		]
		check(
			"D6",
			"Declared /assets/ paths exist on disk",
			not missing,
			"; ".join(f"{p} -> {package}/public/{p[len(prefix) :]} not found" for p in missing),
			f"{len(paths)} declared asset(s) present",
		)
	except Exception as exc:
		record(FAIL, "D6", "Declared /assets/ paths exist on disk", f"{type(exc).__name__}: {exc}")
	finally:
		sys.path.remove(str(app_root))
		for name in [
			m for m in sys.modules if m == "frappe" or m.startswith("frappe.") or m.startswith(package)
		]:
			sys.modules.pop(name, None)


# ─── Reporting ────────────────────────────────────────────────────────────────

GLYPH = {PASS: "PASS", FAIL: "FAIL", WARN: "WARN", SKIP: "SKIP"}


def report(quiet: bool) -> int:
	width = max((len(t) for _, _, t, _ in _RESULTS), default=0)
	section = None
	for status, check_id, title, detail in _RESULTS:
		if quiet and status in (PASS, SKIP):
			continue
		letter = check_id[0]
		if letter != section:
			section = letter
			print()
		print(f"  [{GLYPH[status]}] {check_id:<10} {title:<{width}}  {detail}")

	counts = {s: sum(1 for r in _RESULTS if r[0] == s) for s in (PASS, FAIL, WARN, SKIP)}
	print()
	print("  " + "-" * (width + 24))
	print(f"  {counts[PASS]} passed · {counts[FAIL]} failed · {counts[WARN]} warned · {counts[SKIP]} skipped")
	return 1 if counts[FAIL] else 0


def main() -> int:
	parser = argparse.ArgumentParser(
		description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
	)
	parser.add_argument(
		"--app-root",
		type=Path,
		default=Path(__file__).resolve().parent.parent,
		help="app repository root (default: parent of scripts/)",
	)
	parser.add_argument("--assets", type=Path, default=None, help="brand kit Logo directory")
	parser.add_argument("--quiet", action="store_true", help="print only failures and warnings")
	args = parser.parse_args()

	app_root = args.app_root.resolve()
	print(f"\n  bERP Branding preflight — {app_root}")

	package, package_dir, hooks = check_manifest(app_root)
	if package and package_dir:
		check_module_shadowing(package_dir)
		check_no_app_logo_url(hooks)
		check_hook_resolution(app_root, package, hooks)
		check_branding_logic(app_root, package, hooks)
	check_assets(args.assets.resolve() if args.assets else None, app_root, package)
	if package and package_dir:
		check_declared_assets(app_root, package, hooks)

	return report(args.quiet)


if __name__ == "__main__":
	sys.exit(main())
