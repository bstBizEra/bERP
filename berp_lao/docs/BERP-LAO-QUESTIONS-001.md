# BERP-LAO-QUESTIONS-001 — What berp_lao needs from people

**Date:** 2026-09-17
**Status:** Open. This is the whole remaining blocker list for `berp_lao`.
**Applies to:** `berp_lao` on branch `feat/installable-app-lao-pcg-vat`

---

## Why this document exists

Every item left on the roadmap that engineering can close has been closed. What
remains is not work — it is **eleven questions**, and they have been scattered across
five documents where nobody could answer them as a set.

They fall to **four counterparties**, and two of the four are one meeting each. This
document exists so that one meeting settles several at a time, rather than each being
rediscovered separately over months.

Each question below states what is needed, why it blocks, **what has already been
established and from which source**, and **what the app does with each possible
answer** — so the person answering can see that their answer changes something, and
what.

| Counterparty | Questions | Unblocks |
|---|---|---|
| **A Lao-qualified accountant / LCPAA** | Q1–Q4 | statutory statements, the chart, the VAT return |
| **A Lao tax adviser** | Q5–Q7 | two live rates, the microenterprise regime |
| **MoF, Dept of Financial Information Technology** | Q8–Q10 | e-invoicing, invoice numbering, the software licence |
| **Any Lao reader** | Q11 | the printed documents |

> **One caution on how to read the "established" lines.** Every source cited below is
> **secondary** — PwC, VDB Loi, Acclime, KPMG. Not one is the statute. Where a
> secondary source is all we have, the question is worded so that the answer either
> confirms it or replaces it, rather than assuming it is right.

---

## For a Lao-qualified accountant or the LCPAA

### Q1 — Does the chart of accounts hold up?

**We need** sign-off on 113 accounts built to the Lao MoF PCG 8-class structure, with
79 postable leaves.

**Why it blocks** everything downstream. The chart is what the statements are drawn
from, what the VAT return aggregates, and what the tax accounts hang off. It currently
rests on a `docs/` template plus a reading of the class structure.

**Established:** the governing statute is the Law on Accounting (amended) No. 46/NA of
20 November 2023, in force 31 March 2024, replacing 47/NA of 2013.

**The one structural decision to look at first.** PCG classes 1 and 4 each straddle two
ERPNext root types, and ERPNext applies a **root** node's type to its entire subtree —
a type set on a nested node is silently ignored. So each of those two classes is
emitted as **two roots**. The account numbers are preserved; the tree shape is not the
statutory one.

> **The question in one line:** does splitting classes 1 and 4 into two roots each
> change anything a Lao auditor or the Revenue Department would object to, given the
> numbers are unchanged?

**What we do with the answer.** Acceptable → the chart is signed and 1b.1 unblocks.
Not acceptable → the split has to be undone, which means the statements are built from
a flat account list rather than ERPNext's tree, and that is a different design.

---

### Q2 — What is the prescribed statutory financial statement layout?

**We need** the MoF's prescribed format for the balance sheet, income statement, cash
flow and notes — ideally the form itself, not a description.

**Why it blocks** the single highest-value missing piece in the app. ERPNext's stock
Balance Sheet is not the Lao statutory format, and **the software-licence application
asks for "a balance sheet example produced by the programme"** (see Q10), so this
blocks the licence too.

**Established:** public interest entities apply full IFRS; everyone else applies **LFRS
for Non-Public Interest Enterprises**, based on IFRS for SMEs (2009). Annual statements
are due **31 March** (Decision 137/VTE, 13 February 2024) and records are kept 10 years.

**What we do with the answer.** The template becomes `lao_regional/statements/`, built
as ADR-A6 describes. Without it we would be guessing at a form the MoF will judge us on.

---

### Q3 — Does the VAT return need to be produced on an official form?

**We need** to know whether the monthly VAT return has a prescribed layout a taxpayer
must file on, and if so, the form.

**Why it blocks** roadmap 2.1. Today the report **reconciles** — it produces correct
numbers a human can check — but it does not produce something anyone can file.

**Established:** VAT is 10% (Presidential Decree 003/PS, effective 1 May 2024), exports
are zero-rated, and the return is monthly.

**What we do with the answer.** A prescribed form → we render it, the way the tax
invoice is rendered. No prescribed form → 2.1 closes as "the report is the deliverable"
and we stop carrying it as a gap.

---

### Q4 — Does the input VAT three-month window need to be modelled, or only warned about?

**We need** confirmation of the rule and of what happens to a claim that misses it.

**Why it matters:** the app **warns** today, measuring from the supplier's `bill_date`
rather than the posting date, because a purchase booked late is exactly the case that
misses the window. It does not track what was carried forward or what has expired.

