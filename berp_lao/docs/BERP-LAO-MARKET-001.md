# BERP-LAO-MARKET-001 — The Lao ERP solution landscape

**Date:** 2026-09-15
**Status:** Research brief. Desk research only; no primary contact with the Ministry of
Finance, the LCPAA or any named vendor.
**Applies to:** `berp_lao`, and to the commercial plan built on it.

---

## Executive summary

Three findings, in order of how much they change the plan.

**1. Accounting software is a licensed product in Laos.** The Ministry of Finance
licenses the *software*, through a numbered, fee-bearing, annually renewed formality
administered by its Accounting Department. Only a licensed system's output is accepted
for statutory submission. This is not a formality `berp_lao` can satisfy by being
technically correct: the licence is held by a Lao legal entity that owns or is licensed
the IP, and the application requires a Lao enterprise registration certificate, articles
of association and TIN. **It is an entity-formation task, not an engineering task, and it
sits on the critical path to selling this as statutory-grade software.**

**2. The competitive floor is zero.** A Lao-language, MoF-licensed, e-tax-capable online
accounting system is given away free to MSMEs by a Lao social enterprise under licence
0534/MoF of 12 February 2024. The paid local market prices against that floor at roughly
1.3–3.0 million LAK (≈ USD 60–135). No ERP vendor can win Lao micro-enterprises on price,
and any pricing model that assumes Thai or Vietnamese levels (3–10× higher) is wrong for
this market.

**3. The addressable market is much smaller than the enterprise count suggests, and the
open space is mid-market.** Laos has ~134,000 enterprises, but 94% are micro, and only
12.9% of business units hold a TIN. The ~7,800 small, medium and large enterprises are the
ones that need double-entry books, inventory, multi-user access and an audit trail — and
that band is served by a thin field: one Odoo partner, no SAP/NetSuite/Xero/QuickBooks
partner, no Thai or Vietnamese vendor, and **no ERPNext partner anywhere in Laos**.

The strategic read: the regulatory gate is real but narrow (it binds statutory filing, not
day-to-day use), the free tier owns the bottom, and the mid-market is genuinely open. That
argues for positioning `berp_lao` as an **operations ERP for growing Lao SMEs that also
produces a compliant statutory pack** — with the MoF licence pursued as a business
milestone rather than a prerequisite for the first customer.

---

## 1. The regulatory gate: MoF licensing of accounting software

### 1.1 The instrument

| Field | Value |
|---|---|
| Title | Decision on the Management of Accounting Software |
| Number | **No. 1835/MOF** |
| Issued | 14 July 2020, by the Minister of Finance |
| In force | 28 July 2021 |
| Replaces | Order/Agreement No. 0210 (2010) on the Computerised Enterprise Accounting Programme |
| Statutory hook | Law on Accounting No. 47/NA (2013), Art. 80(7) — MoF may "approve, suspend and cancel the use of accounting software" |
| Scope | Individuals and legal entities **using and developing** accounting software in Lao PDR |

**The text of 1835/MOF is not published anywhere reachable, in Lao or English.** Its number
and date come from two independent places: a Rajah & Tann Asia regional round-up, and the
Lao Ministry of Industry and Commerce business-licence database, which cites it as the legal
basis of the formality and names the operative articles (Ch.1 Art.4, Ch.5 Art.15, Ch.6
Art.19). Everything below about *procedure* is therefore reconstructed from the government's
own formality record, not from the Decision itself.

Banks and financial institutions are carved out to the Bank of Lao PDR, which runs its own
accounting-programme requirement (BOL Notice No. 613/BOL, October 2023, for non-bank
financial institutions). A Lao bank is not a `berp_lao` prospect without a second regulator
in the conversation.

### 1.2 The formality

Item **#43** in the Lao Inventory of Business Formalities, code **MoF-AD-15**, competent
authority the **Ministry of Finance Accounting Department**:

