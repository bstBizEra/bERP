# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Lao font availability — BERP-LAO-ARCH-001 ADR-A4.

THE CONTRACT
    For server-generated bERP PDFs using the supported wkhtmltopdf rendering
    stack, Lao typography MUST NOT depend on CSS ``@font-face``. The required Lao
    static font faces MUST be installed in the server font environment and
    resolvable through fontconfig. Print CSS MAY specify the corresponding
    ``font-family``, but MUST NOT embed or override those Lao faces with
    ``@font-face``.

That is scoped to this rendering stack on purpose. ``@font-face`` is reported to
work for some fonts and fail for others across wkhtmltopdf versions, file formats
and platforms; the inconsistency is itself why it is not part of the contract.

SEVERITY
    This is not a typography defect. DejaVu covers the Lao block, so a missing
    Phetsarath does not produce boxes — it produces Lao that is visually
    plausible with the combining marks in the wrong order (ໜຶງ່ for ໜຶ່ງ), on a
    document that still looks valid. Classify it as **document integrity /
    regulatory presentation risk**. The practical consequence: "characters
    rendered" is not a success criterion for this system.

STATE SEMANTICS
    READY, MISSING and UNKNOWN are three states, not two. ``fc-list`` being
    unavailable means the font state cannot be determined here — it does not mean
    the font is absent, and this module never collapses UNKNOWN into MISSING.

TWO INSTRUMENTS, TWO QUESTIONS — AND ONLY ONE VERDICT
    ``fc-list`` answers *is this face in the index?* — presence. That is the
    question this module's ``status`` reports, because it is the one whose answer
    was shown to track the rendered PDF.

    ``fc-match`` answers *what does fontconfig hand back when asked for this
    family?* — resolution. It looks like the renderer's own question, and it is
    reported here, but it is NOT the verdict, because it was measured and the two
    disagree:

        A strong-binding fontconfig rule mapping Phetsarath → DejaVu Sans made
        ``fc-match "Phetsarath"`` answer ``DejaVu Sans`` while, in the same
        environment and the same HOME, wkhtmltopdf still resolved and embedded
        ``Phetsarath-Regular`` in the PDF.

    Qt WebKit does not take the same path through fontconfig that ``fc-match``
    does. So a substitution reported here is a strong *support hint* — almost
    always a rule in ``/etc/fonts/local.conf`` — and never grounds for failing a
    build. Letting it fail one would manufacture exactly the false negative
    docs/REVIEW-METHOD.md Incident 2 is about.

    The instrument that does answer the renderer's question is
    ``tests/test_renderer_contract.py``, which renders a PDF and reads the fonts
    out of it. Nothing here replaces it.

THE PROBE IS ITSELF UNDER TEST
    ``fc-match`` always answers with *something*, so a positive answer proves
    nothing until the probe has been shown to produce a negative when one is
    due. :func:`probe_is_trustworthy` asks it for a family that cannot exist. If
    the probe claims to have found that, its answers carry no information and
    the resolution verdict is UNKNOWN rather than READY. This is
    docs/REVIEW-METHOD.md P2: *a negative diagnostic result is not trustworthy
    until the diagnostic mechanism itself has been validated against a known-good
    system* — read here in both directions. Validating this probe against a
    known-bad system is what showed its claim had to be narrowed; see the
    measurement above.