**Established:** PwC records that Lao input VAT can be claimed within three months of
being incurred.

> **The question in one line:** is an out-of-window claim simply refused, or does it
> carry forward — and does the return have to show the carry-forward?

**What we do with the answer.** Simply refused → the warning is the right treatment and
1.5 closes. Carries forward → the VAT return needs a carry-forward column and a balance
the taxpayer tracks across periods, which is real work and would be scheduled.

---

## For a Lao tax adviser

### Q5 — PwC and Law 88/NA disagree on two withholding rates. Which governs?

**We need** a ruling on two categories where our sources conflict.

**Why it blocks:** these rates will withhold real money from real suppliers. The app
currently follows 88/NA.

| Category | Law 88/NA (what we follow) | PwC, reviewed 7 Aug 2026 |
|---|---|---|
| Commissions, consultancy, service fees | 5% → **10%** from 1 Jul 2026 | still shows the pre-88/NA rate |
| Sports and performing arts | 10% → **5%** from 1 Jul 2026 | still shows the pre-88/NA rate |

**Established:** Law on Income Tax No. 88/NA was gazetted 19 June 2026 and is in force
from 1 July 2026. Rates in the app are **dated rows**, so an invoice dated before a
change still withholds at the old rate — whichever way this is resolved, historical
invoices are unaffected.

**What we do with the answer.** A new dated row in
`lao_regional/data/lao_tax_templates.json`. Nothing else changes; this is the case the
dated-row convention was built for.

---

### Q6 — What qualifies a company as a microenterprise under 88/NA?

**We need** the threshold — turnover, assets, headcount, or a combination.

**Why it blocks:** the difference is **20% versus 5% of net profit**. On the fixture
company's 1,350,000 LAK that is 270,000 against 67,500.

**Established:** the 5%-on-net-profit rate itself. VDB Loi's alert on the new law states
it and says **explicitly that the qualifying thresholds are absent from their
publication**. We could not find them in any other source.

**What the app does today, deliberately:** it encodes **no threshold**. The regime is a
field a human sets on the Company, defaulting to Standard so that an unset field never
silently reduces someone's tax. Guessing a threshold and enforcing it would be
inventing statute.

**What we do with the answer.** The threshold becomes a check that warns when a company
flagged as a microenterprise has turnover above it — a warning, not a block, because
qualification may depend on facts the ledger does not hold.

---

### Q7 — Does adopting an accounting system move a microenterprise out of the lump-sum regime?

**We need** confirmation of a consequence we believe the product has, because if we are
right, tenants must be told before they adopt it.

**What we believe, and why.** Lao PDR runs two regimes side by side:

| Regime | Base | Rate |
|---|---|---|
| Profit tax, microenterprise | **net profit** | 5% from 1 Jul 2026 |
| Lump-sum (ອາກອນເໝົາ) | **turnover** | 1% manufacturing / 2% commerce / 3% services, ≤400M LAK; 0% below 50M |

Acclime states the lump-sum regime is for businesses that **do not maintain Lao
accounting books**, and that a business maintaining proper records does not qualify.
PwC says the same. **Keeping books is the disqualifying condition.**

A business that adopts bERP keeps proper books. If that reading is right, adopting this
product moves a Lao microenterprise off a turnover tax and onto a profit tax — kinder
for a thin-margin trader, worse for a profitable one.

> **The question in one line:** is that right, and is it automatic on adopting a system,
> or does it depend on registration, election, or turnover?

**What we do with the answer.** Confirmed → it goes in the onboarding material, because
a Lao owner may reasonably expect to keep paying the turnover tax they always have, and
nothing in the software would otherwise tell them. Wrong → we owe the lump-sum regime a
proper treatment, which we currently do not offer at all.

---

## For the MoF Department of Financial Information Technology

### Q8 — May we have the E-Tax Invoice specification?

**We need** the interface specification and whatever certification process attaches to it.

**Why it blocks** roadmap 4.1. This is no longer a research question — the system
exists and Lao products are connected to it.

**Established:** the Ministry launched the E-Tax Invoice system on **29 May 2026**.
`bansi.la` states it can connect and send E-Tax Invoice data, with certification
attributed to this Department; AssetAsia and Pakaithip both issue e-tax invoices.

**What we have built against it.** `lao_regional/e_filing/e_invoice.py` — a payload
modelled on what Lao statute requires a tax invoice to carry, not on a guessed wire
format, plus an abstract transport and an inert recorder. **Nothing is live**, and
anything unconfigured resolves to the recorder, so no misconfiguration can submit.

---

### Q9 — How must a Lao tax invoice be numbered?

**We need** to know whether invoice numbers are controlled by the tax authority.