- **English title:** Permit to Use and Sell the Enterprise Accounting Programme
- **Lao title:** ໃບອະນຸຍາດນໍາໃຊ້ ຫຼື ຈັດຈໍາໜ່າຍໂປຣແກຣມບັນຊີ — permit to *use or distribute*
- **Applicant:** "any person or legal entity that creates the enterprise accounting
  programme" — i.e. the maker, not the user
- **Required documents:** a balance sheet produced by the programme; the user manual;
  evidence of intellectual property right; TIN certificate; enterprise registration
  certificate; articles of association
- **Fees:** 1,100,000 LAK on application (500,000 service + 600,000 certificate);
  **500,000 LAK annual renewal**
- **Processing:** 10 working days, **including testing of the software** by the Department

⚠️ **These figures are from the pre-2020 record.** The Lao Trade Portal listing still cites
only the 2010/2016 legal bases; the MoIC record cites 1835/MOF. Treat the fees and the
10-day limit as indicative and re-verify against the current Decision.

Acclime's phrase "licences and annual track records for approved systems" maps onto the
annual renewal line. The exact legal difference between a *licence* and a *track record* is
not established.

### 1.3 What this means for `berp_lao` — concretely

| Question | Answer | Confidence |
|---|---|---|
| Can a Lao company run `berp_lao` for internal bookkeeping? | **Yes, unlicensed.** "Businesses may use any software for internal bookkeeping." | Stated by Acclime |
| Can it file statutory accounts off `berp_lao`? | **Not until `berp_lao` holds an MoF licence.** "Only software holding a current MOF licence is valid for statutory submissions." | Stated by Acclime |
| Who applies for the licence? | The creator/distributor. In practice, **BizEra as a Lao-registered entity**. | Stated (applicant definition) |
| Can an open-source / foreign-developed system be licensed? | **Not established.** But the document list demands a Lao ERC, articles and TIN, and "evidence of intellectual property right" — so a Lao entity must hold it. GPL-3.0 licensing of `berp_lao` is not obviously an obstacle to the applicant *owning* its own distribution, but this needs a Lao lawyer's view, not mine. | **Inferred** |
| Does custom/in-house software escape? | **No.** "Individuals and legal entities that intend to develop accounting software for specific project must seek permission from MOF." A bespoke `berp_lao` deployment for one client is caught. | Stated |
| Is it enforced? | **Administratively live, weakly policed.** A real licence (0534/MoF, 12 Feb 2024) was issued 2½ years after the Decision. But there is **no public register**, no reported penalty and no documented rejected filing. Consequences are always described conditionally. | Mixed |

**The practical pattern in the market** is a dual stack: an unlicensed international system
for day-to-day bookkeeping, plus a licensed Lao product — or a licensed accounting firm — to
produce and file the statutory pack. That is exactly the shape of the opportunity and the
constraint at once: `berp_lao` can be sold into Laos tomorrow as the operations system, and
cannot be the system of record for filing until the licence exists.

### 1.4 Technical criteria the licence implies

None of these come from 1835/MOF, which I could not read. They come from the Law on
Accounting and the formality record, which the Decision implements.

| Requirement | Source | `berp_lao` status |
|---|---|---|
| Lao language and Kip | Law 47/NA Art. 7 | ✅ `translations/lo.csv`, LAK default, bilingual print format |
| Arabic figures; **full stop** thousands, **comma** decimals | Law 46/NA (2023) | ✅ `1.000.000,00` — already the app's LAK format |
| MoF-prescribed chart of accounts | Law 47/NA Art. 28, carried into 46/NA | ⚠️ PCG chart implemented but **never reviewed by a Lao accountant** |
| Electronic records must follow the same procedure as manual, and be tested before use | Law 47/NA Art. 21 | ⚠️ Untested against a bench, let alone an MoF test |
| 10-year retention in "secure and safe databases" | Law 47/NA Arts. 50–51 | ⚠️ A deployment property, not an app property. Needs a documented backup/retention posture. |
| Balance sheet output in the prescribed format | Formality record | ❌ **Not built.** ERPNext's stock Balance Sheet is not the Lao statutory format. |
| Compliance with the Electronic Transactions Law | Law 47/NA Art. 29 | ❓ Unassessed |
| Data residency | — | ❓ **No source either way.** Do not assume Lao hosting is required; do not assume it is not. |
| Audit trail / immutability | — | ❓ Not addressed in any accessible source |

