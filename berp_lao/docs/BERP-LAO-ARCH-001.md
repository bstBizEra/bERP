# BERP-LAO-ARCH-001 — Structural decisions for berp_lao

**Date:** 2026-09-16
**Status:** A1, A2, A3 (amended), A4, A5 and A7 implemented 2026-09-16; A6 deferred.
**Applies to:** `berp_lao` at `82c9ea3`
**Supersedes:** nothing. Feeds `BERP-LAO-ROADMAP-001`.
**Method:** see [`REVIEW-METHOD.md`](REVIEW-METHOD.md) — ADR-A4 is the incident that produced it.

---

## Why now

The app works. 70 tests pass on a bench, and six defects were found and fixed the first
time it ran. That is the right moment to fix the shape of it: the statutory reporting
work (`BERP-LAO-MARKET-001` §6.2, P0) will roughly double the code, and it will land in
whatever structure exists when it starts.

Every decision below is ranked by what it costs to do later rather than now.

---

## The principle

**Statutory data lives in JSON; code resolves it against a company.**

The app already has this rule and already explains it, in the header of
`lao_regional/data/lao_tax_templates.json`. It is applied to the chart of accounts and
the tax templates and to nothing else. It should be the default for everything the
statute determines: field definitions, statement layouts, report formats, rate schedules.

The reason is not tidiness. Lao statute changes — four withholding rates moved on
1 July 2026 — and a dated row in a JSON file is a diff a Lao accountant can review
without reading Python.

---

## ADR-A1 — Split `lao_regional/utils.py`

**Status:** **implemented 2026-09-16** · **Cost later:** grows with every rule

### Context

`utils.py` is 316 lines and 17 functions covering three unrelated concerns: country
resolution, sales-invoice rules, purchase-invoice rules. Six modules import from it:

| Importer | What it wants |
|---|---|
| `chart_of_accounts/lao_pcg.py` | `is_lao_country` |
| `report/lao_vat_return/lao_vat_return.py` | `is_lao_country` |
| `setup/tax_templates.py` | `is_lao_company` |
| `setup/install.py` | `lao_country_name` |
| `lao_regional/lao_numbers.py` | `is_lao_company` |
| `tests/*` | all of the above |

All six want **country resolution**. None wants the invoice rules. And
`lao_numbers.py:174` does its import *inside a function* — a deferred import to dodge a
circular dependency. That is the module boundary telling us it is in the wrong place.

### Decision

```
lao_regional/
├── country.py          lao_country_name, is_lao_country, is_lao_company,
│                       is_vat_registered, extend_bootinfo, LAO_COUNTRY_CODE
└── rules/
    ├── __init__.py
    ├── sales_invoice.py     validate_lao_sales_invoice + its private helpers
    ├── purchase_invoice.py  validate_lao_purchase_invoice + its private helpers
    └── company.py           update_company_lao_defaults
```

`country.py` is infrastructure with no dependency on anything else in the app, which
removes the cycle. `rules/` is where statute lives, and is where every roadmap item adds
code: WHT application, micro-enterprise CIT, statement mapping.

`hooks.py` doc_events paths change. `utils.py` disappears rather than becoming a
re-export shim — the app has no external consumers, so there is nothing to keep
compatible, and a shim would just preserve the bad name.

### Consequences

- Six import sites change. The 70 tests prove it.
- `hooks.py` dotted paths change; `test_every_hooked_method_resolves` catches a mistake.
- The word "utils" leaves the codebase, which is the point.

---

## ADR-A2 — Move the custom field definitions to JSON

**Status:** **implemented 2026-09-16** · **Cost later:** rises with field count

### Context

`get_lao_custom_fields()` is **122 of `install.py`'s 295 lines — 41% of the file** — and
it is a literal. It is data wearing a function.

Two of the six defects the bench found were field/metadata mismatches against ERPNext
(`Stock In Hand`, `Bank Charge`). The same class of bug is live here: nothing checks that
`insert_after` names a field that exists, or that a `Link` field's `options` names a real
DocType. A typo ships silently and the field lands in the wrong place, or nowhere.

### Decision

