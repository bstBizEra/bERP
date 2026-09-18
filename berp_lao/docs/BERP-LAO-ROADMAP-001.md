# BERP-LAO-ROADMAP-001 — Development plan

**Date:** 2026-09-15
**State at writing:** branch `feat/installable-app-lao-pcg-vat` published at `5cc3387`
(six commits locally, one unpushed). No CI run. No bench run. No PR.

---

## The shape of the problem

`berp_lao` is **installable**. It is not yet **usable for real Lao books**, and the
distance between those two is the whole plan. Two gaps below were found by reading
the code against the framework rather than by running it, and both would surface on
the very first real invoice.

Phases are sequential. Phase 0 is a gate: until it closes, every claim about this app
is static analysis, and building on top of unverified foundations is how a small
defect becomes an expensive one.

---

## Phase 0 — Prove it runs *(gate)*

**The gate is open.** On 2026-09-15 the app was installed and the suite run on a
real bench — Frappe v15.120.1 + ERPNext v15 on MariaDB 10.11, built in the cloud
workspace because CI was still blocked behind an unopened PR. **62 tests pass, one
skips by design.** The first run found six defects; see the commit *Fix six defects
a real bench found on the first run*.

| # | Task | Status |
|---|---|---|
| 0.1 | Open the PR | **Not done.** Still the only way to start CI, and the only way anyone but this session sees a green run. |
| 0.2 | First execution of the code | **Done** — on a throwaway bench, not CI. |
| 0.3 | Fix what it reports | **Done** — six defects, listed below. |
| 0.4 | Run `BERP-LAO-VERIFY-001` end to end | **Partly, and now narrower.** `tests/test_client_scripts.py` (added 2026-09-17) closes the silent half mechanically: every dotted server method a form script calls resolves **and** is whitelisted, every field it reads exists on the DocType it is bound to, every `frappe.boot` key it reads is actually published, and no script hardcodes a country name. A form script calls the server by *string*, so a rename breaks the button with nothing failing anywhere — this app renamed a package two commits earlier. Validated against the known-bad: a renamed module and a removed `@frappe.whitelist()` each fail it with the right message. **What still needs a person:** whether the buttons render, are placed sensibly, and are reachable by a user with the right role. Run on `berp-linux` / `dev.berp.bizera.la`. |
| 0.5 | Fix what the bench reports | **Done.** |
| 0.6 | Update the README Status section | **Done.** |

### What the bench found

Four of these six could not have been found by reading the code.

1. **The country was never matched.** `is_lao_company` compared against the literal
   `"Laos"`. Frappe's Country record is `Lao Peoples Democratic Republic`; nothing
   is named `Laos`. **Every doc_event in the app was dead code** and the VAT
   report's guard would have rejected every real Lao company. Nine call sites,
   three of them client-side. Now resolved from ISO code `la`.
2. **The chart could not install.** `Account.validate_account_number` enforces
   uniqueness per company, so the four numbers shared across the class 1 / class 4
   splits aborted creation partway through. Fixed the way ERPNext's French PCG
   does it — class digit in the name, no `account_number` on the colliding nodes.
3. **`Stock In Hand` and `Bank Charge` are not valid account types in v15.** They
   were in v13/v14.
4. **A Purchase Invoice could not be saved at all** without
   `stock_received_but_not_billed` on the Company, for any item. The chart had no
   such account.
5. **Company defaults landed on the wrong accounts** — `default_receivable_account`
   resolved to *Foreign* trade debtors, because the lookup was by `account_type`
   and two accounts share it, so row order decided.
6. **Writing a Company field ERPNext does not have is a raw SQL error**, not a
   validation.

**Exit criterion:** a green CI run on the PR, plus the Desk-UI half of
`BERP-LAO-VERIFY-001` on `dev.berp.bizera.la`.

---

## Phase 1 — Fit for real books

Five items. The first two are verified defects, not speculation.

### 1.1 Amount in words is English — no Lao support exists *(verified — **done**)*

The Lao Tax Invoice print format renders `doc.in_words`. Frappe's `in_words()` calls
`num2words(integer, lang=frappe.local.lang)` and falls back to English on
`NotImplementedError`.

Checked against num2words: **56 languages, Lao is not among them.** Thai and
Vietnamese are; `lo` raises `NotImplementedError`.

```
num2words(1200000, lang='lo')  ->  NotImplementedError
num2words(1200000, lang='en')  ->  one million, two hundred thousand
```