The two entries that should worry us are **the prescribed statutory report formats** and
**the chart of accounts**. Both are MoF-defined, both are what the licence test examines,
and neither has been checked against a real prescribed template.

---

## 2. Accounting standards and statutory reporting

- **Law on Accounting (amended) No. 46/NA, 20 November 2023, in force 31 March 2024**,
  replacing Law 47/NA of 26 December 2013. `berp_lao` documentation that cites 47/NA as the
  live instrument is out of date; 47/NA remains the best-readable English text, which is why
  it is still cited above for article numbers.
- **Public interest entities** (banks, insurers, securities firms, listed companies) apply
  **full IFRS**.
- **Everyone else** applies **LFRS for Non-Public Interest Enterprises**, based on the
  **2009** version of IFRS for SMEs. Texts are published by the LCPAA.
- **Micro-enterprises** have simplified guidelines.
- **Mandatory audit:** PIEs, foreign enterprises, state-owned enterprises, donor-funded
  projects, and non-PIEs with **total assets over 50 billion LAK**.
- **Accounting period:** calendar year. **Financial statements due 31 March** — within two
  months of year-end, filed with the Tax Department (Decision No. 137/VTE, 13 February 2024).
- **Records in Lao language and Kip** unless MoF permits otherwise; **10-year retention**.
- **Professional body:** LCPAA (est. 1998), membership mandatory for professional
  accountants, running the disciplinary system jointly with MoF.

**Implication for `berp_lao`:** the target customer's framework is *LFRS for Non-PIEs*, i.e.
IFRS for SMEs (2009). That is a simpler standard than full IFRS and is well within what
ERPNext's accounting model supports. The gap is not the ledger — it is the **prescribed
presentation**: a Lao statutory balance sheet, income statement, cash flow statement and
notes in the MoF's own layout. That is report-building work, and it is the single most
valuable piece of localisation still missing.

---

## 3. Tax administration and the e-filing surface

### 3.1 What exists

| System | What it is | Taxpayer-facing? |
|---|---|---|
| **TaxRIS** | Tax Revenue Information System, run by the Tax Department. Taxpayer data, declarations, VAT notices, Property Revenue notices (Form N), other notices (Form M), amendments, penalty waivers, audit memoranda. | **No — officer-facing.** The 2026 programme is eight training rounds for district and city tax officers, funded under PFM Reform Phase 3 (DFAT + EU). |
| **DTax** | Online registration and VAT filing, used by non-resident digital suppliers since 1 August 2024 under MoF regulation 0558/MOF. Quarterly filing, payment in USD/EUR/CNY, eInvoices for B2B. | **Yes, but narrow** — built for foreign digital suppliers. |
| **E-Tax Invoice system** | **Launched 29 May 2026** by the Ministry of Finance. | **Yes.** Newest and most relevant. |
| **Smart Tax** | Electronic payment platform. | Yes |
| **Smart Customs** | Launched 2 June 2026; customs, not accounting. | n/a |

### 3.2 This resolves Q1 of BERP-LAO-TAXRIS-001 — and reframes it

BERP-LAO-TAXRIS-001 asked whether TaxRIS exposes any taxpayer-facing machine interface.
**The evidence says no, and that TaxRIS was never the right target.** TaxRIS is the tax
administration's internal system. The taxpayer-facing surface is DTax for registration and
filing, and the **E-Tax Invoice system** for invoices.

And the e-invoice surface is demonstrably integrable: two Lao products already claim to
connect to it. `bansi.la` states its system "ສາມາດເຊື່ອມຕໍ່ ແລະ ສົ່ງຂໍ້ມູນ E-Tax Invoice" —
can connect and send E-Tax Invoice data — with certification attributed to the MoF
Department of Financial Information Technology. AssetAsia lists e-tax invoice issuance and
testing. Pakaithip sells a separate e-tax invoice programme.

