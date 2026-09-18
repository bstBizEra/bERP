# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

app_name = "berp_branding"
app_title = "bERP Branding"
app_publisher = "BSTBizEra"
app_description = "bERP platform branding and per-tenant white-label for Frappe/ERPNext"
app_email = "dev@bstbizera.com"
app_license = "GNU General Public License (v3)"
required_apps = ["frappe/erpnext"]

# ─── No app_logo_url hook, on purpose ─────────────────────────────────────────
# Verified against Frappe v15 on a bench (navbar_settings.get_app_logo):
#
#     app_logo = Website Settings.app_logo or Navbar Settings.app_logo
#     if not app_logo:
#         logos = frappe.get_hooks("app_logo_url")
#         app_logo = logos[0]
#         if len(logos) == 2:
#             app_logo = logos[1]
#
# So the hook is not a dependable place to put the logo. On the shape bERP actually
# ships — frappe + erpnext + berp_branding — there are three logos and `logos[0]` is
# Frappe's own, so the hook never wins. Only the accidental two-app case would select
# ours. A branding app cannot rest on a rule that depends on how many *other* apps
# happen to declare the same hook.
#
# NOTE (changed when the app began shipping public/images/): the original reason for
# omitting this hook was that it would have served an asset that did not exist. That
# reason is gone — the asset now exists. The hook stays absent on the surviving
# reason above, which is positional unreliability, not a missing file. Test B9 in
# scripts/check_branding.py guards the absence.
#
# Branding is written to Website Settings instead, which get_app_logo() checks
# first and which therefore always wins. See brand.apply_branding.

# ─── Portal and Desk context ──────────────────────────────────────────────────
update_website_context = "berp_branding.brand.update_website_context"
boot_session = "berp_branding.brand.boot_session"

# ─── Setup ────────────────────────────────────────────────────────────────────
after_install = "berp_branding.brand.after_install"
after_migrate = "berp_branding.brand.after_migrate"
