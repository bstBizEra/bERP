# BERP-LAO-TAXRIS-001 — TaxRIS e-filing groundwork

**Status:** Draft. Interfaces only; nothing here submits anything.
**Date:** 2026-09-14 (amended 2026-09-15, 2026-09-16)
**Applies to:** `berp_lao` ≥ 0.1.0

> **This document keeps its number because a published identifier should not move.**
> The code it describes no longer does: the package is `lao_regional/e_filing/`.

> **Amendment, 2026-09-15 — Q1 is answered, and this unit is aimed at the wrong system.**
>
> TaxRIS is the Tax Department's **internal** system: taxpayer records, declarations,
> notices, audit memoranda, operated by tax officers. Its 2026 programme is eight
> training rounds for district and city offices. It is not a taxpayer API and was never
> going to be one.
>
> The taxpayer-facing surfaces are **DTax** (registration and filing, built for
> non-resident digital suppliers under MoF regulation 0558/MOF) and the **E-Tax Invoice
> system, launched by the Ministry of Finance on 29 May 2026**.
>
> The E-Tax Invoice system *is* integrable, and Lao vendors are already integrated with
> it: `bansi.la` states it can connect and send E-Tax Invoice data, with certification
> attributed to the MoF **Department of Financial Information Technology**; AssetAsia and
> Pakaithip both issue e-tax invoices. So the blocker has changed shape — it is no longer
> "does an interface exist" but "obtain the specification", which is a conversation with
> that Department rather than a research question.
>
> **The seam below stays. Its target changes** from VAT-return filing to e-tax invoice
> issuance. See `BERP-LAO-MARKET-001` §3.

> **Amendment, 2026-09-16 — implemented, with one correction to the line above.**
>
> "Its target changes" was half right. There are **two** taxpayer-facing surfaces, and
> the VAT-return payload already served one of them, so changing its target would have
> deleted correct work and left DTax filing with nothing.
>
> | Surface | Payload | Transport interface |
> |---|---|---|
> | **DTax** — registration and periodic filing | `e_filing/vat_return.py` | `VatReturnTransport` |
> | **E-Tax Invoice** — per-invoice issuance | `e_filing/e_invoice.py` | `EInvoiceTransport` |
>
> The package is named `e_filing` for what it does rather than for either counterparty,
> which is the name that survives the next time a Lao system is renamed. Nothing is live:
> both surfaces default to the inert `RecordingClient`, and that is now asserted rather
> than assumed — `test_an_unconfigured_transport_is_never_live`.
>
> `e_invoice.py` adds a statutory `check()`: missing seller TIN, missing buyer TIN above
> 500,000 LAK, VAT on a zero-rated export, a VAT amount that does not follow from the net,
> a foreign currency with no rate. Each of those is a rejection or an assessment later and
> cheap to fix while the invoice is still amendable.
>
> Still blocked on **obtaining the specification** from the MoF Department of Financial
> Information Technology. That is a relationship, not engineering. See ADR-A3.

---

## 1. Why this is interface-first

TaxRIS is the Tax Revenue Information System operated by the Tax Department of the
Lao Ministry of Finance. It handles taxpayer registration, declarations and
payments, VAT notices and Property Revenue notices (Form N, Form M), and
statistical reporting.

**There is no published integration API.** The Department's 2026 programme is eight
training rounds aimed at subnational offices — the first on 2 March 2026 for 20
districts in Savannakhet and Attapeu — funded under Phase 3 of the Public Financial
Management Reform Program with DFAT and EU support. Public material mentions
"stronger connectivity with internal departments and external systems" and stops
there: no endpoint, no schema, no authentication model, no sandbox.

Building a speculative client against an imagined wire format would be worse than
building nothing, because it would look finished. So this unit specifies the seam
and leaves the far side of it empty.

**What this means in practice:** `berp_lao` can build, validate and record a filing
today. When the Department publishes an interface, one class is written and one
site-config key changes. No accounting code moves.

---

## 2. Design

```
  Sales / Purchase Invoices
            │
            ▼
  lao_vat_return.py  ──────────►  the report a human reviews on screen
    _sales_net_by_type()
    _output_vat() / _input_vat()
            │
            ▼
  taxris/payload.py
    build_vat_return_payload()  ─►  VatReturnPayload   (schema berp_lao.vat_return.v1)
            │                          .check()  → reasons it is not fit to file
            ▼
  taxris/client.py
    get_client()  ─────────────►  TaxRISClient (abstract)
                                    └─ RecordingClient   (default; records, submits nothing)
                                    └─ <future live transport>
```