**So there is a real interface, and someone knows its shape. It is just not documented in
public.** That changes the TaxRIS unit's disposition from "blocked on whether an interface
exists" to "blocked on obtaining the specification" — a relationship problem with the
Department of Financial Information Technology, not a research problem. The abstract
transport in `lao_regional/e_filing/` (renamed from `taxris/` on 2026-09-16) was the
right call and should stay; it should be
retargeted at e-tax invoicing rather than at VAT-return filing.

### 3.3 Tax facts that bind the app

- **VAT 10%**, registration automatic on obtaining a TIN or investment approval, **except
  micro-enterprises**. Monthly returns. Exports zero-rated.
- **Input VAT claimable within three months of the date incurred.** `berp_lao` does not
  enforce this. It should — a stale input-VAT line is a silently rejected claim.
- **Law on Income Tax No. 88/NA**, gazetted 19 June 2026, in force **1 July 2026**,
  replacing the 2019 law. Four withholding rates moved at once:

  | Category | Old | New |
  |---|---|---|
  | Commissions, consultancy and service fees | 5% | **10%** |
  | E-commerce / online sales | 2% | **10%** |
  | Construction and repair | 2% | **5%** |
  | Sports and performing arts (above minimum wage) | 10% | **5%** |

- **New 15% domestic minimum top-up tax** for qualifying subsidiaries of multinational
  groups. Out of scope for an SME ERP; relevant if BizEra ever sells upmarket.
- **Micro-enterprises: flat 5% CIT on net profit**, replacing the activity-based system.
- **Expenses above 1,000,000 LAK per invoice are deductible only if settled through a Lao
  commercial bank account.** This is a live, checkable rule and `berp_lao` now warns on it.
- Tax-to-GDP fell from 14.1% (2013) to ~10% (2021). The Tax Strategic Development Plan
  targeted 15% by 2025. **Revenue pressure is the reason compliance tooling keeps tightening
  — expect the licensing regime to get stricter, not looser.**

---

## 4. The competitive landscape

### 4.1 The free, MoF-licensed incumbent at the bottom

**ASSET (assetasia.net)** — "Accounting System Supports Ending Troubles".

- Provider: **ASSET Asia Co., Ltd.**, a Lao **social enterprise** registered 6 December
  2022, grown out of the ASSET Project founded by EBIT Consultancy on 29 May 2021.
- **Licence number 0534/MoF, dated 12 February 2024**, published on its own homepage.
- **Free.** No paid tier disclosed.
- Lao-language UI. Journal entries, income/expense, general ledger, AR/AP, **e-tax invoice
  issuance**, inventory, trial balance, financial reporting.
- Actively marketed: MSME training programme, a guest lecture at the National University of
  Laos in January 2026, TikTok and Facebook presence, Vientiane Times coverage.

One caveat: EBIT's own wording is narrower — "for Micro-Enterprises" — and part of the
assetasia.net copy describes licence 0534/MoF as covering **small** enterprises. Whether the
licence reaches medium enterprises is unsettled, and it matters: if it does not, the
medium-enterprise band has no free compliant option.

### 4.2 The commercial local field

| Product | Vendor | Shape | Price |
|---|---|---|---|
| **bansi.la** (ບັນຊີ.la) | 57BYTES Sole Co., Ltd (est. June 2018, Vientiane) | Cloud + Android/iOS. VAT invoicing, inventory with stock transfers and expiry, **manufacturing**, B.POS retail POS, journals with Excel upload. WSA Business & Commerce nominee 2021. Runs "Bansi Academy" content marketing. Claims E-Tax Invoice connectivity. | 2,984,000 LAK starter (billing period unconfirmed) |
| **APIS** | APIS Company Limited (est. 13 Sept 2001, Vientiane) | 17+ products: business accounting, warehouse, restaurant, hotel, bank accounting, property, school, payroll, tax invoice management. **Online and offline.** Named by KPMG as MoF-approved. | Not published |
| **Pakaithip** (ປະກາຍທິບ) | Owner not identified on site | Online accounting + a separate e-tax invoice programme; custom development. Lao/EN/ZH/VI. | Not published |
| **"Intercom"** | — | Named as MoF-approved by KPMG in 2016 and 2018 and repeated since. **No vendor, website, product or evidence of current existence could be found.** Do not treat as a live competitor without verification. | — |