Move to `lao_regional/data/custom_fields.json`, keyed by DocType, mirroring the shape of
`lao_tax_templates.json`. `create_lao_custom_fields()` loads and applies it.

Add a test that, for every entry, asserts against the **live DocType meta**:

- the target DocType exists
- `insert_after` names a field that exists on it
- a `Link` field's `options` names a DocType that exists
- `fieldtype` is one of Frappe's actual field types

That test can only run on a bench, which is exactly where it belongs — it is the same
shape as `test_every_account_type_is_valid_in_this_erpnext`, which already exists and
already earned its place.

### Consequences

- `install.py` drops to ~170 lines and becomes readable as a sequence of steps.
- Field changes become reviewable diffs.
- The `after_migrate` hook (added 2026-09-15) already re-applies fields on migrate, so a
  field added to the JSON reaches existing sites with no extra work.

---

## ADR-A3 — Rename `taxris/` to `e_invoice/`

**Status:** **implemented 2026-09-16, amended on implementation.** See the amendment below.

### Context

`BERP-LAO-MARKET-001` §3 established that **TaxRIS is the tax administration's internal
system** — taxpayer records, notices, audit memoranda, operated by tax officers, with an
eight-round 2026 training programme for district offices. It is not and was never going
to be a taxpayer API.

The taxpayer-facing surfaces are **DTax** (registration and filing) and the **E-Tax
Invoice system the Ministry of Finance launched on 29 May 2026**, which at least two Lao
products already connect to.

The package is 312 lines named after the wrong system.

### Decision as proposed

Rename `lao_regional/taxris/` → `lao_regional/e_invoice/`, and retarget the payload
builder from VAT-return filing to e-tax-invoice issuance. `BERP-LAO-TAXRIS-001` keeps its
number (it is a published identifier) and carries the amendment it already has.

Do it **now, while the package is inert and nothing imports it.** After a client is built
against it, this is a breaking rename with a migration.

### Amendment, made while implementing — 2026-09-16

**The rename was right. The retarget was not.** Reading the market brief again against the
code showed the proposal had collapsed two things into one.

There are **two** taxpayer-facing surfaces, and the existing payload serves the other one:

| Surface | What a taxpayer does with it | Module |
|---|---|---|
| **DTax** | registration, and periodic filing | `e_filing/vat_return.py` |
| **E-Tax Invoice** | per-invoice issuance; MoF launched it 29 May 2026 | `e_filing/e_invoice.py` |

Retargeting the VAT-return payload to e-invoice issuance would have deleted correct work
and left the filing surface with nothing, in order to satisfy a name. So:

- the package is `lao_regional/e_filing/`, named for **what it does** rather than for
  either counterparty — a name that survives the next time a Lao system is renamed;
- `payload.py` → `vat_return.py`, unchanged in substance, its docstring corrected to say
  DTax rather than TaxRIS;
- `e_invoice.py` is new: `EInvoicePayload`, `EInvoiceLine`, `build_e_invoice_payload`,
  and a `check()` that reports why an invoice is not fit to issue — missing seller TIN,
  missing buyer TIN above 500,000 LAK, VAT on a zero-rated export, a VAT amount that does
  not follow from the net, a foreign currency with no rate;
- `TaxRISClient` → two interfaces, `VatReturnTransport` and `EInvoiceTransport`, because a
  transport that files VAT returns has no reason to also issue invoices;
- exceptions are `LaoFilingError` / `LaoFilingNotConfigured`;
- `berp_lao_taxris_client` → `berp_lao_dtax_client` and `berp_lao_e_invoice_client`.

Neither payload is modelled on a wire format. Both are modelled on what Lao statute
requires the document to carry, which is knowable and stable while no specification is
public — the same reasoning that was right for the VAT return the first time.

### Consequences

- The abstract transport and the inert default client survive — that design was right and
  remains right while no specification is public. **The safety property is unchanged and
  now asserted:** anything unconfigured resolves to the inert recorder, so a misspelt key
  cannot submit to a tax authority.
- A future reader stops being told the integration target is TaxRIS.
- The package shipped 312 lines with **no tests at all**. It now has 16, including the
  safety property above and a `check()` exercised against six known-bad payloads.
