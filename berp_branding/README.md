# berp_branding

**bERP platform branding** for Frappe/ERPNext, and per-tenant white-label over it.

A site that installs this app and configures nothing shows **bERP** — not ERPNext.
A site that configures tenant keys shows the tenant. That order is the app.

Companion to [`berp_lao`](https://github.com/bstBizEra/berp_lao_app), which carries
the Lao accounting and localisation. Branding is kept separate from accounting logic
on purpose (ADR-011).

| | |
|---|---|
| App name | `berp_branding` |
| Module | Branding |
| Requires | Frappe + ERPNext v15 (v16 supported) |
| Authority | [`BERP-WL-001`](../Brandkit/bERP%20Platform%20CI) — White-Label & Tenant Branding |
| Licence | GPL-3.0 |

> Renamed from `berp_whitelabel` on 2026-09-19. The app name, the Python package, the
> module and the repository all read `berp_branding` / `BERP-Branding`. Nothing keeps
> the old name.

---

## The two layers

```
PLATFORM   bERP identity, shipped in berp_branding/public/images/
           app_name "bERP", the bERP mark, the bERP favicon
                    ↓  overridden by
TENANT     site_config.json keys, per site
```

This is the bottom of the BERP-WL-001 §4 chain (platform → tenant → company →
document). A key absent from `site_config.json` falls back to the **platform**
default, never to ERPNext's.

### Platform layer

Shipped in `berp_branding/public/images/` and served from `/assets/berp_branding/images/`:

| Asset | File | Used as |
|---|---|---|
| Mark | `berp-logo.svg` | Desk navbar, login page |
| Favicon | `berp-favicon.png` (256×256) | Browser tab |
| App icon | `berp-app-icon.png` (512×512) | Installable/app surfaces |

Derived from `Brandkit/Logo`, with every SVG `id` and class namespaced `berp-*` so
the mark is safe to inline beside other artwork. The wordmark is **not** shipped —
see [`docs/WORDMARK-REEXPORT.md`](docs/WORDMARK-REEXPORT.md).

`bench build --app berp_branding` is what publishes these. A platform default
pointing at an unbuilt asset is worse than no default — a broken image becomes the
platform identity (WL-001 §45) — so `shipped_assets()` reports READY / MISSING /
UNKNOWN for each, and a test asserts none is MISSING.

### Tenant layer

```json
{
  "berp_brand_name":    "LaoCap ERP",
  "berp_brand_logo":    "/files/laocap-logo.svg",
  "berp_brand_favicon": "/files/laocap-favicon.png",
  "berp_brand_splash":  "/files/laocap-banner.png"
}
```

| Key | Lands in | Shown on |
|---|---|---|
| `berp_brand_name` | `Website Settings.app_name` | Login page, browser tab, portal navbar |
| `berp_brand_logo` | `Website Settings.app_logo` | Desk navbar, login page |
| `berp_brand_favicon` | `Website Settings.favicon` | Browser tab icon |
| `berp_brand_splash` | `Website Settings.banner_image` | Portal banner |

Only site-relative paths (`/files/...`) and `https://` URLs are accepted. Anything
else — `http://`, protocol-relative, `data:`, `javascript:`, a bare filename — is
dropped with a warning rather than rendered, and the **platform default is used
instead**, so a bad value never leaves a site with no logo at all.

A key you leave out means *fall back to the platform default*, never *clear it*.

```bash
bench --site <site> set-config berp_brand_name "LaoCap ERP"
bench --site <site> migrate          # after_migrate re-applies
```

---

## Where branding actually has to go

Frappe resolves the Desk and login logo through `get_app_logo()`:

```
Website Settings.app_logo  →  Navbar Settings.app_logo  →  hooks app_logo_url
```

and the hook branch takes `logos[0]` **unless exactly two apps declare it**:

```python
logos = frappe.get_hooks("app_logo_url")
app_logo = logos[0]
if len(logos) == 2:
    app_logo = logos[1]
```

Which branch you land on depends on how many *other* apps declare the hook. On
frappe + erpnext + berp_branding there are three and `logos[0]` is Frappe's own, so
the hook never wins. **This app declares no `app_logo_url`**, and writes Website
Settings instead — checked first, so it always wins. Test `B9` and a bench test both
guard the absence.

Run `branding_status()` when a tenant says the branding looks wrong. It reports what
is configured, what is stored, what `get_app_logo()` returns, which of the three
sources it came from, and whether the platform assets are built.

---

## Surfaces

| Hook | Function | Effect |
|---|---|---|
| `after_install` | `brand.after_install` | Applies branding, forcing over ERPNext's |
| `after_migrate` | `brand.after_migrate` | Re-applies; does **not** overwrite manual changes |
| `update_website_context` | `brand.update_website_context` | Portal navbar label (HTML-escaped), logo, favicon |
| `boot_session` | `brand.boot_session` | `frappe.boot.berp_brand` for Desk JavaScript |

Whitelisted, System Manager only:

- `berp_branding.brand.apply_branding(force=0)` — write the configured branding.
- `berp_branding.brand.branding_status()` — read-only diagnosis.

---

## Installation

```bash
cd ~/frappe-bench
bench get-app https://github.com/bstBizEra/BERP-Branding
bench --site <site> install-app berp_branding
bench build --app berp_branding        # required: publishes the platform assets
bench --site <site> migrate
```

Tenant branding is optional; without it the site shows bERP.

---

## Development

```bash
ruff check berp_branding scripts && ruff format --check berp_branding scripts

# Bench-free preflight — manifest, hook resolution, logic, assets. ~1s, no deps.
python3 scripts/check_branding.py --assets /path/to/Brandkit/Logo

# Full suite (needs a bench)
bench --site <site> set-config allow_tests true
bench --site <site> run-tests --app berp_branding
```

### `scripts/check_branding.py`

A preflight that answers *"if Frappe loaded this app right now, would it work?"*
without a bench. It resolves every hook the way `frappe.get_attr` does and exercises
the branding logic against a stubbed `frappe`.

| Section | Covers |
|---|---|
| **A** | Manifest coherence — pyproject ↔ package dir ↔ `app_name` ↔ modules.txt, and module/file shadowing |
| **B** | Every hook target imports and the attribute exists |
| **C** | Branding logic: fallbacks, asset validation, `force` semantics, escaping, platform defaults |
| **D** | Asset contract: WL-001 §17 set, SVG safety, live text, namespacing, declared paths on disk |

It is a preflight, not a replacement for the bench suite: it cannot prove what a real
site does with Website Settings, only that the app is internally coherent and its
pure logic is correct.

**The harness is validated against a known-good tree, not just run.** Per
`docs/REVIEW-METHOD.md` P2, a negative diagnostic is untrustworthy until the
mechanism has been checked against a system known to be correct. Doing that caught
three defects in the harness itself — including one where section B reported
`No module named 'frappe'` as a product defect, which would have produced four
fabricated failures.

---

## Status

The rename from `berp_whitelabel` is complete and the preflight is green on every
app-level check (**33 pass**). Two failures remain, both in the source brand kit and
both needing a designer:

- `D4` — the wordmark SVGs carry live text. See [`docs/WORDMARK-REEXPORT.md`](docs/WORDMARK-REEXPORT.md).
- `D2` — `logo.inverse` is missing from the kit (WL-001 §17 requires five assets).

Not done, and needed before a tenant sees this:

- [x] ~~Re-verify on a bench.~~ Done 2026-09-19 on `dev.berp.bizera.la`,
      **Frappe 16.33.1 / ERPNext 16.34.2** — the v16 code path, which had never been
      exercised. `branding_status()` on the live site reports
      `resolved_from: Website Settings` and both platform assets `READY`.
- [ ] Email template and PDF letterhead branding.
- [ ] Browser check of Desk, login and mobile layouts per tenant. Neither suite
      touches the UI.
- [ ] The WL-001 roadmap proper: Brand Profile records, theme compilation and
      validation, company/document scopes, custom domains, entitlements.

### Tenant labels

| Site | Display name |
|---|---|
| dev.berp.bizera.la | bERP Development Tenant |
| bizera.bizera.la | BizEra ERP |
| laocap.bizera.la | LaoCap ERP |

Proposed values, not applied settings.

---

## Licence

GNU General Public License v3. See [`license.txt`](license.txt).