**Why it blocks** roadmap 2.4, which we have deliberately not built. If registered
invoice books or authority-issued serial numbers are required, ERPNext's naming series
may not satisfy the requirement at all, and building a numbering scheme first would be
building the wrong one.

**Established:** taxpayers "must issue invoices that meet the Lao requirements and
conform to the specific and general formats issued by the Ministry of Finance" (VDB Loi
Lao Tax Booklet). So a prescribed format exists. **We could not establish** whether it
carries an authority-controlled serial, whether invoice books must be registered, or
whether a computerised system may assign its own numbers. Instruction 0077/MOF on VAT
implementation, Instruction 618/MOF on the Easy Tax System, and PwC's Lao pages are all
silent on it.

**What our system does today, measured on a bench:**

```
number format     ACC-SINV-2026-00005      prefix · year · 5-digit counter
counter scope     per prefix, PER SITE — not per company
deleted draft     the counter reverts, so no gap
cancelled invoice keeps its number — a gap in the issued sequence
amended invoice   the original number with "-1" appended
```

> **Two questions in one line each.** Must the number come from the tax authority, or
> may the system assign it? And must the issued sequence be gapless per company?

**Already done, because it needed no answer from you.** Two companies on one site shared
a counter and neither was gapless on its own — hard to explain to an auditor under any
rule. `lao_per_company_invoice_numbering` on Company (off by default) now gives a company
its own sequence. **This does not answer the question above**; it removes one thing that
was wrong regardless of how you answer it.

**What we do with your answer.** Authority-issued → we add a field for it and stop
generating numbers, which is a significant change and worth knowing before tenants have
history. System-assigned but gapless per company → the flag becomes the default, and we
add a gap report. No constraint → 2.4 closes.

---

### Q10 — What does the accounting-software licence require of us?

**We need** the application requirements and the assessment criteria.

**Why it blocks** commercial use, not engineering. **Only a licensed system's output is
accepted for statutory submission**; internal bookkeeping is unrestricted. The licence is
held by the software's creator and needs a Lao entity, so it is entity formation as much
as engineering.

**Established:** MoF Decision No. 1835/MOF, dated 14 July 2020, in force 28 July 2021.
The application requires "a balance sheet example produced by the programme" — which is
Q2.

**Why this is the same conversation as Q8 and Q9.** All three sit with the department
that certifies systems. It is plausible that the licence assessment is precisely where
the invoice-numbering and statement-format questions are answered in practice, in which
case one meeting closes Q2, Q8, Q9 and Q10 together.

---

## For any Lao reader

### Q11 — Do the printed documents read correctly?

**We need** a Lao reader to look at two printed PDFs at 200% and say whether the tone
marks sit where they should.

**What is now checked without you.** `tests/test_client_scripts.py` verifies that every
server method the Desk buttons call resolves and is whitelisted, and that the scripts read
only fields and boot keys that exist — so a dead button is no longer a way this fails.

**Why no test can close the rest.** The suite proves the fonts are embedded and that the
text extracts as Lao codepoints. It cannot prove the combining marks are **placed** correctly,
and that is the failure that matters: DejaVu covers the Lao block, so a font problem
does not produce boxes — it produces Lao that is visually plausible with the marks in
the wrong order, on a document that still looks valid.

`BERP-LAO-VERIFY-001` step 9 has the controlled corpus ready:

| Expected | Reading | What a wrong render looks like |
|---|---|---|
| ໜຶ່ງ | one | `ໜຶງ່` — the tone mark lands after the final consonant |
| ເກົ່າ | nine | the circle mark and tone mark swap or collide |
| ໃໝ່ | new | the vowel sign detaches from its consonant |
| ໜຶ່ງລ້ານສອງແສນກີບຖ້ວນ | 1,200,000 kip exactly | any of the above, inside a longer string |

**Also worth their eye, separately:** `translations/lo.csv` — 83 machine-generated
strings. Accounting terminology is exactly where this goes subtly wrong, and it should
be reviewed **in situ** on the screens rather than as a spreadsheet.

---

## What is not blocked

Nothing below needs an answer above. It is listed so that the blocker list does not
read as "the project is stuck".

- The app installs, migrates and runs on Frappe v15 + ERPNext v15.
- **199 tests pass**, one skipped by design; **24** more in `berp_whitelabel`, which was
  executed end to end for the first time on 2026-09-17 and came back clean — a configured
  tenant brand reaches what Frappe actually serves.
- VAT, withholding, profit tax, the tax invoice, the withholding certificate and both
  filing seams are built and measured.
- The remaining engineering item nobody is waiting on: **`berp_whitelabel` has no
  repository.** The app is finished, its branding path has now been run end to end, and
  it has nowhere to go.
