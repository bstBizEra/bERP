# BERP-LAO-VERIFY-001 — First-run verification on a live bench

**Status:** **OPEN — HUMAN-VISUAL-EVIDENCE-REQUIRED.** The automated half is done
(84 tests pass, and `tests/test_renderer_contract.py` proves the Lao fonts are embedded in
a rendered PDF). Step 9 is what remains, and no test can close it.
**Applies to:** `berp_lao` on branch `feat/installable-app-lao-pcg-vat`
**Target:** `dev.bizera.localhost` (or `dev.berp.bizera.la`)

---

## Why this document exists

Every claim made about `berp_lao` so far rests on static analysis: linting, JSON
validation, hook-path resolution, and tests that have never been executed. Nothing
in this app has run against a Frappe bench.

This runbook is the first execution. Work through it in order and record the result
of each check — a failure here is expected and useful, not a setback.

**Do not run this on a site holding real books.** Step 4 replaces a company's Chart
of Accounts.

---

## 0. Prerequisites

```bash
cd ~/frappe-bench
bench version                      # Frappe and ERPNext, expect v15.x
bench --site dev.bizera.localhost list-apps
```

| Need | Why |
|---|---|
| Frappe + ERPNext v15 | `required_apps = ["frappe/erpnext"]` |
| A site you can destroy | Step 4 is destructive to the chart |
| Node 18+ | `bench build` |

> If this is a scratch site, create it fresh — it makes step 8 (uninstall) meaningful.
> `bench new-site dev.bizera.localhost --install-app erpnext`

---

## 1. Install

```bash
bench get-app https://github.com/bstBizEra/berp_lao_app
bench --site dev.bizera.localhost install-app berp_lao
bench --site dev.bizera.localhost migrate
bench build --app berp_lao
```

| # | Check | Expected |
|---|---|---|
| 1.1 | `bench get-app` completes | Checkout lands in `apps/berp_lao/`, **not** `apps/berp_lao_app/` — the name comes from `pyproject.toml` |
| 1.2 | `install-app` completes with no traceback | The `app_name` fix is what this proves |
| 1.3 | `migrate` completes | Proves tax templates are not being imported from `fixtures/` |
| 1.4 | `bench build --app berp_lao` completes | Proves `berp_lao.bundle.css` resolves |

```bash
# 1.5 — geography masters loaded
bench --site dev.bizera.localhost execute frappe.client.get_count \
  --kwargs "{'doctype': 'Lao Province'}"          # expect 18
bench --site dev.bizera.localhost execute frappe.client.get_count \
  --kwargs "{'doctype': 'Lao District'}"          # expect 148

# 1.6 — custom fields created
bench --site dev.bizera.localhost execute frappe.client.get_count \
  --kwargs "{'doctype': 'Custom Field', 'filters': {'module': 'Lao Regional'}}"   # expect 12

# 1.7 — LAK formatted to lo-LA
bench --site dev.bizera.localhost execute frappe.client.get_value \
  --kwargs "{'doctype': 'Currency', 'filters': {'name': 'LAK'}, 'fieldname': ['number_format', 'symbol']}"
# expect {'number_format': '#.###,##', 'symbol': '₭'}
```

---

## 2. Run the test suite

```bash
bench --site dev.bizera.localhost set-config allow_tests true
bench --site dev.bizera.localhost run-tests --app berp_lao
```

36 tests. Record failures verbatim — the integration tests build a company and post
invoices, and that is the path most likely to surprise.

---

## 3. Create a test company

Desk → Company → New.

| Field | Value |
|---|---|
| Company Name | Lao Verify Co |
| Abbreviation | LVC |
| Country | Laos |
| Default Currency | LAK |

| # | Check | Expected |
|---|---|---|
| 3.1 | On saving with Country = Laos | Currency is set to LAK automatically |
| 3.2 | After reload | A **Lao Tools** button group appears |
| 3.3 | Dashboard | Indicator "Lao Localisation Active" |
| 3.4 | `lao_tax_id` field | Present and marked required |

Set a Lao Tax ID — step 7 needs it.

---

## 4. Install the PCG chart

**Lao Tools → Install Lao PCG Chart of Accounts.** Confirm the prompt.

| # | Check | Expected |
|---|---|---|
| 4.1 | Completes without traceback | |
| 4.2 | Chart of Accounts tree | Ten roots. Two numbered **1**, two numbered **4** — this is the class split, not a bug |
| 4.3 | Account count | 113 accounts |
| 4.4 | `4111 Trade Debtors - Local` | `account_type` = Receivable |
| 4.5 | `4011 Trade Creditors - Local` | `account_type` = Payable |
| 4.6 | Company → Accounts Settings | Default Receivable = `4111 - …`, Default Payable = `4011 - …`, Default Income = `7011 - …`, Default Expense = `6011 - …` |