So a Lao statutory tax invoice currently prints its amount in words **in English**.
A Lao invoice is normally expected to carry the figure in Lao script.

**Work:** implement Lao numeral-to-words in `lao_regional/` (ສູນ ໜຶ່ງ ສອງ … ພັນ ໝື່ນ
ແສນ ລ້ານ), override the invoice's `in_words` for Lao companies, and test it against a
table of known values. Consider upstreaming to num2words afterwards.

**Done 2026-09-15** — `lao_regional/lao_numbers.py`, wired to Sales Invoice
`validate`. 18 tests pin every irregularity explicitly so a reviewer can correct a
reading and see exactly what changes. Writing the tests caught a real bug: the ເອັດ
rule is about the whole number, not the six-digit group, so 1,000,001 was reading
ໜຶ່ງລ້ານໜຶ່ງ instead of ໜຶ່ງລ້ານເອັດ.

**Still open:** a native speaker must review the readings. The code is written from
the structure of the system, which follows Thai closely, but that is not the same as
being confirmed. Consider upstreaming Lao to num2words afterwards (§4.3).

### 1.2 Withholding tax is warned about, never applied — **DONE 2026-09-16**

The app created nine `Tax Withholding Category` records with correct dated rates and
correct PCG accounts, and **not one of them could withhold anything**. Two independent
reasons, neither of which produced an error:

**1. `single_threshold = 0` means "never withhold", not "no threshold".**
ERPNext's `get_tds_amount` guards the whole calculation on

```python
if (threshold and tax_withholding_net_total >= threshold) or cumulative_threshold_breached:
```

and `0` is falsy. Lao WHT has no de-minimis — the rate applies to the whole payment —
so the app seeded 0, meaning *no floor*, and ERPNext read it as *never*. Measured on
this stack, one invoice, net 1,000,000 LAK, Services at 10%, everything else identical:

```
single_threshold = 0    withheld           0    grand total  1,000,000
single_threshold = 1    withheld     100,000    grand total    900,000
```

Fixed by seeding `NO_DE_MINIMIS_THRESHOLD = 1` — one kip — with the reasoning recorded
next to it, and `repair_withholding_thresholds()` on `after_migrate` for sites that
already carry the inert copies. Verified end to end: 13 inert rate rows before
`bench migrate`, 0 after.

**2. `apply_tds` is never set on a scripted insert.** `PurchaseInvoice.set_missing_values`
copies the supplier's category and sets `apply_tds = 1` only when `for_validate=False`,
which is the **form** path — hence `purchase_invoice.js` reading `__onload.supplier_tds`.
A Purchase Invoice created through the API, an import or a test goes through `validate()`,
which passes `for_validate=True`, and the block is skipped. Measured: such an invoice came
back with `apply_tds = 0`, no tax row and no WHT ledger entry.

Fixed with `apply_lao_withholding_defaults` on `before_validate` — before ERPNext's own
`set_tax_withholding`, and only on a new document, because unticking `apply_tds` in the
Desk clears the category too and a rule that fired on every save would put both back.

**Ten integration tests** now cover it: the withheld amount, the reduced payable, the
credit landing in PCG 4431, the ledger balancing, a supplier with no category withholding
nothing, a non-Lao company being left alone, the dated rate (an invoice dated before
1 July 2026 withholds 5%, not 10%), and the repair being idempotent.

One ERPNext behaviour worth knowing: withholding is **period-cumulative**. `get_tds_amount`
sums every invoice for the party inside the rate row's date window and deducts what was
already withheld. The first version of these tests shared one supplier and got 200,000 on
a 1,000,000 invoice; each test now creates its own supplier.

### 1.3 Accountant sign-off on the PCG chart

113 accounts built from your `docs/` template plus a reading of the class structure.
The class 1 and class 4 root splits change the shape of the statutory tree to fit
ERPNext. Someone Lao-qualified should confirm that before it carries books.

### 1.4 Native-speaker review of `lo.csv`

83 machine-generated strings. Accounting terminology is exactly where this goes
subtly wrong. Review in situ (step 8.4 of the verification runbook), not as a
spreadsheet.

### 1.5 Input VAT claim window

PwC records that Lao input VAT can be claimed within three months of being incurred.
The VAT return claims all input VAT posted in the period, with no view of what was
carried forward or what has expired. Confirm the rule with an accountant, then decide
whether the report models it or simply documents that it does not.

---

## Phase 1b — What the market research changed *(added 2026-09-15)*

