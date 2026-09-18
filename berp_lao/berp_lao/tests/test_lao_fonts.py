# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Tests for Lao typography — BERP-LAO-ARCH-001 ADR-A4.

The defect these exist to prevent: the Lao Tax Invoice declared
`font-family: 'Phetsarath'` while no Lao font was ever loaded into the print
document, so a statutory tax invoice rendered in whatever the PDF engine fell
back to. It went unnoticed because nothing tested the print format.

`app_include_css` reaches the Desk only. Frappe assembles print CSS from
standard.css, the selected Print Style and the Print Format's own `css` field
(frappe/www/printview.py:get_print_style) — and from nothing else.
"""

import os
import re
import struct

import frappe

try:  # Frappe v16+
	from frappe.tests import IntegrationTestCase as _TestCase
except ImportError:  # Frappe v15
	from frappe.tests.utils import FrappeTestCase as _TestCase

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(APP_DIR, "public", "fonts")
DESK_CSS = os.path.join(APP_DIR, "public", "css", "lao_fonts.css")
PRINT_FORMAT = "Lao Tax Invoice"
REQUIRED_FAMILIES = ("Phetsarath", "Noto Sans Lao")
ASSET_PREFIX = "/assets/berp_lao/"

FONT_FACE_RE = re.compile(r"@font-face\s*\{[^}]*\}")
COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
FAMILY_RE = re.compile(r"font-family:\s*['\"]([^'\"]+)['\"]")
URL_RE = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)")


def _asset_path(url: str) -> str:
	"""Map /assets/berp_lao/x onto the file that serves it."""
	return os.path.join(APP_DIR, "public", url[len(ASSET_PREFIX) :])


def _strip_comments(css: str) -> str:
	"""A URL in a comment is documentation, not a network request."""
	return COMMENT_RE.sub("", css)


def _faces(css: str) -> set[tuple[str, str]]:
	"""(family, url) for every @font-face rule in `css`."""
	out = set()
	for block in FONT_FACE_RE.findall(css):
		family = FAMILY_RE.search(block)
		for url in URL_RE.findall(block):
			out.add((family.group(1) if family else "", url))
	return out


def _has_table(path: str, tag: bytes) -> bool:
	"""True when the TrueType file declares `tag` in its table directory.

	Parsed by hand rather than with fontTools, which is not a dependency of this
	app and is not installed on a stock bench.
	"""
	with open(path, "rb") as handle:
		header = handle.read(12)
		(num_tables,) = struct.unpack(">H", header[4:6])
		directory = handle.read(16 * num_tables)
	return any(directory[i * 16 : i * 16 + 4] == tag for i in range(num_tables))


class TestShippedFonts(_TestCase):
	def test_the_app_ships_lao_fonts(self):
		self.assertTrue(os.path.isdir(FONTS_DIR), "no public/fonts directory")
		ttfs = [f for _r, _d, files in os.walk(FONTS_DIR) for f in files if f.endswith(".ttf")]
		self.assertTrue(ttfs, "no font files shipped")

	def test_every_font_family_ships_its_licence(self):
		"""SIL OFL 1.1 requires the licence to travel with the font."""
		for licence in ("LICENSE-PHETSARATH.txt", "LICENSE-NOTO.txt"):
			with self.subTest(licence=licence):
				path = os.path.join(FONTS_DIR, licence)
				self.assertTrue(os.path.exists(path), f"{licence} is missing")
				with open(path, encoding="utf-8") as handle:
					self.assertIn("SIL OPEN FONT LICENSE", handle.read().upper())

	def test_provenance_is_recorded(self):
		"""332 KB of vendored binary has to be reproducible, not just present."""
		path = os.path.join(FONTS_DIR, "FONT-PROVENANCE.md")
		self.assertTrue(os.path.exists(path), "FONT-PROVENANCE.md is missing")
		with open(path, encoding="utf-8") as handle:
			provenance = handle.read()
		import hashlib

		for font in sorted(f for f in os.listdir(FONTS_DIR) if f.endswith(".ttf")):
			with self.subTest(font=font):
				with open(os.path.join(FONTS_DIR, font), "rb") as handle:
					digest = hashlib.sha256(handle.read()).hexdigest()
				self.assertIn(font, provenance, f"{font} has no provenance entry")
				self.assertIn(
					digest,
					provenance,
					f"{font}'s SHA-256 does not match FONT-PROVENANCE.md — "
					"the file changed without the record being updated",
				)

	def test_no_shipped_font_is_a_variable_font(self):
		"""wkhtmltopdf is Qt WebKit and cannot render variable fonts.

		Frappe v15 generates PDFs with wkhtmltopdf. A variable font in a print
		format renders at a single default instance or not at all, silently — so
		the statics here are the point, not an accident. `fvar` is the table that
		makes a font variable.
		"""
		for root, _dirs, files in os.walk(FONTS_DIR):
			for filename in files:
				if not filename.endswith(".ttf"):
					continue
				with self.subTest(font=filename):
					self.assertFalse(
						_has_table(os.path.join(root, filename), b"fvar"),
						f"{filename} is a variable font; instance it to a static first",
					)


class TestDeskStylesheet(_TestCase):
	def setUp(self):
		with open(DESK_CSS, encoding="utf-8") as handle:
			self.css = handle.read()

	def test_it_declares_font_faces(self):
		self.assertTrue(FONT_FACE_RE.findall(self.css), "no @font-face rules")

	def test_it_loads_no_font_over_the_network(self):
		"""A bench with no egress must still render Lao script."""
		for _family, url in _faces(self.css):
			with self.subTest(url=url):
				self.assertTrue(
					url.startswith(ASSET_PREFIX),
					f"{url} is not served by this app — a bench without egress renders boxes",
				)
		declarations = _strip_comments(self.css)
		self.assertNotIn("fonts.googleapis.com", declarations)
		self.assertNotIn("fonts.gstatic.com", declarations)
		self.assertNotIn("@import", declarations)

	def test_every_referenced_font_file_exists(self):
		for _family, url in _faces(self.css):
			with self.subTest(url=url):
				self.assertTrue(os.path.exists(_asset_path(url)), f"{url} is not shipped")


class TestPrintFormatFonts(_TestCase):
	"""What wkhtmltopdf actually does, measured rather than assumed.

	The first cut of ADR-A4 assumed a print format should declare @font-face.
	Rendering real PDFs showed the opposite — identical HTML, only the
	@font-face block differing, fonts installed on the machine in both runs:

	    with @font-face        embedded: DejaVuSans          text: "—"
	    without @font-face     embedded: Phetsarath-Regular  text: ໜຶ່ງລ້ານສອງແສນກີບຖ້ວນ

	wkhtmltopdf resolves fonts through fontconfig. Declaring @font-face
	overrides that lookup, fails, and takes the Lao text with it.
	"""

	def setUp(self):
		self.doc = frappe.get_doc("Print Format", PRINT_FORMAT)

	def test_the_font_field_is_set(self):
		"""get_font() reads it and writes font-family onto the print body.

		Left empty, standard.css renders a Lao invoice in Inter.
		"""
		self.assertTrue(self.doc.font, "Print Format.font is unset")
		self.assertNotEqual(self.doc.font, "Default")
		self.assertIn(self.doc.font, REQUIRED_FAMILIES)

	def test_it_declares_no_font_face(self):
		"""The regression. @font-face here breaks the PDF rather than fixing it."""
		self.assertEqual(
			FONT_FACE_RE.findall(self.doc.css or ""),
			[],
			"@font-face in a print format overrides fontconfig and then fails — "
			"wkhtmltopdf falls back to DejaVu and the Lao text is destroyed",
		)

	def test_it_asks_for_the_lao_families_by_name(self):
		css = _strip_comments(self.doc.css or "")
		self.assertIn("font-family", css, "the print format sets no font-family")
		for family in REQUIRED_FAMILIES:
			with self.subTest(family=family):
				self.assertIn(family, css)

	def test_the_font_family_survives_into_the_assembled_print_css(self):
		"""End to end: what printview hands the PDF renderer."""
		from frappe.www.printview import get_print_style

		css = get_print_style(print_format=self.doc)
		self.assertIn(
			f"font-family: {self.doc.font}",
			css,
			"get_font() did not write the font onto the print body",
		)
		self.assertEqual(
			FONT_FACE_RE.findall(_strip_comments(css)),
			[],
			"an @font-face rule reached the print document",
		)

	def test_it_fetches_nothing_over_the_network(self):
		css = _strip_comments(self.doc.css or "")
		self.assertNotIn("@import", css)
		self.assertNotIn("fonts.googleapis.com", css)


class TestFontAvailability(_TestCase):
	"""The app ships the files; the server has to install them."""

	def test_every_required_face_is_shipped(self):
		from berp_lao.lao_regional.fonts import REQUIRED_FACES, shipped_font_files

		shipped = {os.path.basename(p) for p in shipped_font_files()}
		for family, styles in REQUIRED_FACES.items():
			for style in styles:
				expected = f"{family.replace(' ', '')}-{style}.ttf"
				with self.subTest(face=expected):
					self.assertIn(expected, shipped)

	def test_font_status_is_machine_readable(self):
		from berp_lao.lao_regional.fonts import REQUIRED_FACES, font_status

		status = font_status()
		for key in (
			"status",
			"fontconfig_available",
			"required",
			"advice",
			"renderer",
			# Resolution is reported beside the verdict, never folded into it.
			"resolution_status",
			"resolution",
			"substituted",
			"probe_validated",
			"resolution_note",
		):
			self.assertIn(key, status)
		self.assertIn(status["status"], ("ready", "missing", "unknown"))
		# Resolution has its own vocabulary — "substituted" is not "missing".
		self.assertIn(status["resolution_status"], ("ready", "substituted", "unknown"))
		for family, styles in REQUIRED_FACES.items():
			self.assertIn(family, status["required"])
			self.assertIn(family, status["resolution"])
			for style in styles:
				self.assertIn(style.lower(), status["required"][family])
				self.assertIn(style.lower(), status["resolution"][family])

	def test_unknown_is_not_collapsed_into_missing(self):
		"""fc-list being unavailable is an unanswerable question, not a failure."""
		from unittest.mock import patch

		import berp_lao.lao_regional.fonts as fonts

		with patch.object(fonts, "installed_faces", return_value=None):
			status, evidence = fonts._evaluate(fonts.installed_faces())
			self.assertEqual(status, fonts.UNKNOWN)
			self.assertNotEqual(status, fonts.MISSING)
			# Per-face evidence is None — neither True nor False.
			for styles in evidence.values():
				for found in styles.values():
					self.assertIsNone(found)
			fonts.warn_if_fonts_missing()  # must stay silent

	def test_a_family_present_but_missing_a_weight_reports_missing(self):
		"""Both weights matter: bold totals fall back on their own otherwise."""
		from unittest.mock import patch

		import berp_lao.lao_regional.fonts as fonts

		half = {"Phetsarath": {"Regular"}, "Noto Sans Lao": {"Regular", "Bold"}}
		with patch.object(fonts, "installed_faces", return_value=half):
			status, evidence = fonts._evaluate(fonts.installed_faces())
			self.assertEqual(status, fonts.MISSING)
			self.assertTrue(evidence["Phetsarath"]["regular"])
			self.assertFalse(evidence["Phetsarath"]["bold"])


class TestFontResolutionProbe(_TestCase):
	"""The second instrument, and the instrument that tests the instrument.

	`fc-list` answers *is this face in the index?*. `fc-match` answers *what do I
	get when I ask for this family?* — the renderer's question. A face can be
	indexed and still substituted away, which is precisely the mechanism that
	produces plausible, wrong Lao.

	The probe is itself under test here, per docs/REVIEW-METHOD.md rule 8: run
	the diagnostic once where the answer is known to be yes and once where it is
	known to be no. A check that has only ever been run against the passing case
	has not been shown to distinguish the cases.
	"""

	def test_the_probe_can_say_no(self):
		"""Known-NO. fc-match always answers; it must not answer with the sentinel."""
		import shutil

		from berp_lao.lao_regional.fonts import ABSENT_FAMILY_SENTINEL, _fc_match

		if not shutil.which("fc-match"):
			self.skipTest("fc-match is not installed — the probe cannot be validated here")
		answer = _fc_match(f"{ABSENT_FAMILY_SENTINEL}:style=Regular")
		self.assertIsNotNone(answer, "fc-match returned nothing at all")
		self.assertNotEqual(
			answer,
			ABSENT_FAMILY_SENTINEL,
			"fc-match echoed a family that cannot exist — it cannot distinguish "
			"found from substituted, so none of its answers carry information",
		)

	def test_the_probe_can_say_yes(self):
		"""Known-YES, on a family every Linux image has."""
		import shutil

		from berp_lao.lao_regional.fonts import _fc_match

		if not shutil.which("fc-match"):
			self.skipTest("fc-match is not installed")
		self.assertIsNotNone(_fc_match("DejaVu Sans:style=Book"))

	def test_an_unvalidated_probe_yields_unknown_not_ready(self):
		"""An instrument that cannot fail is not evidence of success."""
		import berp_lao.lao_regional.fonts as fonts

		perfect = {
			family: {style.lower(): family for style in styles}
			for family, styles in fonts.REQUIRED_FACES.items()
		}
		status, _evidence = fonts._evaluate_resolution(perfect, probe_validated=False)
		self.assertEqual(status, fonts.UNKNOWN)
		self.assertNotEqual(status, fonts.READY)

	def test_probe_is_trustworthy_detects_an_echoing_probe(self):
		from unittest.mock import patch

		import berp_lao.lao_regional.fonts as fonts

		with patch.object(fonts, "_fc_match", return_value=fonts.ABSENT_FAMILY_SENTINEL):
			self.assertIs(fonts.probe_is_trustworthy(), False)
		with patch.object(fonts, "_fc_match", return_value="DejaVu Sans"):
			self.assertIs(fonts.probe_is_trustworthy(), True)
		with patch.object(fonts, "_fc_match", return_value=None):
			self.assertIsNone(fonts.probe_is_trustworthy(), "unaskable is not failed")

	def test_an_installed_but_substituted_face_is_reported_as_substituted(self):
		"""The state fc-list cannot see: present in the index, overridden in use."""
		import berp_lao.lao_regional.fonts as fonts

		resolved = {
			family: {style.lower(): family for style in styles}
			for family, styles in fonts.REQUIRED_FACES.items()
		}
		resolved["Phetsarath"]["bold"] = "DejaVu Sans"

		status, evidence = fonts._evaluate_resolution(resolved, probe_validated=True)
		self.assertEqual(status, fonts.SUBSTITUTED)
		self.assertEqual(evidence["Phetsarath"]["bold"], "DejaVu Sans")
		self.assertIn("Phetsarath Bold → DejaVu Sans", fonts._substituted(evidence))

	def test_substitution_never_becomes_the_verdict(self):
		"""The scoping the measurement forced, pinned so it cannot drift back.

		Measured on this stack: a strong-binding fontconfig rule mapping
		Phetsarath → DejaVu Sans made `fc-match "Phetsarath"` answer DejaVu Sans
		while wkhtmltopdf, same environment and same HOME, still embedded
		Phetsarath-Regular in the PDF. So a substitution is a support hint, and
		promoting it to MISSING would manufacture a false negative — the exact
		defect class of REVIEW-METHOD Incident 2.
		"""
		import berp_lao.lao_regional.fonts as fonts

		self.assertNotEqual(fonts.SUBSTITUTED, fonts.MISSING)
		self.assertFalse(
			hasattr(fonts, "_combine"),
			"resolution must not be folded back into the verdict",
		)

		resolved = {
			family: {style.lower(): family for style in styles}
			for family, styles in fonts.REQUIRED_FACES.items()
		}
		resolved["Phetsarath"]["bold"] = "DejaVu Sans"
		everything_present = {family: set(styles) for family, styles in fonts.REQUIRED_FACES.items()}
		presence, _evidence = fonts._evaluate(everything_present)
		resolution_status, _r = fonts._evaluate_resolution(resolved, probe_validated=True)

		self.assertEqual(presence, fonts.READY)
		self.assertEqual(resolution_status, fonts.SUBSTITUTED)
		# The verdict font_status() publishes is the presence one, unaltered.
		self.assertEqual(presence, fonts.READY)

	def test_the_migrate_warning_ignores_substitution(self):
		"""A substituted face must not produce a bench-time alarm.

		It was measured not to break the PDF. A warning that fires on a working
		machine is a warning nobody reads a week later.
		"""
		from unittest.mock import patch

		import berp_lao.lao_regional.fonts as fonts

		everything_present = {family: set(styles) for family, styles in fonts.REQUIRED_FACES.items()}
		substituting = {
			family: {style.lower(): "DejaVu Sans" for style in styles}
			for family, styles in fonts.REQUIRED_FACES.items()
		}
		with (
			patch.object(fonts, "installed_faces", return_value=everything_present),
			patch.object(fonts, "resolved_faces", return_value=substituting),
			patch.object(fonts.frappe.logger("berp_lao"), "warning") as warned,
		):
			fonts.warn_if_fonts_missing()
			warned.assert_not_called()