Local software houses that build to order — **LaoSys Technologies** (advertises ERP, CRM,
POS, HRM, manufacturing ERP), **Lao IT Dev**, **Lailaolab**, **64Bit Development**, **First
Lao Solutions** — plus POS specialists with published Lao pricing: **UnikOnCloud**
(2.3–3.0m LAK/yr), **Speed POS** (1.3m LAK one-time).

### 4.3 International and regional presence

| Vendor | Laos presence |
|---|---|
| **Odoo** | **Two partners.** **Laooddoo Co., Ltd.** — founded 2008 as DevCom, Odoo partner since 2013, a **subsidiary of Kolao Group**, 9 references, 4 certified experts. Plus A-BE ONE Consulting (0 references, 0 experts). Odoo works the market actively: Vientiane roadshow July 2023, Odoo Business Show at the Crowne Plaza Vientiane June 2025. **This is the real competitor.** |
| **Microsoft Dynamics 365 Business Central** | Supported country, but on the **W1 international base** — no Microsoft-shipped Lao localisation. No Lao partner found. |
| **SAP Business One, Oracle NetSuite, Xero, QuickBooks, Zoho Books** | **No Laos partner or reseller found.** Acclime names QuickBooks, Odoo, Xero and Zoho as tools clients use *for internal bookkeeping only*, explicitly not as MoF-approved. |
| **ERPNext / Frappe** | **No partner in Laos.** Frappe lists partners in Thailand (1), Vietnam (1), Myanmar (2), Philippines (4), Indonesia (3), Singapore (2) — and none in Laos, Cambodia or Malaysia. No Lao deployment, no Lao translation effort, no forum activity found. |
| **Thai** (FlowAccount, PEAK, Express, Business Plus, Formula) | **None found.** |
| **Vietnamese** (MISA, Fast, Bravo, 1C) | **None found.** |
| **Chinese** (Kingdee, Yonyou) | **None found.** |

**Read this carefully.** The absence of ERPNext in Laos is not proof of opportunity — it is
equally consistent with the market being too small and too price-constrained to support a
partner. But the same is true of SAP, NetSuite, Xero, MISA and every Thai vendor, and Odoo
*did* find it worth two roadshows and a Kolao Group subsidiary. The honest reading is that
the mid-market is thin but real, and currently contested by one serious player.

### 4.4 Price anchors

| Market | Product | Price |
|---|---|---|
| **Laos** | AssetAsia | **Free** |
| | bansi.la starter | 2,984,000 LAK (≈ USD 134) |
| | UnikOnCloud POS | 2.3–3.0m LAK/yr |
| | Speed POS | 1.3m LAK one-time |
| **Thailand** | FlowAccount | ฿1,990–5,490/yr |
| | PEAK | ฿499–1,499/mo |
| | Xero / QuickBooks TH | ฿700–2,000/mo |
| **Vietnam** | MISA SME 2026 | 6.15–9.15m VND/yr + per-user |
| | MISA AMIS starter | 2.45m VND/yr |
| **Global** | Odoo | $24.90–49.00/user/mo (annual) |
| | ERPNext | Free (GPLv3); hosting only |
| | SAP Business One | $15K–150K+ implementation |

Reference rate, Bank of Lao PDR, 15 September 2026: ~22,281 LAK/USD.

**The Lao ceiling for small-business software is roughly 1.3–3.0 million LAK — a quarter to
a half of Thai cloud accounting, competing against free.** Odoo's per-user pricing converts
to ~550,000 LAK/user/month, which is 2–4× the *annual* price of the local field. That is
Odoo's weakness and the opening: an ERPNext-based product has no licence cost to pass on.

