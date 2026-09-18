#!/usr/bin/env bash
# ==============================================================================
# bERP deployment helper
#
# Installs ERPNext and berp_lao onto the dev and pilot tenants. Run it from the
# bench directory (the one containing apps/ and sites/), not from this app.
#
#   cd /home/frappe/frappe-bench && ./apps/berp_lao/berp_lao/setup/deploy_berp_online.sh
#
# The app is installed as "berp_lao" — that is hooks.app_name and the Python
# package name, and bench resolves it from pyproject.toml's [project] name.
# ==============================================================================

set -euo pipefail

DEV_SITE="${DEV_SITE:-dev.bizera.localhost}"
PILOT_SITE="${PILOT_SITE:-bizera.localhost}"

if [[ ! -d "apps" || ! -d "sites" ]]; then
	echo "error: run this from the bench directory (apps/ and sites/ not found)." >&2
	exit 1
fi

echo "=== 1. Dev tenant (${DEV_SITE}): ERPNext + berp_lao ==="
bench --site "${DEV_SITE}" install-app erpnext
bench --site "${DEV_SITE}" install-app berp_lao

echo "=== 2. Pilot tenant (${PILOT_SITE}): ERPNext only ==="
bench --site "${PILOT_SITE}" install-app erpnext

echo "=== 3. Migrate and build assets ==="
bench --site "${DEV_SITE}" migrate
bench --site "${PILOT_SITE}" migrate
bench build --app berp_lao

echo "=== 4. Verify ==="
bench --site "${DEV_SITE}" list-apps
bench --site "${DEV_SITE}" execute frappe.client.get_count --kwargs "{'doctype': 'Lao Province'}"

echo "=== Deployment finished. ==="
echo "Next: open each Lao company and use Lao Tools -> Install Lao PCG Chart of Accounts,"
echo "then Lao Tools -> Create Lao VAT / WHT Templates."