`BERP-LAO-MARKET-001` established three things that reorder the plan. Full reasoning
is in that document; the actionable residue is here.

| # | Task | Notes |
|---|---|---|
| 1b.1 | **Lao statutory financial statements** in the MoF's prescribed layout — balance sheet, income statement, cash flow, notes, per LFRS for Non-PIEs | **This is now the highest-value missing piece.** It is what a Lao accountant needs on 31 March, and it is what the MoF software-licence test examines: the licence application requires "a balance sheet example produced by the programme". ERPNext's stock Balance Sheet is not the Lao statutory format. Blocked on 1b.2. |
| 1b.2 | **Obtain a prescribed statutory report template and have the PCG chart reviewed** by a Lao-qualified accountant or the LCPAA | Unblocks 1b.1 and closes §1.3 of the roadmap at the same time. The chart currently rests on secondary sources. |
| 1b.3 | ~~**Input VAT 3-month claim window**~~ **Done.** `_warn_if_input_vat_claim_window_missed` measures from the supplier's `bill_date`, not the posting date — a purchase booked late is exactly the case that misses the window. | PwC: "Input VAT can be claimed within three months from the date incurred." A stale claim is silently rejected money. |
| 1b.4 | ~~**Micro-enterprise treatment**~~ **DONE 2026-09-16** | 94.2% of Lao enterprises are micro. `lao_profit_tax_regime` on Company (Standard / Micro-enterprise), dated rates in `lao_regional/data/lao_profit_tax.json`, and `profit_tax.py` with an estimate that carries every reason not to rely on it. See the note below — researching this changed what was built. |

### What researching 1b.4 turned up — read before touching profit tax

The roadmap said "flat 5% CIT on net profit". That is right, and it was worth checking,
because **Lao PDR runs two regimes side by side and the sources are easy to conflate**:

| Regime | Base | Rate | Who it is for |
|---|---|---|---|
| Profit tax, standard | **net profit** | 24% → **20%** from 1 Jul 2026 | everyone else |
| Profit tax, microenterprise | **net profit** | **5%** from 1 Jul 2026 | microenterprises, under 88/NA |
| Lump-sum (ອາກອນເໝົາ) | **turnover** | 1% manufacturing / 2% commerce / 3% services, ≤400M LAK; 0% below 50M | businesses that **do not keep Lao accounting books** |

> **The disqualifying condition for the lump-sum regime is keeping proper books — and a
> business that adopts bERP keeps proper books.**

So adopting this product can move a Lao microenterprise *out* of a turnover-based
presumptive tax and *into* profit-based assessment. That cuts both ways: kinder for a
thin-margin trader, worse for a profitable one. It is a real consequence of the software,
a Lao owner may reasonably expect to keep paying the turnover tax they always have, and
nothing else in the system would tell them. The app therefore does not offer "Lump-sum" as
a regime at all, and a test asserts that it does not — offering it would invite a tenant to
select a regime that running this software disqualifies them from.

**What the app deliberately does not decide.** The turnover threshold that *qualifies* a
company as a microenterprise under 88/NA is not established in the sources this was built
from — VDB Loi's alert on the new law states the 5% rate and says explicitly that the
thresholds are absent from it. So the regime is a field a human sets, and the app applies
the rate for whatever they set. Guessing a threshold and enforcing it would be inventing
statute. **Open question for the tax adviser: what turnover, assets or headcount qualifies
a company as a microenterprise under 88/NA?**

Also not modelled, each because it needs a qualification test this app cannot make:
listed companies (10%), tobacco and alcohol (22%), mining concessions (35%), casinos (30%),
MNC group members (15%).

**Sources:** VDB Loi's alert on the new Income Tax Law (effective 1 July 2026); PwC
Worldwide Tax Summaries, Lao PDR corporate income; Acclime Laos taxation overview. All
secondary. The statute itself should be obtained alongside the chart sign-off.

---

### Rate corrections already applied

Law No. 88/NA (gazetted 19 June 2026, in force 1 July 2026) moved four withholding
rates. Two were already carried as dated rows; two were not:

- **Commissions, consultancy and service fees 5% → 10%.** The app carried a flat 10%
  from 2024-01-01. **This was a live defect** — any invoice dated before July 2026
  would have withheld at double the statutory rate. Now dated.
- **Sports and performing arts 10% → 5%.** Category was missing entirely. Added, with
  new PCG account **4439**.