---

## 5. Market size

| Measure | Figure | Source/date |
|---|---|---|
| Total enterprises | **133,997** | 3rd Economic Census, 2019/20 |
| — micro | 126,168 (94.2%) | |
| — small | 6,600 (4.9%) | |
| — medium | 954 (0.7%) | |
| — large | 276 (0.2%) | |
| Employment | 490,373 | |
| Registered with MoIC | **30.4%** of business units | |
| Holding a licence | 22% | |
| **Holding a TIN** | **12.9%** | ≈17,000 units (my arithmetic) |
| Registered on TaxRIS | 99,419 of 131,688 businesses | Finance Minister, Aug 2022 |
| New registrations | 18,076 (2022), +42.9% YoY | |
| SMEs with a website | **26%** | ADB/LNCCI ProFIT 2024, n=1,386 |
| SMEs reporting no innovation activity | >80% | |
| Internet penetration | 63.6% (4.97m users) | DataReportal, Jan 2025 |
| Digital economy | 3% of GDP, target 10% by 2040 | US ITA |
| IT share of workforce | **1%** | US ITA |
| Informal charges | 5.6% of enterprise revenue | ProFIT 2022 |

**The serviceable market is not 134,000.** It is the ~7,830 small, medium and large
enterprises — and realistically a fraction of those, since only 26% of SMEs maintain a
website at all. A thousand paying customers would be an excellent outcome, not a modest one.

Note also the 1%-of-workforce IT figure. Implementation capacity, not software, is the
binding constraint on ERP adoption in Laos. That is a services opportunity for BizEra and a
cost problem for everyone selling self-serve software into this market.

---

## 6. What this changes for `berp_lao`

### 6.1 Applied in this commit

| Finding | Change |
|---|---|
| Law 88/NA raised consultancy/service WHT 5% → 10% on 1 Jul 2026 | The WHT Services category carried a flat 10% from 2024. Corrected to dated rows: 5% to 2026-06-30, 10% from 2026-07-01. **This was a live defect** — any invoice dated before July 2026 was withholding at double the statutory rate. |
| Law 88/NA lowered sports & performing arts 10% → 5% | New category and PCG account **4439**, with dated rows. |
| Expenses over 1,000,000 LAK must be bank-settled to be deductible | New Purchase Invoice warning when a cash-settled invoice exceeds the threshold. |
| Law 46/NA prescribes Arabic figures, `.` thousands, `,` decimals | README now cites the statutory basis for the LAK format rather than only CLDR. |
| Law 46/NA (2023) replaced Law 47/NA (2013) | README no longer attributes the chart to 47/NA. |

### 6.2 Newly on the roadmap

| Priority | Item | Why |
|---|---|---|
| **P0** | **Lao statutory financial statements** — balance sheet, income statement, cash flow and notes in the MoF's prescribed layout, per LFRS for Non-PIEs | This is what the MoF licence test examines, and what a Lao accountant needs on 31 March. ERPNext's stock reports are not it. Without this the app cannot be licensed and cannot replace the incumbent at filing time. |
| **P0** | **Obtain a prescribed statutory report template and a real PCG chart** from a Lao accountant or the LCPAA | Everything in §1.4 marked ⚠️ resolves here. Currently the chart rests on secondary sources. |
| **P1** | **Input VAT 3-month claim window** — warn when a purchase invoice's input VAT is claimed outside it | A stated, checkable rule; a silently rejected claim is real money. |
| **P1** | ~~**Retarget `lao_regional/taxris/` at the E-Tax Invoice system**, not at TaxRIS~~ **Done 2026-09-16**, and amended: the package is now `lao_regional/e_filing/` and carries *both* surfaces — `vat_return.py` for DTax, `e_invoice.py` for the E-Tax Invoice system. Retargeting the one payload would have left the filing surface with nothing. See ADR-A3. | TaxRIS is officer-facing. The e-invoice interface is the one that exists, launched 29 May 2026, and at least two Lao products already connect to it. |
| **P2** | **MoF software licence application** (business track, not engineering) | Needs a Lao entity, ERC, articles, TIN, IP evidence, a manual, and a balance sheet the software produces. The last item depends on P0. |
| **P2** | **Micro-enterprise 5% flat CIT** and the VAT exemption for micro-enterprises | Affects how the app should behave for the largest segment by count. |
| **P3** | Domestic minimum top-up tax (15%) | Only if BizEra sells to MNE subsidiaries. |