- `e_invoice.py` computes VAT from the standard-rate tax rows, never from
  `total_taxes_and_charges` — the same header-sum trap the VAT report was fixed for. The
  test that proves it selects its invoice *by the property under test*, after selecting
  "the largest one" produced a false failure on correct output.

---

## ADR-A4 — Ship the Lao fonts, and install them on the server

**Status:** **implemented 2026-09-16** · **Fixed a live defect**

> **This ADR was wrong when first written, and rendering real PDFs corrected it.**
> The original text said to declare `@font-face` in the Print Format's `css` field.
> Measurement showed that breaks the PDF rather than fixing it. The reasoning below is
> what the renderer actually does, not what the CSS specification says it should.

### The defect

**The Lao Tax Invoice loaded no Lao font.** `app_include_css` reaches the Desk only —
`frappe/www/printview.py:get_print_style` assembles print CSS from `standard.css`, the
selected Print Style and the Print Format's own `css` field, and from nothing else. The
format's `css` was empty, its `font` field unset (so `get_font()` returned Inter), and its
HTML named `'Phetsarath'` against a font the print document never loaded.

### What measurement showed

Identical HTML through wkhtmltopdf 0.12.x, differing only by the `@font-face` block, with
the fonts installed on the machine in both runs:

| | Font embedded | Lao text extracted |
|---|---|---|
| **with `@font-face`** | DejaVuSans | `—` — destroyed |
| **without `@font-face`** | **Phetsarath-Regular** | `ໜຶ່ງລ້ານສອງແສນກີບຖ້ວນ` |
| without, and font not installed | DejaVuSans, DejaVuSerif | renders, marks reordered: `ໜຶງ່` |

Renderer: **wkhtmltopdf 0.12.6**, `--enable-local-file-access`, fonts installed on the
machine in the first two runs.

Three conclusions:

1. **On this stack, `@font-face` is not a usable font-delivery mechanism.** wkhtmltopdf
   is Qt WebKit and resolves fonts through **fontconfig**. This is a statement about the
   supported rendering path, **not** a universal claim about every wkhtmltopdf build —
   `@font-face` is reported to work for some fonts and fail for others across versions,
   file formats and platforms. That inconsistency is an additional reason not to make it
   part of the production contract, not a reason to doubt the measurement.
2. **Declaring `@font-face` is actively harmful here.** It overrides the fontconfig
   lookup, then fails, and the Lao text does not survive.
3. **A missing font does not give you boxes.** DejaVu covers the Lao block, so you get
   Lao that looks very nearly right with the combining marks stacked in the wrong order,
   on a document that still appears valid.

### Severity: document integrity, not typography

The third row is why this is not filed as a cosmetic defect:

```
font absent
→ fallback occurs
→ Lao remains visually plausible
→ combining-mark ordering is wrong
→ document may appear valid
```

For invoices, tax documents, contracts, receipts and financial statements this is a
**document integrity / regulatory presentation risk**. The operative consequence for the
whole system: **"characters rendered" is not a success criterion.**

### Decision

> **For server-generated bERP PDFs using the supported wkhtmltopdf rendering stack, Lao
> typography MUST NOT depend on CSS `@font-face`. The required Lao static font faces MUST
> be installed in the server font environment and resolvable through fontconfig. Print CSS
> MAY specify the corresponding `font-family`, but MUST NOT embed or override those Lao
> faces with `@font-face`.**

Desk and print are different rendering environments and get different answers:

| Surface | Font mechanism | Contract |
|---|---|---|
| Browser / Desk | web-font capable | `@font-face` permitted |
| Server PDF | wkhtmltopdf + system fonts | fontconfig-installed static faces |
| Print CSS | renderer-facing family declaration | `font-family: "Phetsarath", …` |
| Deployment | system dependency | install + `fc-cache` + verification |
| Runtime diagnostics | `font_status()` | observable, non-destructive |
| Migration / install | `after_migrate` warning | warn; never falsely declare failure |
| Acceptance | rendered PDF | structural evidence + human visual |

Frappe supports custom Print Format CSS, but its documentation does not make web-font
support a PDF correctness guarantee. **Valid Frappe CSS** and **supported production-PDF
font delivery** are therefore different contracts, and this ADR governs the second.

