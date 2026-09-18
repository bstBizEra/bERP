#!/usr/bin/env bash
# Install the Lao fonts berp_lao ships into the system font path.
#
#   sudo bash scripts/install-lao-fonts.sh
#
# Run this on every machine that RENDERS PDFs — the bench host, and each worker
# if they are separate. It is idempotent.
#
# THE CONTRACT
#   For server-generated bERP PDFs using the supported wkhtmltopdf rendering
#   stack, Lao typography MUST NOT depend on CSS @font-face. The required Lao
#   static font faces MUST be installed in the server font environment and
#   resolvable through fontconfig. This script is what satisfies that.
#
# WHY. Measured on wkhtmltopdf 0.12.6, same HTML, only the @font-face block
# differing, fonts installed on the machine in both runs:
#
#     with @font-face        embedded: DejaVuSans          text: "—"
#     without, font present  embedded: Phetsarath-Regular  text: ໜຶ່ງລ້ານສອງແສນກີບຖ້ວນ
#
# That is a statement about this rendering stack, not about every wkhtmltopdf
# build — reports differ across versions, formats and platforms, and that
# inconsistency is itself why @font-face is not part of the contract.
#
# SEVERITY. DejaVu covers the Lao block, so skipping this does not give you
# missing glyphs — it gives you Lao with the combining marks in the wrong order,
# on a document that still looks valid. Document integrity risk, not typography.

set -euo pipefail

DEST="${DEST:-/usr/local/share/fonts/berp-lao}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${SRC:-$HERE/../berp_lao/public/fonts}"

[ -d "$SRC" ] || { echo "no fonts at $SRC — set SRC=..." >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || { echo "run as root (sudo), writing to $DEST" >&2; exit 1; }

echo "==> installing from $SRC to $DEST"
mkdir -p "$DEST"
find "$SRC" -name '*.ttf' -exec cp -v {} "$DEST/" \;
# SIL OFL 1.1 requires the licence to travel with the font.
find "$SRC" -name 'LICENSE-*.txt' -exec cp -v {} "$DEST/" \;
cp -v "$SRC/FONT-PROVENANCE.md" "$DEST/" 2>/dev/null || true
chmod 644 "$DEST"/*

echo "==> rebuilding the font cache"
fc-cache -f "$DEST" >/dev/null

# ---------------------------------------------------------------------------
# Validate the diagnostic BEFORE trusting it.
#
# fc-match never says "not found" — it substitutes. So ask it for a family that
# cannot exist. If it hands that name back, this machine's fontconfig cannot
# produce a negative, and every OK below would be meaningless.
#
# docs/REVIEW-METHOD.md P2: a negative diagnostic result is not trustworthy
# until the diagnostic mechanism itself has been validated against a known-good
# system. Read in both directions — a positive one is not either.
#
# This block only gates the advisory fc-match reporting below; a fontconfig that
# cannot answer no makes that reporting uninformative, not the install wrong.
# ---------------------------------------------------------------------------
echo "==> validating the diagnostic"
SENTINEL="BerpLaoAbsentFamilySentinel"
sentinel_answer="$(fc-match "$SENTINEL:style=Regular" --format '%{family}' 2>/dev/null || true)"
probe_ok=1
if [ -z "$sentinel_answer" ] || [ "$sentinel_answer" = "$SENTINEL" ]; then
	probe_ok=0
	echo "    fc-match cannot produce a negative on this machine, so its" >&2
	echo "    substitution reporting below carries no information. Presence" >&2
	echo "    checking is unaffected." >&2
else
	echo "    OK      fc-match answers '$sentinel_answer' for a family that cannot exist"
fi

echo "==> verifying"
missing=0
# Two questions, asked separately.
#
#   fc-list   is this face in the index?      → presence
#   fc-match  what does fontconfig hand back   → resolution. It LOOKS like the
#             when asked for this family?        renderer's question. It is not.
#
# Presence is the gate. Resolution is reported beside it and never fails the
# install: the two were measured to disagree, and wkhtmltopdf followed presence.
#
# Both weights, not just the family: a print format that goes bold for totals
# falls back on its own if only Regular is installed.
#
# No pipe into `grep -q` here. Under `set -o pipefail` grep exits on its first
# match, SIGPIPEs fc-list, and the pipeline reports failure — which shows up as
# an intermittent false MISSING depending on buffering. Capture, then test.
for face in "Phetsarath:Regular" "Phetsarath:Bold" \
            "Noto Sans Lao:Regular" "Noto Sans Lao:Bold"; do
	family="${face%%:*}"; style="${face##*:}"
	found="$(fc-list "$family:style=$style" --format '%{file}\n' 2>/dev/null || true)"
	if [ -z "$found" ]; then
		echo "    MISSING $family $style — not in the font index" >&2
		missing=1
		continue
	fi
	if [ "$probe_ok" -eq 0 ]; then
		echo "    OK      $family $style (resolution not checked)"
		continue
	fi
	got="$(fc-match "$family:style=$style" --format '%{family}' 2>/dev/null || true)"
	got="${got%%,*}"   # fc-match lists aliases; the first is the name
	if [ "$got" = "$family" ]; then
		echo "    OK      $family $style"
	else
		# Advisory, NOT a failure. Measured on this stack: a strong-binding rule
		# mapping Phetsarath -> DejaVu Sans made fc-match answer DejaVu Sans while
		# wkhtmltopdf still embedded Phetsarath-Regular in the PDF. Failing the
		# install here would block a machine that renders correctly — the same
		# false-negative shape as the grep -q bug above.
		echo "    NOTE    $family $style is installed, but fc-match answers '$got'" >&2
		echo "            a rule in /etc/fonts/local.conf is likely overriding it." >&2
		echo "            Not treated as a failure: this renderer was measured" >&2
		echo "            embedding the right face anyway. Worth checking if a PDF" >&2
		echo "            later looks wrong." >&2
	fi
done

if [ "$missing" -ne 0 ]; then
	echo "fontconfig cannot see every family — do not ship invoices from here" >&2
	exit 1
fi

cat <<'NEXT'

Installed. Two things left:

  1. Restart the bench workers, so the running processes pick up the new cache:
         bench restart          # or: sudo supervisorctl restart all

  2. Confirm from inside Frappe:
         bench --site <site> execute berp_lao.lao_regional.fonts.font_status

     and then print one Lao Tax Invoice to PDF and look at it. The suite can
     prove the font is installed; only a person can confirm the tone marks sit
     where they should.
NEXT