### 6.3 Positioning

The regulatory gate binds **statutory filing**, not use. That suggests a two-stage entry:

1. **Sell `berp_lao` as an operations ERP** — inventory, manufacturing, multi-company,
   multi-currency, project accounting — to small and medium Lao enterprises that have
   outgrown a free bookkeeping tool. This is legal today, unlicensed, and is exactly the band
   AssetAsia does not serve and bansi.la serves only partially.
2. **Pursue the MoF licence** so that the same install becomes the filing system of record,
   which is what removes the customer's dual-stack cost and is the durable moat.

Against Odoo — the only serious mid-market competitor — the argument is cost structure (no
per-user licence), depth of Lao localisation (Odoo runs no Lao localisation at all; Business
Central runs on the W1 international base), and local implementation presence. Against the
free tier, do not compete on price; compete on the things a free bookkeeping tool cannot do.

---

## 7. What is not established

These are open and should not be assumed either way:

1. **The text of Decision 1835/MOF.** Every procedural statement in §1.2 is reconstructed
   from a formality record whose figures pre-date the Decision.
2. **Whether a GPL-licensed, openly-developed system can be licensed**, and the exact form
   the "evidence of intellectual property right" must take.
3. **Data residency** — whether Lao accounting data must be hosted in Laos. Nothing found in
   either direction. This determines whether a cloud offering is viable at all.
4. **Audit trail and immutability requirements.** Not addressed anywhere accessible.
5. **Whether Law 46/NA retains the software-approval power** (old Art. 80(7)), the 10-year
   retention rule, the secure-database rule and the Lao/Kip rule. Both official PDFs of
   46/NA are non-text scans; the MoF copy is proxy-blocked. No firm has published an
   article-level English summary.
6. **Any public MoF register of licensed accounting software.** None found.
7. **Whether licence 0534/MoF covers medium enterprises** or only micro and small.
8. **Whether "Intercom" exists.**
9. **The e-tax invoice interface specification.** Known to exist; not public.
10. **PwC vs VDB Loi on two WHT rates.** PwC's table (reviewed 7 Aug 2026) still shows 10%
    for consultancy and 10% for artists/athletes; VDB Loi's alert on Law 88/NA says 10% and
    5% respectively. This app follows 88/NA. **A Lao tax adviser should settle it before
    these rates carry real invoices.**
11. Any enterprise count more recent than the 2019/20 census.

**Method note.** The Lao vendor landscape is documented on Facebook and TikTok, not on the
indexed web; `bansi.la`, `acs-lao.com` and Lexology all block automated fetch. English-language
advisory content on this market (Acclime, Commenda, Healy) is SEO marketing that asserts the
MoF-approval rule while naming no approved product, and at least one of those pages still
cites the superseded 2013 Accounting Law. **Nothing in this brief substitutes for a
conversation with a Lao-qualified accountant and a Lao lawyer.** The two most valuable next
actions are both offline: obtain a copy of 1835/MOF, and get a prescribed statutory report
template in hand.

---

## Sources