**1. The app ships the fonts** under `public/fonts/`, 332 KB, as the canonical copy:

| Family | Files | Source | Licence |
|---|---|---|---|
| Phetsarath | Regular, Bold | [`google/fonts` `ofl/phetsarath`](https://github.com/google/fonts/tree/main/ofl/phetsarath) | SIL OFL 1.1 |
| Noto Sans Lao | Regular, Bold | [`google/fonts` `ofl/notosanslao`](https://github.com/google/fonts/tree/main/ofl/notosanslao) | SIL OFL 1.1 |

Neither copyright notice declares a Reserved Font Name, so bundling is unrestricted.
`google/fonts` ships Noto Sans Lao only as a variable font and **wkhtmltopdf cannot render
variable fonts**, so the two statics were instanced from it with
`fontTools.varLib.instancer` — the same operation Google's own static builds perform. A
test fails if a variable font ever appears in `public/fonts/`.

Phetsarath leads every fallback chain because it is the official Lao government font
(*Copyright (c) 2010-2012, Ministry of Posts and Telecommunications, Laos*). It is also
the narrower of the two — **65 codepoints in the Lao block against Noto Sans Lao's 83** —
so Noto follows it everywhere as the wider net.

**2. `scripts/install-lao-fonts.sh` installs them into fontconfig.** A Frappe app cannot
install system fonts, so this is a deployment step and has to be run on **every machine
that renders PDFs**. It is idempotent, copies the OFL licences alongside the fonts as OFL
requires, and verifies with `fc-list` before reporting success.

**3. `berp_lao.lao_regional.fonts` reports whether it worked.** `font_status()` is
whitelisted — call it first when a tenant says an invoice looks wrong. A new
`after_migrate` hook warns at install time rather than letting this surface as a subtly
wrong invoice months later. When `fc-list` is unavailable the answer is "cannot tell", not
"broken", and it stays quiet.

**4. Eleven tests** in `tests/test_lao_fonts.py` pin all of it — including that the print
format declares **no** `@font-face`, that every shipped font has its OFL.txt, that none is
a variable font, and end-to-end that `get_print_style` writes the font onto the print body.

### Verified, and to what rung

`docs/REVIEW-METHOD.md` records the instrument ladder this sits on. Four different
questions, four different instruments:

| Assertion | Instrument | Status |
|---|---|---|
| **A.** the Unicode source string is correct | unit tests | ✅ |
| **B.** the expected font was resolved | `TestRendererCorrectness` in `tests/test_renderer_contract.py` | ✅ |
| **B′.** fontconfig's own answer for each family | `font_status()` `resolution` — **advisory only**, see below | ℹ️ |
| **C.** the expected font was embedded in the PDF | `pdffonts` on a rendered artifact | ✅ |
| **D.** glyph shaping / combining-mark placement is visually correct | **a person** | **OPEN** |

The real Lao Tax Invoice, rendered through Frappe's own `get_rendered_template` and
`get_print_style`, then wkhtmltopdf:

```
name                    type              emb sub uni
Phetsarath-Regular      CID TrueType      yes no  yes
Phetsarath-Bold         CID TrueType      yes no  yes
NotoSansLao-Regular     CID TrueType      yes no  yes
NotoSansLao-Bold        CID TrueType      yes no  yes
DejaVuSans / -Bold      CID TrueType      yes no  yes     ← the Latin text
```

**D is not closed and must not be reported as closed.** `pdftotext` drops combining
marks in extraction — the amount-in-words line comes out `ຫາແສນກີບຖວນ` where
`ຫ້າແສນກີບຖ້ວນ` was rendered. A PDF's text representation and the visual positioning of
its combining glyphs are related but not equivalent, so usable extracted Lao is
**supporting evidence only**. `BERP-LAO-VERIFY-001` carries the human-visual step and its
corpus.

### Consequences

- **Deployment gained a required step.** An install that skips
  `scripts/install-lao-fonts.sh` produces subtly wrong Lao. The script, the
  `after_migrate` warning and `font_status()` exist to make that hard to miss; the
  deploy script for `berp-linux` calls it.
- `public/fonts/` is **SIL OFL 1.1, not GPL-3.0**, and carries `FONT-PROVENANCE.md`
  recording upstream source, version, SHA-256 before and after transformation, the
  instancing command, and the regeneration recipe — so the 332 KB is reproducible rather
  than merely vendored. A test fails if a shipped font's hash stops matching that record.
- A print format that wants a different font sets its `font` field. It must not reach for
  `@font-face`, and a test now stops it.
- `font_status()` returns **READY / MISSING / UNKNOWN** with per-face evidence. UNKNOWN is
  never collapsed into MISSING: `fc-list` being unavailable is an unanswerable question,
  not a defect.
- **Upgrade path:** MTS Lao's [Phetsarath OT v4.103](https://fonts.mts.la/f/phetsarath-ot)
  has twelve styles, corrected Lao word-wrapping and Pali/Sanskrit letters this 2011 build
  lacks. Same family name, also OFL — a straight file replacement; update the hashes in
  `FONT-PROVENANCE.md` when it happens.

### Dependency risk — record it, do not act on it yet

The [wkhtmltopdf repository was archived in January 2023](https://github.com/wkhtmltopdf/wkhtmltopdf/issues/5160)
and is no longer maintained upstream. This ADR's entire contract is scoped to that
renderer's observed behaviour.

**This is not a reason to replace it now.** It is a reason to treat the PDF renderer as a
**pinned compatibility dependency** in the architecture risk register:

| | |
|---|---|
| Component | `wkhtmltopdf` 0.12.6 (Qt WebKit) |
| Upstream status | Archived January 2023; no further releases expected |
| What depends on it | Every statutory PDF this app produces, and ADR-A4's font contract |
| Risk | Security patches and OS-packaging drift; eventual removal from distributions |
| Mitigation now | Pin the version; keep `TestRendererCompatibilityCharacterization` pointed at the supported binary so a swap fails loudly |
| Trigger to revisit | Frappe changing its default PDF generator, or the binary leaving a target distribution |

If the renderer changes, **the font contract must be re-measured, not assumed to carry
over.** A Chromium-based generator would almost certainly honour `@font-face`, which would
make this ADR's constraint unnecessary rather than wrong.

That is why the `@font-face` assertion lives in its own class,
`TestRendererCompatibilityCharacterization`, rather than among the correctness tests. It
is a **compatibility characterization**: it records a measured property of the external
environment, not a requirement on this product. When a newer wkhtmltopdf makes it fail,
the correct reading is *environment changed → this ADR must be reconsidered*, not
*product regressed*. Amend this ADR with the new measurement first; only then update the
characterization to match. `docs/REVIEW-METHOD.md` carries the general rule.

**`fc-match` is not a substitute for rendering a PDF.** `font_status()` reports what
fontconfig hands back for each required family, but that reading is advisory and never
a verdict, because the two were measured to disagree: a strong-binding rule mapping
Phetsarath → DejaVu Sans made `fc-match "Phetsarath"` answer `DejaVu Sans` while
wkhtmltopdf, same environment and same `HOME`, still embedded `Phetsarath-Regular`.
Qt WebKit does not take fontconfig's pattern-matching path. A substitution reported by
`font_status()` therefore means *check `/etc/fonts/local.conf`*, not *this PDF is
broken*. REVIEW-METHOD Incident 3 records how that was found.

---

## ADR-A5 — Move the shell scripts out of the Python package

**Status:** **implemented 2026-09-16**

`berp_lao/setup/deploy_berp_online.sh` is a 42-line bench operations script living inside
the installed Python package, so it ships to every site. `docs/deploy-berp-lao-dev.sh` is
already outside the package. The repo is inconsistent with itself.

**Decision:** both moved to `scripts/` at the repo root, joining
`install-lao-fonts.sh`. None of them is app code.

---

## ADR-A6 — Give statutory reporting its own package *(when that work starts)*

**Status:** proposed, deferred

The P0 from `BERP-LAO-MARKET-001` is financial statements in the MoF's prescribed layout —
balance sheet, income statement, cash flow, notes, under LFRS for Non-PIEs (IFRS for SMEs
2009). That is a different concern from the VAT return and should not be filed under
`report/`.

```
lao_regional/statutory/
├── data/                 prescribed layouts as JSON, per the principle above
├── balance_sheet.py
├── income_statement.py
├── cash_flow.py
└── notes.py
```

Blocked on obtaining a prescribed template and an accountant's review of the chart. Do not
start this by guessing the layout.

---

## ADR-A7 — Split the tests to mirror the source *(alongside A1)*

**Status:** **implemented 2026-09-16**, alongside A1

`test_vat_return.py` is **710 lines and five classes**. More to the point,
`LaoVatReturnFixture` lives inside it, so anything needing a Lao company must be written
*into that file*. That is already shaping where tests go rather than where they belong.

**Decision:** extract the fixture to `tests/fixtures.py`, then split into
`test_sales_rules.py`, `test_purchase_rules.py`, `test_vat_return.py`, mirroring
`rules/`. Do it in the same change as A1, so the test layout and the source layout move
together.

---

## Two standing rules

### Config placement

BizEra.la is multi-tenant, one site per tenant. Write this down before it drifts:

| Scope | Where | Example |
|---|---|---|
| Tenant-wide | `site_config.json` | `berp_brand_name` (berp_whitelabel) |
| Per legal entity | Company custom field | `lao_not_vat_registered` |

One tenant may run several companies. Anything that varies between them is a Company
field, never site config.

### Keep `lao_numbers.py` framework-free

It imports exactly one thing from Frappe: `flt`. Splitting `set_lao_in_words` into the
hooks layer makes the module pure Python — which is what makes the num2words upstream
contribution possible, and what removes the deferred import noted in A1.

---

## What not to change

- **Do not split the Frappe module.** "Lao Regional" is a Desk workspace grouping, not an
  architectural boundary. Splitting it means DocType migrations for no user benefit.
- **Do not restructure the chart JSON.** It earned its current shape against the framework
  on 2026-09-15 — roots and split groups carry their class digit in the name because
  ERPNext enforces `account_number` uniqueness per company. That is load-bearing.
- **Do not add a `patches/` package yet.** `after_migrate` covers custom fields. Real
  patches are for *data* migrations — a chart renumbering — and not before.
- **Do not add a re-export shim for `utils.py`.** The app has no external consumers. (Done: `utils.py` is gone, not shimmed.)

---

## Sequence

```
A4 + A5        DONE 2026-09-16 — the font contract, measured
A1 + A2 + A7   DONE 2026-09-16 — utils split, fields to JSON, tests mirrored
A3             DONE 2026-09-16 — renamed to e_filing, and amended (see above)
A6             when the statutory template is in hand                 —
```

123 tests pass on a Frappe v15.120.1 + ERPNext v15 bench, one skipped by design.

A4 was the only item that fixed something broken, so it went first — and it turned out to
be the item whose stated design was wrong, which is an argument for implementing the
risky ADR early rather than last.

## What would change this plan

- An accountant rejecting the class 1 / class 4 root split — that is a chart rebuild and
  reorders everything.
- The E-Tax Invoice specification arriving, which promotes A3 from a rename to real work.
- A decision to publish `berp_lao` as an app other people install, which would make the
  `utils.py` removal in A1 a breaking change and require the shim it currently does not.

---

## Sources

Frappe print pipeline verified against the installed source at
`apps/frappe/frappe/www/printview.py` (`get_print_style`, `get_font`) on Frappe v15.120.1.

Fonts: [Phetsarath OT — LaoFonts / MTS Lao](https://fonts.mts.la/f/phetsarath-ot) ·
[Phetsarath on Google Fonts](https://fonts.google.com/specimen/Phetsarath) ·
[google/fonts `ofl/phetsarath`](https://github.com/google/fonts/tree/main/ofl/phetsarath)

Regulatory context: [`BERP-LAO-MARKET-001`](BERP-LAO-MARKET-001.md) ·
[`BERP-LAO-TAXRIS-001`](BERP-LAO-TAXRIS-001.md) ·
[`BERP-LAO-ROADMAP-001`](BERP-LAO-ROADMAP-001.md)
