# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Where Lao statute meets an ERPNext document.

Every function registered in ``hooks.doc_events`` lives under this package, one
module per DocType it acts on. Each returns immediately unless the document's
company is Lao, so a multi-country site pays almost nothing for having this app
installed.

THE CHECKS WARN; THEY DO NOT BLOCK
    Lao VAT and WHT treatment depends on facts ERPNext does not model — supplier
    residency, goods versus services, exemption certificates — so a hard block on
    submission would stop legitimate invoices. Every rule here raises a message and
    lets the document through. Anything that genuinely must not post belongs in
    ERPNext's own validation, not here.

THE SHARED CONSTANTS
    Statutory thresholds and rates live in this ``__init__`` rather than in one of
    the rule modules, because several of them are cited by more than one rule and
    by the e-filing payloads. A rate or threshold change is a change here and
    nowhere else.
"""

#: The Lao standard VAT rate (Presidential Decree 003/PS, effective 1 May 2024).
VAT_STANDARD_RATE = 10.0

#: Lao Revenue Department: VAT invoices at or above this value must record the
#: customer's TIN.
TIN_REQUIRED_THRESHOLD_LAK = 500_000

#: Invoice types that carry no output VAT.
NON_VATABLE_INVOICE_TYPES = ("Export (0%)", "VAT Exempt")

#: Law on Income Tax No. 88/NA (in force 1 July 2026): an expense above this
#: value per invoice is deductible only if it was settled through a Lao
#: commercial bank account, so cash-settled invoices above it are a CIT risk.
BANK_SETTLEMENT_THRESHOLD_LAK = 1_000_000

#: Modes of payment that are not a bank transfer for the rule above.
CASH_MODE_TYPES = ("Cash",)

#: Input VAT is claimable only within this many months of the date incurred.
#: The claim is simply refused after that, and nothing in ERPNext would say so.
INPUT_VAT_CLAIM_WINDOW_MONTHS = 3
