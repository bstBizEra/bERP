# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Renderer contract — the instrument that interrogates the external system.

WHY THIS FILE EXISTS
    ADR-A4's first cut specified the wrong mechanism, the implementation matched
    that specification, the tests were derived from it, and 82 tests passed
    against a PDF that was still broken. The missing layer was an instrument that
    asks the renderer itself rather than asking our own rules back.

    The governing lesson, recorded in docs/REVIEW-METHOD.md: *tests derived
    solely from an ADR can prove conformance to a false architectural assumption.
    At least one acceptance instrument must interrogate the external system whose
    behaviour the ADR claims to describe.*

WHAT THIS CAN AND CANNOT CERTIFY
    A. the Unicode source string is correct        ← unit tests
    B. the expected font was resolved              ← here
    C. the expected font was embedded in the PDF   ← here
    D. combining-mark placement is visually right  ← NOT here

    D is a different kind of claim. A PDF's text representation and the visual
    positioning of its combining glyphs are related but not equivalent, so text
    extraction returning usable Lao does not prove a glyph was placed correctly.
    D stays open in BERP-LAO-VERIFY-001 as human visual evidence.

TWO KINDS OF TEST LIVE HERE, AND THEY MEAN DIFFERENT THINGS ON FAILURE
    ``TestRendererCorrectness``
        Renderer correctness tests. They assert the product requirement: every
        Lao glyph the document needs resolves through the approved fallback
        chain and reaches the PDF. A failure here means **the product is
        broken** — fix the product.

    ``TestRendererCompatibilityCharacterization``
        Renderer compatibility characterization. It does not assert a product
        requirement at all. It pins an *observed property of the external
        environment* that ADR-A4 was derived from. A failure here means **the
        environment changed** — the architectural assumption may no longer
        hold, and the ADR must be reconsidered. It does not mean product
        behaviour regressed, and it must not be "fixed" by changing the product.

    Keeping them in one class would make a future maintainer read a red build as
    a regression and patch the wrong thing. Somebody will eventually install a
    "better" wkhtmltopdf and break CI; the class name is what tells them which
    conversation to have.

    The requirement itself is stated as a chain, not as an inventory:

        WRONG    every PDF MUST embed Phetsarath and Noto Sans Lao
        CORRECT  every required glyph MUST resolve through the approved
                 fallback chain

    An ordinary invoice never needs Noto. Its absence from that PDF is correct.

This module skips rather than fails where the renderer or the fonts are absent —
a developer machine without wkhtmltopdf has not broken anything. It is CI and the
deployment target that must not skip.
"""

import os
import re
import shutil
import subprocess
import tempfile

import frappe

try:  # Frappe v16+
	from frappe.tests import IntegrationTestCase as _TestCase
except ImportError:  # Frappe v15
	from frappe.tests.utils import FrappeTestCase as _TestCase

from berp_lao.lao_regional.fonts import READY, _evaluate, installed_faces

#: The supported renderer. Frappe v15 shells out to this binary for every PDF.
RENDERER = "wkhtmltopdf"

#: The primary face. Everyday Lao must be carried by this one.
PRIMARY_FONT = "Phetsarath"
#: The fallback face. It should appear only where the primary lacks a glyph —
#: absent from an ordinary invoice is correct, not a defect.
FALLBACK_FONT = "NotoSansLao"
#: Any Lao carried by this instead means the chain failed.
FORBIDDEN_AS_LAO_CARRIER = "DejaVu"

#: Pali/Sanskrit letters Noto Sans Lao covers and this build of Phetsarath does
#: not — 18 codepoints, which is exactly what MTS Lao's v4.103 rebuild adds. They
#: are the only way to exercise the second link in the fallback chain.
PALI_CORPUS = "ຆຉຌຎຏຐຑຒຓຘຠຨຩຬ"

#: A controlled corpus rather than one phrase: consonant + vowel + tone-mark
#: combinations that a fallback font renders plausibly and wrongly.
LAO_CORPUS = (
	"ໜຶ່ງ",
	"ເກົ່າ",
	"ໃໝ່",
	"ຖ້ວນ",
	"ລ້ານ",
	"ກີບ",
	"ໜຶ່ງລ້ານສອງແສນກີບຖ້ວນ",
)

#: Where a failing artifact is kept, so a human can look at what the renderer did.
ARTIFACT_DIR = os.path.join(tempfile.gettempdir(), "berp_lao_renderer_contract")


def _renderer_available() -> str | None:
	return shutil.which(RENDERER)


def _render(html: str, out_path: str) -> None:
	subprocess.run(
		[RENDERER, "--enable-local-file-access", "-q", "-", out_path],
		input=html.encode("utf-8"),
		check=True,
		timeout=180,
	)


def _embedded_fonts(pdf_path: str) -> list[str]:
	"""Font names the PDF actually carries, via poppler's pdffonts."""
	output = subprocess.run(
		["pdffonts", pdf_path], capture_output=True, text=True, timeout=60, check=True
	).stdout
	names = []
	for line in output.splitlines()[2:]:  # two header lines
		if line.strip():
			names.append(line.split()[0])
	return names