- Also added: a Purchase Invoice warning when a cash-settled invoice exceeds
  **1,000,000 LAK**, above which Law 88/NA makes the expense non-deductible unless it
  is paid through a Lao commercial bank account.

Note the conflict recorded in BERP-LAO-MARKET-001 §7: PwC's table, reviewed 7 August
2026, still shows the pre-88/NA rates for consultancy and for artists and athletes.
The app follows 88/NA. A Lao tax adviser should settle this before these rates carry
real invoices.

---

## Phase 2 — Compliance depth

| # | Task | Why |
|---|---|---|
| 2.1 | VAT return export in the official form layout | The report reconciles; it does not produce something fileable. Needed before anyone files from it. |
| 2.2 | ~~Item-level VAT treatment~~ **DONE 2026-09-17** | The VAT return now classifies **per line**, from `Sales Invoice Item.item_tax_rate` — the rate ERPNext actually applied. Three Lao Item Tax Templates ship (10%, 0% export, exempt), and a rule warns when a line contradicts its invoice's header type. **The defect this fixed:** grouping by the invoice-level type and summing `base_net_total` declared a mixed invoice entirely under its header label. Measured — 1,000,000 taxable + 500,000 exempt marked "Standard" declared a 1,500,000 standard-rated base against 100,000 of output VAT, so **the return did not reconcile with itself**: at 10% that base implies 150,000. ERPNext charged correctly throughout; only the report was wrong. Validated against the known-bad: with the old implementation restored, three of the new tests fail with the right messages. |
| 2.3 | ~~Withholding certificate for suppliers~~ **DONE 2026-09-16** | A supplier who has had tax withheld is paid net and needs the statement to evidence the credit. `lao_regional/certificates/withholding.py` builds it from ERPNext's own `Tax Withholding Details` rather than re-querying the ledger — one representation cannot drift from itself. Bilingual Lao/English document, both TINs, the statute, the total in Lao words, and a `check()` that says on the document's face when it is not fit to issue. 14 tests. **Verified end to end:** rendered through wkhtmltopdf, the PDF embeds Phetsarath and Noto Sans Lao and 203 Lao codepoints survive extraction. **Upstream defect found:** `Tax Withholding Details` raises MariaDB 1064 when `party` is a list — which is what its own MultiSelectList filter sends. We pass a scalar, and a characterization test pins that. |
| 2.4 | Invoice numbering | **Researched 2026-09-17; still open, and deliberately not built.** Established: taxpayers must issue invoices conforming to "the specific and general formats issued by the Ministry of Finance" (VDB Loi Lao Tax Booklet), so a prescribed format exists. **Not** established, in Instruction 0077/MOF, Instruction 618/MOF, PwC or KPMG: whether the format carries an authority-controlled serial, whether invoice books must be registered, or whether a computerised system may assign its own numbers. Measured on our bench: numbers are `ACC-SINV-2026-00005`, the counter is **per prefix per site, not per company**, a deleted draft reverts it, a cancelled invoice keeps its number, an amendment appends `-1`. **The shared counter is fixed, opt-in, 2026-09-17** — independent of the statutory answer, because a company's own sequence being contiguous is never worse. `lao_per_company_invoice_numbering` on Company, off by default; `before_naming` gives the company `SINV-<ABBR>-.YYYY.-` with its own `tabSeries` counter, and `-RET-` for credit notes. Amendments keep ERPNext's `-1`. **The test reproduces the defect rather than a proxy:** two companies on one site, flag off → Company A's numbers differ by 2; flag on → by 1. Numbering *itself* — whether the authority issues the numbers — remains BERP-LAO-QUESTIONS-001 Q9. |

---

## Phase 3 — Productise

| # | Task |
|---|---|
| 3.1 | Create the `berp_whitelabel` repository — the app is finished and has nowhere to go |
| 3.2 | Logo asset: `hooks.app_logo_url` points at a file not in the repo |
| 3.3 | Verify `berp_whitelabel` on a bench; its 20 tests have never run either |
| 3.4 | Per-tenant provisioning for BizEra.la |
| 3.5 | bOPEN integration (deep-study Ch10) |

---

## Phase 4 — Blocked or later