4.6 is the defect found while writing the tests: the chart replacement used to leave
these pointing at deleted accounts.

```bash
# 4.7 — refuses once GL entries exist. Run this AFTER step 6 and expect it to throw.
bench --site dev.bizera.localhost execute \
  berp_lao.lao_regional.chart_of_accounts.lao_pcg.install_lao_chart_of_accounts \
  --kwargs "{'company': 'Lao Verify Co', 'force': 1}"
```

---

## 5. Create the tax templates

**Lao Tools → Create Lao VAT / WHT Templates.**

| # | Check | Expected |
|---|---|---|
| 5.1 | Message reports templates created | No "PCG accounts were not found" warning |
| 5.2 | Sales Taxes and Charges Template | `VAT 10% (ອາກອນ 10%) - LVC` exists, is default, account head `4412 - …` |
| 5.3 | Purchase template | `VAT 10% Input (ອາກອນ VAT ຊື້) - LVC`, account head `4411 - …` |
| 5.4 | Tax Withholding Category | 8 categories, each with an accounts row for Lao Verify Co |
| 5.5 | `WHT - Construction & Repair 5%` | **Two** rate rows: 2% to 2026-06-30, then 5% from 2026-07-01 |
| 5.6 | Re-run the button | Reports everything skipped, creates nothing (idempotent) |

---

## 6. Post the VAT scenario

Create a non-stock Item (`is_stock_item = 0`), a Customer and a Supplier, then post
and **submit**:

| Doc | Invoice Type | Net (LAK) | Taxes |
|---|---|---|---|
| SI-1 | Standard | 1,000,000 | VAT 10% |
| SI-2 | Standard | 200,000 | VAT 10% **and** an Actual charge of 50,000 to `6241 Transport & Delivery` |
| SI-3 | Export (0%) | 500,000 | VAT row at rate 0 |
| PI-1 | — | 400,000 | VAT 10% Input |

| # | Check | Expected |
|---|---|---|
| 6.1 | SI with type Standard and no VAT row | Orange warning naming the missing 10% row |
| 6.2 | SI-3 (export) with no VAT | **No** VAT warning |
| 6.3 | SI ≥ 500,000 LAK with no customer TIN | Warning about the Tax ID |
| 6.4 | Purchase Invoice of a service item, no WHT category | Blue WHT notice |
| 6.5 | All four submit cleanly | |

---

## 7. The VAT return — the decisive check

Desk → **Lao Monthly VAT Return**. Company = Lao Verify Co, period covering the
postings.

| Row | Expected |
|---|---|
| 1. Standard domestic sales | Net **1,200,000**, 2 invoices |
| 2. Export sales, zero-rated | Net **500,000**, VAT 0, 1 invoice |
| 3. VAT-exempt sales | 0 |
| **4. Total output VAT** | **120,000** |
| 5. Purchases eligible for input VAT | Net 400,000 |
| 6. Total input VAT | 40,000 |
| 7. Net VAT payable | **80,000** |

**If row 4 reads 170,000, the report is summing the freight line as VAT** — that is
the original defect, and it means the fix did not take. This single number is the
most important check in this document.

| # | Check | Expected |
|---|---|---|
| 7.1 | Row 4 | 120,000, not 170,000 |
| 7.2 | No total row at the bottom | `add_total_row` is 0; a total would double-count row 7 |
| 7.3 | Summary tiles | Output VAT, Input VAT, Net VAT Payable (red) |
| 7.4 | Run against a non-Lao company | Throws, naming the country |
| 7.5 | Period before the postings | All zeros |

```bash
# 7.6 — the TaxRIS payload must agree with the report, and submit nothing
bench --site dev.bizera.localhost execute \
  berp_lao.lao_regional.e_filing.client.preview_vat_return \
  --kwargs "{'company': 'Lao Verify Co', 'from_date': '2026-09-01', 'to_date': '2026-09-30'}"
# expect total_output_vat 120000, net_vat_payable 80000,
#        transport "...RecordingClient", is_live False
```

---

## 8. Print format, translation, uninstall

| # | Check | Expected |
|---|---|---|
| 8.1 | Print SI-1 with **Lao Tax Invoice** | Bilingual headings, Lao script renders (not boxes), company TIN shown |
| 8.2 | Print SI-3 | States the export/zero-rated note |
| 8.3 | Print a credit note | Title reads ໃບຫຼຸດໜີ້ / Credit Note |
| 8.4 | Set user language to Lao | Report sections and form buttons appear in Lao |
| 8.5 | `bench --site … uninstall-app berp_lao` | Removes the 12 custom fields, leaves ERPNext data intact |