"""

import os
import subprocess

import frappe
from frappe import _

#: Families the Lao print formats ask for, in fallback order, and the styles of
#: each that must be present. Both weights matter: a print format that goes bold
#: for totals falls back on its own if only Regular is installed.
REQUIRED_FACES = {
	"Phetsarath": ("Regular", "Bold"),
	"Noto Sans Lao": ("Regular", "Bold"),
}
REQUIRED_FAMILIES = tuple(REQUIRED_FACES)

READY = "ready"
MISSING = "missing"
UNKNOWN = "unknown"

#: Resolution-only verdict. Deliberately NOT ``MISSING``: a substituted face was
#: measured to still render correctly on this stack, so it is a hint to chase,
#: not a failure to report. See the module docstring.
SUBSTITUTED = "substituted"

#: A family name no font can carry. ``fc-match`` never says "not found" — it
#: substitutes — so this is how the probe is shown to be able to say no.
ABSENT_FAMILY_SENTINEL = "BerpLaoAbsentFamilySentinel"


def shipped_fonts_dir() -> str:
	"""Where this app keeps its canonical copies."""
	return os.path.join(frappe.get_app_path("berp_lao"), "public", "fonts")


def shipped_font_files() -> list[str]:
	"""Absolute paths of every TTF the app ships."""
	root = shipped_fonts_dir()
	return sorted(
		os.path.join(base, name)
		for base, _dirs, files in os.walk(root)
		for name in files
		if name.endswith(".ttf")
	)


def installed_faces() -> dict[str, set[str]] | None:
	"""``{family: {style, ...}}`` as fontconfig sees it, or None if it cannot be asked.

	None is the UNKNOWN state and is not the same as an empty mapping, which would
	mean fontconfig answered and knows of no fonts at all.
	"""
	try:
		output = subprocess.run(
			["fc-list", "--format", "%{family}\\t%{style}\\n"],
			capture_output=True,
			text=True,
			timeout=20,
			check=True,
		).stdout
	except (OSError, subprocess.SubprocessError):
		return None

	faces: dict[str, set[str]] = {}
	for line in output.splitlines():
		family_field, _, style_field = line.partition("\t")
		# fc-list reports comma-separated aliases for one face.
		families = [part.strip() for part in family_field.split(",") if part.strip()]
		styles = [part.strip() for part in style_field.split(",") if part.strip()]
		for family in families:
			faces.setdefault(family, set()).update(styles or ["Regular"])
	return faces


def _fc_match(pattern: str) -> str | None:
	"""The family ``fc-match`` hands back for ``pattern``, or None if it cannot be asked."""
	try:
		output = subprocess.run(
			["fc-match", pattern, "--format", "%{family}"],
			capture_output=True,
			text=True,
			timeout=20,
			check=True,
		).stdout
	except (OSError, subprocess.SubprocessError):
		return None
	# fc-match reports comma-separated aliases for one face; the first is the name.
	first = output.split(",")[0].strip()
	return first or None


def probe_is_trustworthy() -> bool | None:
	"""Has ``fc-match`` been shown able to answer *no*?

	Ask it for a family that cannot exist. A healthy fontconfig substitutes
	something else, which is the negative answer we need it to be capable of. If
	it echoes the sentinel back, the probe cannot distinguish found from
	substituted and every other answer it gives is worthless.

	Returns None when ``fc-match`` cannot be run at all — unanswerable, not failed.
	"""
	answer = _fc_match(f"{ABSENT_FAMILY_SENTINEL}:style=Regular")
	if answer is None:
		return None
	return answer != ABSENT_FAMILY_SENTINEL


def resolved_faces() -> dict[str, dict[str, str | None]] | None:
	"""``{family: {style: family fontconfig actually returns}}``, or None if unaskable.

	This is the renderer's question, not the index's. ``None`` for a style means
	``fc-match`` could not be asked for that face.
	"""
	out: dict[str, dict[str, str | None]] = {}
	for family, styles in REQUIRED_FACES.items():
		out[family] = {}
		for style in styles:
			out[family][style.lower()] = _fc_match(f"{family}:style={style}")
	if all(value is None for styles in out.values() for value in styles.values()):
		return None
	return out


def _evaluate_resolution(
	resolved: dict[str, dict[str, str | None]] | None,
	probe_validated: bool | None,
) -> tuple[str, dict]:
	"""READY / SUBSTITUTED / UNKNOWN — what fontconfig hands back, and nothing more.

	UNKNOWN when the probe could not be run, or could not be shown able to say
	no. An instrument that cannot fail is not evidence of success.

	SUBSTITUTED is advisory. It does not mean the PDF is wrong — measured on this
	stack, a face fontconfig substitutes away can still reach the PDF intact — so
	no caller may turn it into a build failure. It means *look at this machine's
	fontconfig rules*, which is worth saying because nothing else says it.
	"""
	if resolved is None or probe_validated is not True:
		evidence = {
			family: dict.fromkeys((style.lower() for style in styles), None)
			for family, styles in REQUIRED_FACES.items()
		}
		return UNKNOWN, evidence

	evidence: dict[str, dict[str, str | None]] = {}
	unanswered = False
	substituted = False
	for family, styles in REQUIRED_FACES.items():
		evidence[family] = {}
		for style in styles:
			answer = resolved.get(family, {}).get(style.lower())
			evidence[family][style.lower()] = answer
			if answer is None:
				unanswered = True
			elif answer != family:
				substituted = True

	if substituted:
		return SUBSTITUTED, evidence
	if unanswered:
		return UNKNOWN, evidence
	return READY, evidence


def _substituted(resolution: dict) -> list[str]:
	"""Faces fontconfig answers with a *different* family — installed or not."""
	return [
		f"{family} {style.title()} → {answer}"
		for family, styles in resolution.items()
		for style, answer in styles.items()
		if answer is not None and answer != family
	]


def _evaluate(faces: dict[str, set[str]] | None) -> tuple[str, dict]:
	"""Resolve the three-state status and the per-face evidence behind it."""
	if faces is None:
		evidence = {family: dict.fromkeys(styles, None) for family, styles in REQUIRED_FACES.items()}
		return UNKNOWN, evidence

	evidence = {}
	complete = True
	for family, styles in REQUIRED_FACES.items():
		present = faces.get(family, set())
		evidence[family] = {}
		for style in styles:
			found = style in present
			evidence[family][style.lower()] = found
			complete = complete and found
	return (READY if complete else MISSING), evidence


@frappe.whitelist()
def font_status() -> dict:
	"""Machine-readable report on whether the Lao fonts will reach a rendered PDF.

	Call this first when a tenant says an invoice looks wrong. The shape is meant
	for health checks and support diagnostics as much as for a person.
	"""
	frappe.only_for("System Manager")

	faces = installed_faces()
	status, required = _evaluate(faces)

	probe_validated = probe_is_trustworthy()
	resolution_status, resolution = _evaluate_resolution(resolved_faces(), probe_validated)

	return {
		# The verdict. Presence, because that is the answer measured to track the
		# rendered PDF. Resolution below is evidence, not a second verdict.
		"status": status,
		"fontconfig_available": faces is not None,
		"required": required,
		# Advisory only — see resolution_note. Never fail a build on this.
		"resolution_status": resolution_status,
		"resolution": resolution,
		"substituted": _substituted(resolution),
		"probe_validated": probe_validated,
		"resolution_note": (
			"fc-match reports what fontconfig hands back; wkhtmltopdf was measured "
			"resolving a face that fc-match substituted away. Treat a substitution "
			"as a pointer at /etc/fonts/local.conf, not as a broken PDF. The "
			"rendered-PDF question is answered by tests/test_renderer_contract.py."
		),
		"shipped_with_app": [os.path.basename(p) for p in shipped_font_files()],
		"renderer": "wkhtmltopdf",
		"contract": (
			"Lao faces must be resolvable through fontconfig on this machine. "
			"Print CSS must not declare @font-face for them."
		),
		"advice": _advice(status, required, resolution, probe_validated),
	}


def _missing_faces(required: dict) -> list[str]:
	return [
		f"{family} {style.title()}"
		for family, styles in required.items()
		for style, found in styles.items()
		if found is False
	]


def _advice(
	status: str,
	required: dict,
	resolution: dict | None = None,
	probe_validated: bool | None = None,
) -> str:
	hint = ""
	substituted = _substituted(resolution or {})
	if substituted:
		hint = (
			f" Separately, fontconfig substitutes {', '.join(substituted)} — usually a "
			"rule in /etc/fonts/local.conf. That was measured NOT to stop wkhtmltopdf "
			"embedding the right face, so it is a lead to follow if a PDF does look "
			"wrong, not a verdict on its own."
		)

	if status == UNKNOWN:
		return (
			"fc-list is not available here, so font state cannot be determined from "
			"inside Frappe. This is not evidence that the fonts are missing — verify "
			"on the machine that renders PDFs." + hint
		)

	if status == MISSING:
		return (
			f"Not resolvable through fontconfig on this machine: "
			f"{', '.join(_missing_faces(required))}. PDFs will fall back to a font that "
			"covers Lao but stacks the combining marks wrongly, so the documents will "
			"look plausible and be wrong. Run scripts/install-lao-fonts.sh here, then "
			"restart the workers." + hint
		)

	if probe_validated is False:
		hint += (
			" Note also that fc-match answered for a family that cannot exist on this "
			"machine, so its substitution reporting above carries no information."
		)
	return "All required Lao faces are resolvable through fontconfig on this machine." + hint


def warn_if_fonts_missing():
	"""hooks.after_migrate — say so at install time rather than at print time.

	Silent in the UNKNOWN state: an unanswerable question is not a failure, and a
	warning that fires on every bench without fontconfig would be ignored within a
	week.
	"""
	status, required = _evaluate(installed_faces())
	if status != MISSING:
		return

	message = _(
		"berp_lao: {0} not resolvable through fontconfig on this server. Lao PDFs "
		"will render in a fallback font with the combining marks in the wrong order — "
		"plausible-looking and wrong. Run scripts/install-lao-fonts.sh here."
	).format(", ".join(_missing_faces(required)))

	frappe.logger("berp_lao").warning(message)
	print(f"\n\033[33m{message}\033[0m\n")  # a bench-time notice, not app output