| # | Task | Status |
|---|---|---|
| 4.1 | ~~TaxRIS e-filing~~ → **E-Tax Invoice integration** | **Q1 is answered, and the target was wrong.** TaxRIS is the tax administration's *internal* system — the 2026 programme is officer training, not a taxpayer API. The taxpayer-facing surfaces are DTax (registration and filing) and the **E-Tax Invoice system launched 29 May 2026**. That one is demonstrably integrable: `bansi.la` claims certified E-Tax Invoice connectivity through the MoF Department of Financial Information Technology, and AssetAsia and Pakaithip both issue e-tax invoices. So this is no longer blocked on *whether* an interface exists — it is blocked on **obtaining the specification**, which is a relationship with that Department. **Done 2026-09-16:** the seam is now `lao_regional/e_filing/`, carrying both surfaces — `vat_return.py` for DTax and `e_invoice.py` for the E-Tax Invoice system, the latter with a statutory `check()` and 16 tests. Still blocked on the specification, which is a relationship with that Department, not engineering. See BERP-LAO-MARKET-001 §3.2 and the ADR-A3 amendment. |
| 4.2 | NSSF payroll integration | Not started |
| 4.3 | Upstream Lao support to num2words | Optional follow-on to 1.1 |

---

## Structure — BERP-LAO-ARCH-001 *(proposed 2026-09-16)*

`docs/BERP-LAO-ARCH-001.md` proposes seven structural decisions. One of them fixes
something currently broken and should not wait:

| # | Decision | Note |
|---|---|---|
| A4 | **Ship the Lao fonts with the app** | **Fixes a live defect.** `app_include_css` does not reach Frappe's print pipeline — verified against `printview.get_print_style` — so the Lao Tax Invoice loads no Lao font at all and renders in a fallback. Self-host Phetsarath OT and Noto Sans Lao (both SIL OFL 1.1, redistribution permitted) and wire them through the Print Format's own `font` and `css` fields. |
| A1 | Split `lao_regional/utils.py` into `country.py` + `rules/` | Six modules import country logic from a file called "utils", and one does a deferred import to dodge a cycle |
| A2 | Custom field definitions to JSON | 122 of `install.py`'s 295 lines are a literal; nothing validates `insert_after` or `options` against the live meta |
| A3 | ~~Rename `taxris/` → `e_invoice/`~~ → **`e_filing/`, done 2026-09-16** | Named after the wrong system. Amended on implementation: two surfaces, not one |
| A5 | `deploy_berp_online.sh` out of the Python package | It ships to every site |
| A7 | Split the tests to mirror `rules/` | `test_vat_return.py` is 710 lines and owns the shared fixture |
| A6 | `statutory/` package | Deferred until a prescribed template is in hand |

---

## Engineering hygiene, any time

- **Branch protection on `main`** for all three repositories. ADR-023 authorizes
  feature-branch pushes and says enforcement must be server-side; it currently is not.
- **Fix the stop hook.** It reported "6 unpushed commits, no remote branch" against a
  branch already published, because the clone was made `--depth 50` and its fetch
  refspec was pinned to `main`. A hook reading local state can be confidently wrong.
- **`device_commit_files` silently fails.** Three occurrences on 2026-09-14/15:
  reported success, updated the mtime, wrote nothing. Round-trip every write — read
  the file back and compare — until it is fixed.
- **Rename `docs/01-erpnext-deep-study/07-lao-berp-design.md`**; it still carries the
  old app name. Needs the device's Linux workspace.
- **Retire `C:\laragon\www\berp\berp_lao\`** once `berp_lao_app\` is confirmed good.

---

## Sequencing

```
Phase 0  ██████                      gate — days
Phase 1        ████████████          1.1 and 1.2 are the real work — 1–2 weeks
Phase 2                    ██████    after an accountant has seen Phase 1
Phase 3          ████████            can run parallel to Phase 1; different skills
Phase 4                              blocked / opportunistic
```

Phase 3 is the one that can overlap: it is branding and deployment work, and it does
not touch the accounting logic Phase 1 is changing.

---

## What would change this plan

- CI or the bench verification finding something structural in Phase 0.
- An accountant rejecting the class 1 / class 4 root split — that would be a chart
  rebuild and would reorder everything.
- The Revenue Department answering TAXRIS Q1 positively, which would promote 4.1.
  **Partly answered as of 2026-09-15** — see 4.1.
- The MoF software-licence requirement (BERP-LAO-MARKET-001 §1) turning out to bind
  earlier or harder than assumed. It gates statutory *filing*, not use, so it does not
  block a first customer — but it does gate the product becoming the system of record,
  and it is an entity-formation task with a lead time, not an engineering one.
- A finding on data residency. Nothing establishes whether Lao accounting data must be
  hosted in Laos. If it must, the BizEra.la multi-tenant plan needs Lao infrastructure.
