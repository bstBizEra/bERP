# berp_lao — Lao PDR localisation for ERPNext

`berp_lao` adapts ERPNext to Lao PDR accounting and tax practice: the PCG
chart of accounts, VAT at 10%, the withholding-tax schedule, the 18-province /
148-district administrative hierarchy, and Lao-script typography and print
formats.

Part of the **bERP** suite by [BSTBizEra](https://github.com/bstBizEra).

| | |
|---|---|
| App name | `berp_lao` |
| Module | Lao Regional |
| Requires | Frappe + ERPNext v15 (v16 supported) |
| Licence | GPL-3.0 |

---

## What it provides

**Accounting**

- **Lao PCG Chart of Accounts** — the 8-class plan comptable prescribed under
  the Law on Accounting. 116 accounts across 10 roots, 82 of them postable,
  account numbers preserved on every postable account, bilingual Lao/English names.
- **VAT templates** — output 10%, export 0%, input 10%, wired to the PCG VAT
  accounts (4411 input / 4412 output), plus three **Item Tax Templates** (10%,
  0% export, exempt) so one invoice can mix treatments. The VAT return classifies
  **per line**, from the rate ERPNext actually applied — an invoice-level label
  over a mixed invoice makes the return fail to reconcile with itself.
- **Withholding tax, applied** — nine categories, each posting to its own PCG
  liability account (4431–4439). Rates are carried as *dated* rows, so the four
  that moved under Law No. 88/NA on 1 July 2026 apply from that date and invoices
  dated before it still withhold at the old rate. A Lao supplier carrying a
  category has `apply_tds` set on new purchase invoices, including those created
  through the API — ERPNext only does that on the Desk form path.

  Note `NO_DE_MINIMIS_THRESHOLD` in `setup/tax_templates.py` before editing a rate
  row: ERPNext treats `single_threshold = 0` as **never withhold**, not as *no
  threshold*, so Lao rates are seeded with a one-kip floor.
- **LAK currency format** — `1.000.000,00`, symbol ₭. This is both the CLDR
  `lo-LA` convention and the separator rule the Law on Accounting (amended)
  No. 46/NA imposes: Arabic figures, full stop for thousands, comma for
  decimals.

**Compliance**

- **Lao Monthly VAT Return** — a script report that reconciles output VAT
  against input VAT and states the net payable or claimable for the period.
- **Invoice validation** — warns when a Standard invoice carries no 10% VAT row,
  when an export/exempt invoice carries one anyway, when a service purchase has
  no WHT category, when an invoice at or above 500,000 LAK has no customer TIN on
  it, when a purchase above 1,000,000 LAK is settled in cash, which makes the
  expense non-deductible under Law No. 88/NA, and when input VAT is claimed more
  than three months after the supplier's invoice date, past the claim window.
  A company flagged **Not VAT Registered** — a micro-enterprise, which is 94.2% of
  Lao businesses by count — is exempted from the VAT checks entirely.
- **Custom fields** — 13 in all: Lao TIN, business registration and a
  micro-enterprise flag on Company,
  TIN and province/district on Customer and Supplier, and a Lao tax section with
  customer TIN and invoice type on Sales Invoice.

**Geography**

- `Lao Province` (18), `Lao District` (148) and `Lao Village` doctypes with
  bilingual names, codes and coordinates, loaded from fixtures at install.
- GeoJSON boundaries under `berp_lao/public/geo/` — country, provinces,
  districts (national and per-province), village points, plus roads, rivers,
  railway, SEZs, border checkpoints and power plants.

**Presentation**

- **Lao Tax Invoice** print format — bilingual Lao/English tax invoice and
  credit note.
- **Phetsarath and Noto Sans Lao ship with the app** (SIL OFL 1.1, 332 KB under
  `berp_lao/public/fonts/`, with `FONT-PROVENANCE.md` recording hashes and the build
  recipe). The Desk loads them by `@font-face`. **PDFs must not** — on the supported
  wkhtmltopdf stack the faces have to be resolvable through fontconfig, so
  **`scripts/install-lao-fonts.sh` runs on every machine that renders PDFs.**
  `berp_lao.lao_regional.fonts.font_status()` reports READY / MISSING / UNKNOWN. See
  [`docs/BERP-LAO-ARCH-001.md`](docs/BERP-LAO-ARCH-001.md) ADR-A4.
- **Lao UI translation** — `translations/lo.csv` covers every translatable string
  the app defines: validation messages, report sections, form buttons, and the
  DocType labels and select options.
- **Amounts in Lao words** — `lao_regional/lao_numbers.py`. Frappe's `in_words()`
  falls back to English for Lao, because num2words has no Lao, so an invoice would
  otherwise print its amount in English. Handles ສິບ/ຊາວ, the trailing ເອັດ, and the
  ລ້ານ-based reading above a million. Wants a native-speaker review.

**Compliance groundwork**

- **E-filing seam** — `lao_regional/e_filing/` builds and validates filing payloads from
  the same queries the VAT return report uses, behind an abstract transport. The
  default transport records and submits nothing: no specification is public. See
  [`docs/BERP-LAO-TAXRIS-001.md`](docs/BERP-LAO-TAXRIS-001.md).

---

## Before you deploy this in Laos

**Accounting software is a licensed product in Lao PDR.** The Ministry of Finance
licenses the *software*, through its Accounting Department, under Decision No. 1835/MOF
of 14 July 2020 (in force 28 July 2021). Only a licensed system's output is accepted for
statutory submission; a company may use anything it likes for internal bookkeeping.

`berp_lao` does **not** hold that licence. In practice that means it can be run today as
an operations and bookkeeping system, and the statutory pack must still be produced
through a licensed system or a licensed accounting firm.

It also means the app is **not finished for Lao statutory use**: the MoF prescribes the
chart of accounts and the financial statement layouts, and this app implements the chart
from secondary sources and does not implement the statements at all.

[`docs/BERP-LAO-MARKET-001.md`](docs/BERP-LAO-MARKET-001.md) sets out the licensing
regime, the accounting-standards framework (LFRS for Non-PIEs, based on IFRS for SMEs
2009), the state of Lao e-filing, and the competitive landscape — with what is
established, what is inferred, and what is not known.

---

## Installation

```bash
cd ~/frappe-bench
bench get-app https://github.com/bstBizEra/berp_lao_app
bench --site <your-site> install-app berp_lao
bench --site <your-site> migrate
bench build --app berp_lao
```

`bench get-app` reads the app name from `pyproject.toml`, so the checkout lands
in `apps/berp_lao/` regardless of the repository name.

Installation sets the LAK format, creates the custom fields and loads the
province and district masters. If the site already has a Lao company with no
posted transactions, the PCG chart and tax templates are applied to it
automatically.

### Setting up a company

The chart of accounts and tax templates are company-scoped, so for a company
created after installation, open it and use **Lao Tools**:

1. **Install Lao PCG Chart of Accounts** — replaces the company's chart. Refused
   outright once the company has General Ledger entries.
2. **Create Lao VAT / WHT Templates** — run this second; the templates resolve
   their account heads against the PCG accounts by number.

Both are also callable from a script or `bench execute`:

```bash
bench --site <site> execute \
  berp_lao.lao_regional.chart_of_accounts.lao_pcg.install_lao_chart_of_accounts \
  --kwargs "{'company': 'My Lao Co', 'force': 1}"

bench --site <site> execute \
  berp_lao.setup.tax_templates.install_lao_tax_templates \
  --kwargs "{'company': 'My Lao Co'}"
```

---

## Two decisions worth knowing about

### The PCG classes are split across ERPNext root types

The Lao PCG is class-based, and two of its classes straddle ERPNext's five root
types: class 1 mixes equity with long-term borrowings, and class 4 mixes
receivables and prepayments with payables, payroll and tax liabilities. ERPNext
applies the **root node's** `root_type` to its entire subtree — a `root_type` on
a nested node is ignored — so those two classes are emitted as two roots each:

| Root | `root_type` | Contents |
|---|---|---|
| 1 Capital & Reserves | Equity | 10–15 |
| 1 Non-Current Liabilities | Liability | 16 |
| 4 Third-Party Accounts — Assets | Asset | 41, 44 (4411), 48 (4811) |
| 4 Third-Party Accounts — Liabilities | Liability | 40, 43, 44 (4412–4439), 48 (4821) |

Groups 44 and 48 are split the same way, for the same reason.

**The class digit lives in the account name, not in `account_number`.** ERPNext
validates `account_number` uniqueness per *company*, not per root, so the four
numbers that appear on both sides of a split — 1, 4, 44, 48 — cannot be written to
`account_number` at all; chart creation aborts partway through and leaves a
half-built tree. ERPNext's own French PCG has the same problem and solves it by
setting no `account_number` anywhere and prefixing every name with its number.
This chart does that for exactly the nodes that collide: the ten roots and the four
split groups. **Every postable account keeps its number**, which is what the statute
and the tax templates depend on, and a test fails if that ever stops being true.

### Tax templates are not fixtures

`bench migrate` imports **every** JSON file under `berp_lao/fixtures/`, with
validation on. Tax templates cannot survive that: `Sales Taxes and Charges
Template` is company-scoped and its `account_head` resolves to a company-suffixed
account name, and `Tax Withholding Category` needs a per-company row in its
`accounts` table. So the definitions live in
`berp_lao/lao_regional/data/lao_tax_templates.json`, keyed by PCG **account
number**, and `berp_lao.setup.tax_templates` resolves them against a real
company. Only company-independent records belong in `fixtures/`.

---

## Layout

```
berp_lao/
├── hooks.py                     app metadata, doc_events, fixtures, assets
├── patches.txt
├── fixtures/                    imported verbatim by bench migrate
│   ├── lao_province.json        18 provinces
│   └── lao_district.json        148 districts
├── setup/
│   ├── install.py               after_install / before_uninstall
│   ├── tax_templates.py         per-company VAT + WHT templates
│   └── deploy_berp_online.sh
├── lao_regional/
│   ├── country.py               is this Lao? — resolved from ISO code "la"
│   ├── rules/                   one module per DocType the app hooks
│   │   ├── __init__.py          the statutory rates and thresholds
│   │   ├── sales_invoice.py
│   │   ├── purchase_invoice.py
│   │   └── company.py
│   ├── chart_of_accounts/
│   │   ├── lao_pcg.py           chart installer (whitelisted)
│   │   └── lao_pcg_chart_of_accounts.json
│   ├── data/
│   │   ├── lao_tax_templates.json
│   │   ├── lao_profit_tax.json  dated CIT rates, by regime
│   │   └── custom_fields.json   14 fields, validated against live DocType meta
│   ├── doctype/                 lao_province, lao_district, lao_village
│   ├── fonts.py                 Lao font availability (READY/MISSING/UNKNOWN)
│   ├── print_format/lao_tax_invoice/
│   ├── report/lao_vat_return/
│   ├── profit_tax.py            CIT estimate — standard 20%, microenterprise 5%
│   ├── certificates/            documents that leave the building
│   │   └── withholding.py       Lao withholding certificate (bilingual, printable)
│   └── e_filing/                DTax + E-Tax Invoice seams, both inert
│       ├── vat_return.py        periodic VAT filing payload
│       ├── e_invoice.py         one tax invoice, with its statutory check()
│       └── client.py            abstract transports + recording default
├── public/
│   ├── css/berp_lao.bundle.css  Desk bundle entry point
│   ├── js/                      Company and Sales Invoice form scripts
│   └── geo/                     GeoJSON boundary and feature layers
├── translations/lo.csv          Lao UI strings
└── tests/
```

---

## Development

```bash
# lint
ruff check berp_lao && ruff format --check berp_lao

# tests
bench --site <site> set-config allow_tests true
bench --site <site> run-tests --app berp_lao
```

91 tests, in five groups:

- `tests/test_lao_regional.py` — 26 tests, mostly data integrity that touches no
  database:
  chart structure, tax-template/chart agreement, fixture link integrity, hook
  resolution, report shape. These catch the failure this app is most exposed to,
  a JSON file drifting out of step with the code that reads it.
- `tests/fixtures.py` — the Lao company every integration test posts against. Builds
  it from nothing: item groups, territories, UOM, price lists, fiscal year, then
  replaces the chart and posts invoices. Extracted from `test_vat_return.py`, where
  it used to force unrelated tests into a 710-line file.
- `tests/test_vat_return.py`, `test_company_setup.py`, `test_sales_rules.py`,
  `test_purchase_rules.py` — the integration suites, split to mirror the source.
  `test_purchase_rules.py` carries the withholding-tax suite: the withheld amount,
  the reduced payable, the credit landing in PCG 4431, the ledger balancing, and
  the dated rate — an invoice dated before 1 July 2026 withholds 5%, not 10%.
  `test_company_setup.py` also validates `custom_fields.json` against the live
  DocType meta: every `insert_after` names a field that exists, every `Link` option
  names a real DocType, every `fieldtype` is one this Frappe has.
- `tests/test_invoice_numbering.py` — 12 tests on per-company invoice numbering,
  including the defect reproduced with two real companies: with the flag off, one
  company's invoice numbers differ by 2 because a sibling took the number in between.
- `tests/test_client_scripts.py` — 10 tests that ask the *server* about the Desk form
  scripts: every dotted method they call resolves and is whitelisted, every field they
  read exists, every `frappe.boot` key they read is published. A form script calls the
  server by **string**, so a rename breaks the button while every test stays green.
- `tests/test_profit_tax.py` — 20 tests on the CIT estimate, including that our
  ledger aggregation agrees with ERPNext's own Profit and Loss Statement, and that a
  microenterprise period before 1 July 2026 reports **no rate in force** rather than a
  rate of zero.
- `tests/test_withholding_certificate.py` — 14 tests on the supplier certificate,
  including that it declares **no** `@font-face` (ADR-A4, carried into the second Lao
  document this app prints) and a characterization pinning an upstream ERPNext defect:
  `Tax Withholding Details` raises a SQL error when `party` is a list.
- `tests/test_e_filing.py` — 16 tests on the filing seams. The one that matters is
  `test_an_unconfigured_transport_is_never_live`: anything not explicitly configured
  must resolve to the inert recorder, so a misspelt config key cannot submit to a tax
  authority.
- `tests/test_lao_numbers.py` — 18 tests pinning every irregularity in the Lao
  numeral system, so a refactor of `lao_numbers.py` cannot quietly change how an
  invoice reads.
- `tests/test_lao_fonts.py` — 23 tests on typography: that the shipped fonts carry
  their OFL licences and match the SHA-256s in `FONT-PROVENANCE.md`, that none is a
  variable font, and that the print format declares **no** `@font-face`. The last
  seven put the font *diagnostic* under test rather than the fonts — including that
  it can produce a negative at all, and that a fontconfig substitution is reported
  without being promoted to a failure.
- `tests/test_renderer_contract.py` — 5 tests that launch the real `wkhtmltopdf` and
  assert on the fonts actually embedded in a rendered PDF. This is the instrument that
  was missing when a green suite certified a broken invoice; see
  [`docs/REVIEW-METHOD.md`](docs/REVIEW-METHOD.md). They are two suites, deliberately
  named apart:
  - `TestRendererCorrectness` (4) — every required glyph resolves through the
    approved fallback chain. **Red means the product is broken.**
  - `TestRendererCompatibilityCharacterization` (1) — pins the measured behaviour of
    the supported renderer that ADR-A4 rests on. **Red means the environment changed
    and the ADR must be reconsidered** — do not "fix" the product to make it green.

Everything this app still needs from a person is consolidated in
[`docs/BERP-LAO-QUESTIONS-001.md`](docs/BERP-LAO-QUESTIONS-001.md) — eleven questions across
four counterparties, each with what is already established, from which source, and what the
app does with every possible answer.

CI (`.github/workflows/ci.yml`) runs lint and tests against a real Frappe + ERPNext
v15 bench. It triggers on **pull requests** and on pushes to `main` — not on a push
to a feature branch, so opening the PR is what starts the first run. `workflow_dispatch`
is declared but GitHub only offers it for workflows already on the default branch.

### Adding to the chart of accounts

`lao_pcg_chart_of_accounts.json` is the source of truth. Keep every account
number unique within its root, put `root_type` only on root nodes, and give leaf
accounts an explicit `account_type` where ERPNext depends on one (`Receivable`,
`Payable`, `Bank`, `Cash`, `Stock`, `Tax`, `Fixed Asset`, `Accumulated
Depreciation`, `Cost of Goods Sold`, `Depreciation`). The test suite enforces the
first two and checks that every account number referenced by a tax template
exists as a leaf.

---

## Status

**Verified on a bench.** Frappe v15.120.1 + ERPNext v15 on MariaDB 10.11: the app
installs, creates its 13 custom fields, loads 18 provinces and 148 districts, sets
the LAK format, builds the PCG chart and tax templates for a Lao company, posts
sales and purchase invoices, produces the VAT return, and renders a Lao Tax Invoice to
PDF with Phetsarath embedded and Pali text falling through to Noto Sans Lao.
**91 tests pass**, one skips by design.

What is **not** closed: whether Lao combining marks are placed correctly on the page.
Text extraction drops them, so that needs a person — see
[`docs/BERP-LAO-VERIFY-001.md`](docs/BERP-LAO-VERIFY-001.md) step 9, which is open.

That first run found six defects, four of which no static analysis could have
found — including that the app matched the company's country against the literal
string `"Laos"`, which is not what Frappe calls Lao PDR, so every document hook in
the app was dead code. See the commit *Fix six defects a real bench found on the
first run*, and `docs/BERP-LAO-VERIFY-001.md` for what remains to be checked by
hand.

Known gaps:

- The bench above was a throwaway built to close the gate. **CI has still never
  run**, and the app has not been exercised through the Desk UI — the client
  scripts and the print format are checked by reading, not by clicking.
- `translations/lo.csv` was machine-generated and wants a native-speaker review.
- TaxRIS is a seam, not an integration — and it is aimed at the wrong system; see
  [`docs/BERP-LAO-MARKET-001.md`](docs/BERP-LAO-MARKET-001.md) §3.
- Statutory financial statements in the MoF's prescribed layout are **not built**. The
  app reconciles VAT; it does not yet produce a fileable Lao statutory pack.
- The Lao PCG chart reflects Law 47/NA 2013 as read from secondary sources; a
  Lao-qualified accountant should confirm it before it carries real books.

---

## Roadmap

| Priority | Item | Status |
|---|---|---|
| P2 | `lo.csv` Lao UI translation | Done — 83 strings; wants a native-speaker review |
| — | Ship the Lao fonts | **Done** — and it fixed a live defect. See [`docs/BERP-LAO-ARCH-001.md`](docs/BERP-LAO-ARCH-001.md) ADR-A4 |
| P0 | Lao statutory financial statements in the MoF's prescribed layout | Not started — the highest-value missing piece. See [`docs/BERP-LAO-MARKET-001.md`](docs/BERP-LAO-MARKET-001.md) |
| P1 | Input VAT 3-month claim window | Done — warns on a claim past the window, measured from the supplier's invoice date |
| P2 | E-Tax Invoice integration | Interfaces only. The Lao E-Tax Invoice system launched 29 May 2026 and is integrable; blocked on obtaining its specification, not on whether one exists |
| P2 | NSSF payroll integration | Not started |
| P3 | VAT deadline reminders | Scheduler hook stubbed in `hooks.py` |

---

## Tax reference

| Item | Rate | PCG account | Basis |
|---|---|---|---|
| VAT, standard | 10% | 4412 / 4411 | Presidential Decree 003/PS, effective 1 May 2024 |
| VAT, exports | 0% | 4412 | Zero-rated |
| WHT, commissions, consultancy & service fees | 5% → **10%** from 1 Jul 2026 | 4431 | Law 88/NA |
| WHT, dividends & interest | 10% | 4432 | Law 88/NA |
| WHT, lease of assets | 10% | 4433 | Law 88/NA |
| WHT, teaching & research | 5% | 4434 | Law 88/NA |
| WHT, royalties | 5% | 4435 | Law 88/NA |
| WHT, share transfer | 2% | 4436 | Law 88/NA |
| WHT, construction & repair | 2% → **5%** from 1 Jul 2026 | 4437 | Law 88/NA |
| WHT, online sales | 2% → **10%** from 1 Jul 2026 | 4438 | Law 88/NA |
| WHT, sports & performing arts | 10% → **5%** from 1 Jul 2026 | 4439 | Law 88/NA |
| Customer TIN required from | 500,000 LAK | — | Lao Revenue Department |
| Expense deductible only if bank-settled, from | 1,000,000 LAK per invoice | — | Law 88/NA |
| Input VAT claim window | 3 months from the date incurred | — | VAT Law |
| Annual financial statements due | 31 March | — | Decision 137/VTE, 13 Feb 2024 |
| Fiscal year | Jan–Dec | — | Decision 137/VTE |

**Law on Income Tax No. 88/NA** was gazetted on 19 June 2026 and took effect on
1 July 2026, replacing the 2019 Income Tax Law. It moved four withholding rates at
once, which is why every category carries dated rows. PwC's Worldwide Tax Summaries
for Lao PDR (reviewed 7 August 2026) still shows the pre-88/NA figures for
consultancy and for artists and athletes; where the two disagree this app follows
88/NA. None of this is a substitute for advice from a Lao-qualified accountant.

Rates are encoded as data, not scattered through the code:
`lao_regional/data/lao_tax_templates.json` for the templates, and the constants at
the top of `lao_regional/rules/__init__.py` and the VAT report. A statutory change is a new
dated row in that file, never an edit to an existing one — otherwise the old rate
is lost and invoices predating the change are withheld at the wrong rate.

---

## Licence

GNU General Public License v3. See [`license.txt`](license.txt).