### 2.1 The payload reuses the report

`build_vat_return_payload` calls the same four query functions the Lao Monthly VAT
Return calls. This is deliberate. A separate extraction path would drift from the
report, and the first anyone would know is a mismatch between what was reviewed and
what was filed. One query path, two renderings.

### 2.2 The payload is not a wire format

`VatReturnPayload` is modelled on what the Lao VAT return requires — taxpayer,
period, and the split between standard-rated, zero-rated and exempt supplies
against reclaimable input VAT — not on any TaxRIS structure. Serialising it to
whatever TaxRIS accepts belongs in the transport. A wire-format change must never
reach the accounting code.

### 2.3 Default is inert

`get_client()` resolves `berp_lao_taxris_client` from `site_config.json` and falls
back to `RecordingClient`. A missing, misspelt or unloadable value therefore
resolves to the transport that submits nothing, never to a live one. Submitting to
a tax authority requires an explicit, deliberate configuration change.

### 2.4 Idempotency is the transport's contract

`submit_vat_return` must be idempotent on `(company, period_from, period_to)`. The
Lao return is filed once per period; a retry after a timeout must not create a
second filing. This is stated in the ABC because only the transport can honour it —
it depends on how the remote system deduplicates.

---

## 3. What ships

| Path | Role |
|---|---|
| `lao_regional/taxris/payload.py` | `VatReturnPayload`, `build_vat_return_payload`, `check()` |
| `lao_regional/taxris/client.py` | `TaxRISClient` ABC, `RecordingClient`, `get_client`, `preview_vat_return` |

`preview_vat_return` is whitelisted, read-only, and returns the payload, the list of
reasons it is not fit to file, and which transport is active. It is the call to wire
to a "Check VAT return" button.

---

## 4. What does not ship, and why

| Not built | Reason |
|---|---|
| A live transport | No published endpoint, schema or auth model. |
| An event outbox DocType | Premature: the outbox's columns are determined by the receipt format, which is unknown. `RecordingClient` logs receipts in the meantime. |
| Invoice-level e-invoicing | No evidence Lao PDR operates a clearance or real-time invoice reporting model. Do not assume one. |
| Scheduled auto-filing | Filing is an accountable act. It stays manual until a live transport exists and has been accepted. |

---

## 5. Open questions

| # | Question | Blocks |
|---|---|---|
| Q1 | Does TaxRIS expose any machine interface to taxpayers, or is it staff-facing only? | Everything below |
| Q2 | If yes: transport, schema, authentication, sandbox? | The live transport |
| Q3 | Is a filing receipt/acknowledgement returned, and in what form? | The outbox schema |
| Q4 | Is there a correction/amendment flow, or is a period refiled whole? | Idempotency strategy |
| Q5 | Does the Department recognise a third-party filing agent, and does BizEra need accreditation? | Whether this is legal to operate |

Q1 is the gate. Until it is answered by the Department rather than inferred, this
unit stays at Draft and nothing here is activated.

---

## 6. Acceptance

None of the following has been met; they are stated so that "done" is not
negotiated later.

- [ ] Q1–Q5 answered from a Tax Department source, not a secondary one.
- [ ] A live transport implemented against a published schema.
- [ ] Idempotency proven: the same period submitted twice yields one filing.
- [ ] A sandbox submission accepted and its receipt persisted.
- [ ] A Lao-qualified accountant confirms the payload matches the statutory return.

---

## 7. Sources

- Lao News Agency (KPL), *Laos Launches 2026 TaxRIS Training to Strengthen Revenue
  Administration* — TaxRIS scope, operator, 2026 rollout, PFM Reform Phase 3 funding.
- PwC Worldwide Tax Summaries, *Lao PDR — Corporate — Other taxes* (reviewed
  7 August 2026) — VAT 10%, automatic VAT registration on TIN issue, three-month
  input VAT claim window.
- PwC Worldwide Tax Summaries, *Lao PDR — Corporate — Withholding taxes* — the WHT
  schedule the app's categories are built from.
- VDB Loi, *Laos Alert — New Income Tax Law 2025 (effective 1 July 2026)* — the rate
  changes now carried as dated rows in `lao_regional/data/lao_tax_templates.json`.

None of these is a Tax Department integration specification. That is the point of
Q1.
