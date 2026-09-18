#!/usr/bin/env bash
# Install or update berp_lao on the bERP private development VM and run its suite.
#
#   ssh berp-linux
#   bash deploy-berp-lao-dev.sh
#
# Development only. This script installs an app and runs its tests; it does not
# touch production, does not open any port, and does not read or write secrets.
# Do not run it against berp-prod.
#
# It is idempotent: safe to re-run after each `git pull`.

set -euo pipefail

BENCH="${BENCH:-/srv/berp/deployments/dev}"
SITE="${SITE:-dev.berp.bizera.la}"
APP="berp_lao"
REPO="${REPO:-https://github.com/bstBizEra/berp_lao_app}"
BRANCH="${BRANCH:-feat/installable-app-lao-pcg-vat}"

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
fail() { printf '\n\033[31mFAILED: %s\033[0m\n' "$*" >&2; exit 1; }

[ -d "$BENCH/sites" ] || fail "no bench at $BENCH (override with BENCH=...)"
cd "$BENCH"

say "Bench and site"
bench --site "$SITE" version || fail "site $SITE not reachable"

# ── fetch or update the app ───────────────────────────────────────────────────
if [ -d "apps/$APP" ]; then
	say "Updating apps/$APP to origin/$BRANCH"
	git -C "apps/$APP" fetch --all --prune
	git -C "apps/$APP" checkout "$BRANCH"
	git -C "apps/$APP" reset --hard "origin/$BRANCH"
else
	say "Fetching $APP from $REPO ($BRANCH)"
	# --skip-assets: the Python suite does not need a built bundle, and the asset
	# build pulls git tarballs that a restricted egress policy may refuse.
	bench get-app "$REPO" --branch "$BRANCH" --skip-assets
fi

git -C "apps/$APP" log --oneline -1

# ── install or migrate ────────────────────────────────────────────────────────
if bench --site "$SITE" list-apps | grep -qx "$APP"; then
	say "Already installed — migrating"
	bench --site "$SITE" migrate
else
	say "Installing $APP on $SITE"
	bench --site "$SITE" install-app "$APP"
fi

say "Installing the Lao fonts into fontconfig"
# wkhtmltopdf resolves fonts through fontconfig and ignores @font-face, so this is
# what makes a Lao PDF render correctly. Skipping it does not give you missing
# glyphs — it gives you Lao with the tone marks in the wrong order.
sudo bash "$BENCH/apps/$APP/../scripts/install-lao-fonts.sh" 2>/dev/null \
	|| sudo bash "$(dirname "${BASH_SOURCE[0]}")/install-lao-fonts.sh" \
	|| echo "  (font install failed — run scripts/install-lao-fonts.sh by hand, then bench restart)"
bench --site "$SITE" execute berp_lao.lao_regional.fonts.font_status || true

say "Building assets"
bench build --app "$APP" || echo "  (asset build failed — the Desk CSS will be stale, tests are unaffected)"

# ── verify ────────────────────────────────────────────────────────────────────
say "Post-install checks"
bench --site "$SITE" execute frappe.client.get_count --kwargs "{'doctype': 'Lao Province'}"
bench --site "$SITE" execute frappe.client.get_count --kwargs "{'doctype': 'Lao District'}"
# Expect 18 and 148.

say "Running the suite"
bench --site "$SITE" set-config allow_tests true
bench --site "$SITE" run-tests --app "$APP"

cat <<'NEXT'

================================================================================
The suite is the automated half. It does not touch the Desk UI, so these four
still need a browser — open a tunnel first and do not expose the VM:

    ssh -N -L 18080:127.0.0.1:8080 berp-linux
    # then http://127.0.0.1:18080

  1. Company form for a Lao company: the "Lao Localisation Active" indicator
     shows, and a "Lao Tools" menu appears with two buttons.
     This exercises hooks.extend_bootinfo — the country name has to reach
     frappe.boot, or the whole form script silently does nothing.

  2. Lao Tools → Install Lao PCG Chart of Accounts, then → Create Lao VAT / WHT
     Templates, in that order. The chart must land 116 accounts, 10 roots.

  3. A Sales Invoice with no VAT row must raise the orange "Lao VAT Notice";
     one at or above 500,000 LAK with no customer TIN must raise the TIN notice.

  4. Print the invoice with the "Lao Tax Invoice" format. The amount in words
     must be Lao script, not English — that is lao_numbers.py doing its job.
     Check the Lao glyphs actually render; the fonts load from Google Fonts, so
     a VM with restricted egress will show boxes.

Then run docs/BERP-LAO-VERIFY-001.md step 7 by hand: the Lao Monthly VAT Return
for the period must read 120,000 output VAT, not 170,000. If it reads 170,000 the
report is counting freight as VAT again.
================================================================================
NEXT