def _extract_text(pdf_path: str) -> str:
	return subprocess.run(
		["pdftotext", pdf_path, "-"], capture_output=True, text=True, timeout=60, check=True
	).stdout


def _keep(pdf_path: str, name: str) -> str:
	"""Retain a failing artifact and return where it went."""
	os.makedirs(ARTIFACT_DIR, exist_ok=True)
	kept = os.path.join(ARTIFACT_DIR, name)
	shutil.copy(pdf_path, kept)
	return kept


class _RendererCase(_TestCase):
	"""Shared plumbing: ask wkhtmltopdf what it does, rather than asking our CSS.

	Not a test case in its own right — it carries the preconditions and the
	corpus renderer that both suites below need.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.renderer = _renderer_available()
		status, _evidence = _evaluate(installed_faces())
		cls.fonts_ready = status == READY

	def setUp(self):
		if not self.renderer:
			self.skipTest(f"{RENDERER} is not installed — nothing to interrogate")
		if not shutil.which("pdffonts"):
			self.skipTest("poppler-utils (pdffonts) is not installed")
		if not self.fonts_ready:
			self.skipTest(
				"the Lao faces are not resolvable through fontconfig here — "
				"run scripts/install-lao-fonts.sh; this is the deployment "
				"precondition, not a code defect"
			)

	def _render_corpus(self, extra_css: str = "") -> tuple[str, list[str], str]:
		html = (
			"<!doctype html><html><head><meta charset='utf-8'><style>"
			+ extra_css
			+ 'body { font-family: "Phetsarath", "Noto Sans Lao", serif; font-size: 18pt; }'
			+ "</style></head><body>"
			+ "".join(f"<p>{phrase}</p>" for phrase in LAO_CORPUS)
			+ "</body></html>"
		)
		handle, pdf_path = tempfile.mkstemp(suffix=".pdf")
		os.close(handle)
		_render(html, pdf_path)
		return pdf_path, _embedded_fonts(pdf_path), _extract_text(pdf_path)


class TestRendererCorrectness(_RendererCase):
	"""Renderer correctness tests — the product requirement.

	Each of these asserts something the shipped system must do: every Lao glyph
	the document needs resolves through the approved fallback chain
	(Phetsarath → Noto Sans Lao) and reaches the PDF.

	A failure here means the product is broken. Fix the product.
	"""

	def test_everyday_lao_is_carried_by_the_primary_face(self):
		"""B and C: Phetsarath resolved, and it reached the artifact."""
		pdf_path, fonts, _text = self._render_corpus()
		joined = " ".join(fonts)
		try:
			self.assertIn(
				PRIMARY_FONT,
				joined,
				f"{PRIMARY_FONT} is not embedded; the PDF carries {fonts}",
			)
		except AssertionError:
			self.fail(f"artifact retained at {_keep(pdf_path, 'primary-face.pdf')}")
		finally:
			os.unlink(pdf_path)

	def test_the_fallback_is_not_carrying_the_lao_text(self):
		"""The original failure mode: DejaVu standing in for a Lao face.

		DejaVu may legitimately appear for Latin runs. What must not happen is
		DejaVu appearing while no Lao face does.
		"""
		pdf_path, fonts, _text = self._render_corpus()
		joined = " ".join(fonts)
		try:
			self.assertTrue(
				PRIMARY_FONT in joined or FALLBACK_FONT in joined,
				f"only fallbacks are embedded: {fonts} — the Lao is being carried "
				f"by {FORBIDDEN_AS_LAO_CARRIER}",
			)
		except AssertionError:
			self.fail(f"artifact retained at {_keep(pdf_path, 'fallback-carrier.pdf')}")
		finally:
			os.unlink(pdf_path)

	def test_the_second_link_in_the_fallback_chain_works(self):
		"""Pali letters Phetsarath lacks must reach Noto, not DejaVu.

		This is why two families ship. An ordinary invoice never needs Noto — its
		absence from that PDF is correct — so the chain is only observable on the
		18 codepoints Phetsarath does not cover.
		"""
		html = (
			"<!doctype html><html><head><meta charset='utf-8'><style>"
			'body { font-family: "Phetsarath", "Noto Sans Lao", serif; font-size: 24pt; }'
			f"</style></head><body><p>{PALI_CORPUS}</p></body></html>"
		)
		handle, pdf_path = tempfile.mkstemp(suffix=".pdf")
		os.close(handle)
		_render(html, pdf_path)
		fonts = _embedded_fonts(pdf_path)
		joined = " ".join(fonts)
		try:
			self.assertIn(
				FALLBACK_FONT,
				joined,
				f"Pali text did not fall through to {FALLBACK_FONT}; the PDF carries "
				f"{fonts}. If it carries {FORBIDDEN_AS_LAO_CARRIER} instead, the "
				"fallback chain is broken and those glyphs are wrong.",
			)
		except AssertionError:
			self.fail(f"artifact retained at {_keep(pdf_path, 'pali-fallback.pdf')}")
		finally:
			os.unlink(pdf_path)

	def test_the_corpus_survives_extraction_as_lao(self):
		"""A weaker check than it looks, and labelled as such.

		Extraction proves the text is present and mapped to Lao codepoints. It
		does NOT prove the combining marks are placed correctly — pdftotext drops
		them — so this asserts base characters only. Mark placement is assertion
		D, and it stays with a human.
		"""
		pdf_path, _fonts, text = self._render_corpus()
		try:
			lao = [c for c in text if 0x0E80 <= ord(c) <= 0x0EFF]
			self.assertGreater(len(lao), 20, f"almost no Lao survived extraction: {text!r}")
			# One unambiguous base sequence, no combining marks involved.
			self.assertIn("ກີບ", re.sub(r"\s+", "", text))
		except AssertionError:
			self.fail(f"artifact retained at {_keep(pdf_path, 'extraction.pdf')}")
		finally:
			os.unlink(pdf_path)


class TestRendererCompatibilityCharacterization(_RendererCase):
	"""Renderer compatibility characterization — NOT a product requirement.

	This suite pins an observed property of the *external environment* that
	ADR-A4 was derived from: on the supported wkhtmltopdf build, declaring
	``@font-face`` for a Lao family overrides the fontconfig lookup, fails, and
	takes the Lao text with it. The contract ("MUST NOT depend on
	``@font-face``") is a consequence of that measurement, not of a preference.

	READ A FAILURE HERE AS:

	    environment changed
	        → the architectural assumption behind ADR-A4 may no longer hold
	        → re-run the comparison and reconsider the ADR

	NOT AS:

	    product behaviour regressed

	Concretely: if somebody upgrades to a wkhtmltopdf build that honours
	``@font-face`` correctly, this test is *supposed* to fail. That failure is
	the signal working. Do not repair it by changing the product, and do not
	delete it to make CI green — amend ADR-A4 with the new measurement first,
	then update this characterization to match what was measured.

	It is kept in this file, and separate from the correctness suite above,
	because the two answer different questions and a shared class name would
	invite a maintainer to patch the wrong layer.
	"""

	def test_declaring_font_face_breaks_this_renderer(self):
		"""Pins the finding the contract rests on, so a future change re-checks it.

		If a wkhtmltopdf build ever honours @font-face correctly, this test fails
		and the contract in ADR-A4 should be revisited — which is the point. It
		asserts the *observed* behaviour of the supported stack, not a universal
		claim about the tool.

		Failure semantics: environment changed, not product regressed. See the
		class docstring before touching anything in response to a red build here.
		"""
		fonts_dir = os.path.join(frappe.get_app_path("berp_lao"), "public", "fonts")
		face_css = (
			'@font-face { font-family: "Phetsarath"; font-weight: 400; '
			f'src: url("file://{fonts_dir}/Phetsarath-Regular.ttf") format("truetype"); }}'
		)
		pdf_path, fonts, _text = self._render_corpus(extra_css=face_css)
		try:
			joined = " ".join(fonts)
			if PRIMARY_FONT in joined or FALLBACK_FONT in joined:
				self.fail(
					"@font-face resolved on this renderer, which contradicts the "
					"measurement ADR-A4 rests on. Re-run the comparison and revisit "
					f"the contract. Artifact: {_keep(pdf_path, 'font-face-worked.pdf')}"
				)
		finally:
			os.unlink(pdf_path)