Regulatory and legal:
[Rajah & Tann Regional Round-Up Q3 2021](https://www.rajahtannasia.com/regional-roundup-q3-2021/) ·
[Lao Inventory of Business Formalities #43](https://www.laotradeportal.gov.la/en-gb/site/display/1540) ·
[Formality record PDF](https://www.laotradeportal.gov.la/upload/files/43._Permit_to_Use_and_Sell_the_Enterprise_Accounting_Programme.pdf) ·
[Law on Accounting No. 47/NA (2013), English](http://www.laoofficialgazette.gov.la/kcfinder/upload/files/Accounting%20Law%202013-%20engl%20revised%205%20nov%202014...pdf) ·
[Law on Accounting (amended) No. 46/NA (2023)](https://www.laotradeportal.gov.la/en-gb/site/display/2794) ·
[VDB Loi Law Digest, February 2024](https://www.vdb-loi.com/law_digest/law-digest-february-2024/) ·
[Instruction No. 618/MOF on the Easy Tax System](https://www.laotradeportal.gov.la/en-gb/site/display/1341)

Standards, filing and tax:
[IFAC — Lao PDR](https://www.ifac.org/about-ifac/membership/profile/lao-pdr) ·
[LCPAA — LFRS texts](http://www.lcpaa.la/) ·
[Acclime — financial statement filing](https://laos.acclime.com/guides/financial-statement-filing/) ·
[Acclime — accounting software](https://laos.acclime.com/guides/accounting-software/) ·
[Acclime — bookkeeping compliance](https://laos.acclime.com/accounting/bookkeeping-compliance/) ·
[Commenda — Laos annual compliance](https://www.commenda.io/laos/annual-compliance) ·
[PwC Worldwide Tax Summaries — Lao PDR, other taxes](https://taxsummaries.pwc.com/lao-pdr/corporate/other-taxes) ·
[PwC — withholding taxes](https://taxsummaries.pwc.com/lao-pdr/corporate/withholding-taxes) ·
[VDB Loi — New Income Tax Law 2025 (Law 88/NA)](https://www.vdb-loi.com/laos_publication/vdb-loi-laos-alert-new-income-tax-law-2025-effective-1-july-2026/) ·
[ASEAN Briefing — MoF regulation 0558 and DTax](https://www.aseanbriefing.com/news/navigating-lao-e-commerce-understanding-the-latest-tax-regulations/)

Tax administration and digitalisation:
[KPL — TaxRIS 2026 training](https://kpl.gov.la/En/detail.aspx/detail.aspx?id=97244) ·
[Xinhua — E-Tax Invoice and Smart Customs launch, June 2026](https://english.news.cn/asiapacific/20260602/0f8ba0d7237e49dc954b96fed54ee760/c.html) ·
[AMRO — Progress and Challenges of Lao's Tax Reform](https://amro-asia.org/progress-and-challenges-of-laos-tax-reform-2/)

Vendors and market:
[AssetAsia.net](https://www.assetasia.net/) ·
[57BYTES / bansi.la](https://57bytes.com/) ·
[bansi.la help centre](https://help.bansi.la/lo) ·
[APIS Company Limited](http://www.apislaos.com/) ·
[Pakaithip](https://pakaithip.com/) ·
[Odoo partners — Laos](https://www.odoo.com/partners/country/laos-121) ·
[Laooddoo](https://laoodoo.com/about-us) ·
[Frappe partners by region](https://frappe.io/partners/regions) ·
[KPMG Laos Tax Profile 2018](https://assets.kpmg.com/content/dam/kpmg/xx/pdf/2018/09/laos-2018.pdf) ·
[Microsoft Learn — Business Central country availability](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/compliance/apptest-countries-and-translations) ·
[Aqqount](https://aqqount.com/accounting-service/)

Market size:
[Vientiane Times — 3rd Economic Census](https://www.vientianetimes.org.la/freeContent/FreeConten_Micro34.php) ·
[Vientiane Times / ADB — ProFIT 2024](https://www.vientianetimes.org.la/freefreenews/freecontent_132_Enhancing_y25.php) ·
[World Bank Enterprise Survey — Lao PDR 2024](https://www.enterprisesurveys.org/en/data/exploreeconomies/2024/lao-pdr) ·
[DataReportal — Digital 2025: Laos](https://datareportal.com/reports/digital-2025-laos) ·
[US ITA — Laos Digital Economy](https://www.trade.gov/country-commercial-guides/laos-digital-economy) ·
[Bank of Lao PDR — exchange rates](https://www.bol.gov.la/)