Step 8.4 is where a native speaker should look at `translations/lo.csv` in situ.

---

## 9. Lao shaping — the step that stays with a person

**This is the open item.** Everything above can be automated and most of it now is. This
cannot.

### Why extraction is not enough

Four separate assertions hide behind "the Lao renders correctly":

```
A. the Unicode source string is correct          → unit tests cover this
B. the expected font was resolved                → renderer contract test covers this
C. the expected font was embedded in the PDF     → pdffonts covers this
D. glyph shaping and combining-mark placement    → THIS STEP
```

A PDF's text representation and the visual positioning of its combining glyphs are
related but not equivalent. `pdftotext` returning usable Lao does **not** prove a glyph
was positioned correctly on the page — it drops combining marks in extraction, so the
amount-in-words line comes back `ຫາແສນກີບຖວນ` where `ຫ້າແສນກີບຖ້ວນ` was rendered.

And the failure mode is not a missing glyph. A fallback font that covers the Lao block
renders text that is **visually plausible with the marks in the wrong order** — `ໜຶງ່`
for `ໜຶ່ງ`. The document still looks valid. See `REVIEW-METHOD.md` on why this is
classified as document integrity risk rather than typography.

### Before you start

```bash
bench --site <site> execute berp_lao.lao_regional.fonts.font_status
```

Expect `"status": "ready"`. If it says `missing`, run
`sudo bash scripts/install-lao-fonts.sh` on **this** machine and `bench restart`. If it
says `unknown`, fontconfig could not be queried from here — check on the machine that
actually renders PDFs, and do not proceed on the assumption that it is fine.

`resolution_status` and `substituted` sit beside the verdict and are **advisory**.
`"resolution_status": "substituted"` means a fontconfig rule on this machine is
redirecting one of the families — worth chasing in `/etc/fonts/local.conf` if the PDF
turns out wrong, but measured *not* to stop wkhtmltopdf embedding the right face, so it
is not by itself a reason to stop. `"probe_validated": false` means that reporting
carries no information at all; the `status` verdict above is unaffected.

### The verification corpus

Print a Lao Tax Invoice to PDF and check each of these **on screen at 200% or more**,
against a reference — a Lao colleague, or an existing invoice from a Lao accountant.
These are chosen because each combines a consonant with a vowel and a tone mark, which is
exactly what a fallback font reorders.

| Expected | Reading | What a wrong render looks like |
|---|---|---|
| ໜຶ່ງ | one | `ໜຶງ່` — the tone mark lands after the final consonant |
| ເກົ່າ | nine | the circle mark and tone mark swap or collide |
| ໃໝ່ | new | the vowel sign detaches from its consonant |
| ຖ້ວນ | exactly | `ຖວນ` — the tone mark disappears or displaces |
| ລ້ານ | million | as above |
| ກີບ | kip | vowel sign sits at the wrong height |
| ໜຶ່ງລ້ານສອງແສນກີບຖ້ວນ | 1,200,000 kip exactly | any of the above, in sequence |

Then check the same in real invoice fields, where the text is surrounded by table
borders and Latin script:

- [ ] the invoice title — `ໃບເກັບເງິນອາກອນ`
- [ ] every bilingual field label, e.g. `ສະກຸນເງິນ / Currency`
- [ ] the customer name, if it is in Lao
- [ ] item descriptions in Lao
- [ ] **the amount in words** — the output of `lao_numbers.py`, and the longest
      unbroken Lao string on the document
- [ ] the invoice type — `ປະເພດ`
- [ ] any Lao text that wraps across a line break

### Record the result

Attach the PDF to the session log entry. If a reviewer who reads Lao has signed off,
record who and when — that signature is the evidence, not the test suite.

- [ ] PDF generated from a real Sales Invoice, not a fixture page
- [ ] Every corpus phrase checked at magnification
- [ ] Line-wrapped Lao checked
- [ ] Reviewed by someone who reads Lao: ____________________  date: __________

Until that last line is filled in, this document stays **OPEN** and the app should not be
described as verified for statutory output.

---

## Result

| Step | Pass | Notes |
|---|---|---|
| 1 Install | ☐ | |
| 2 Tests | ☐ | |
| 3 Company | ☐ | |
| 4 Chart | ☐ | |
| 5 Templates | ☐ | |
| 6 Postings | ☐ | |
| 7 VAT return | ☐ | |
| 8 Presentation | ☐ | |

Record the outcome as a `docs/SESSION-LOG.md` entry, and update the Status section of
the README — it currently says the app is unverified, and that should stop being true
once this passes.
