# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Lao government filing interfaces — seams only, no live transport.

WHY THIS PACKAGE IS NO LONGER CALLED ``taxris``
    It was, and the name was wrong. BERP-LAO-MARKET-001 §3 established that TaxRIS
    is the **tax administration's internal** system — taxpayer records, notices,
    audit memoranda, operated by tax officers, with an eight-round 2026 training
    programme for district offices. It is not and was never going to be a taxpayer
    API. Renamed while the package was still inert and nothing imported it; after a
    client is built against it, this becomes a breaking rename with a migration.

THE TWO TAXPAYER-FACING SURFACES
    ADR-A3 as proposed said "rename to ``e_invoice`` and retarget the payload
    builder to e-tax-invoice issuance". Implementing it literally would have thrown
    away correct work, because there are **two** surfaces, not one, and the existing
    payload serves the other:

    ===============  =====================================  ====================
    Surface          What a taxpayer does with it           Module here
    ===============  =====================================  ====================
    DTax             registration, and periodic filing      ``vat_return.py``
    E-Tax Invoice    per-invoice issuance; launched by the  ``e_invoice.py``
                     Ministry of Finance on 29 May 2026
    ===============  =====================================  ====================

    So the package is named for what it does — filing to the Lao government — and
    each surface gets its own payload. See the ADR-A3 amendment note.

WHAT SHIPS, AND WHAT DELIBERATELY DOES NOT
    No live transport ships, and none should until an interface is published and
    BizEra holds credentials for it. What ships is the seam: a stable internal
    representation of each submission, a ``check()`` that reports why it is not fit
    to send, an abstract transport, and an inert recorder that writes what *would*
    have been sent. A missing or misspelt configuration value resolves to the inert
    recorder, never to a live one — a configuration mistake must not be able to
    reach a tax authority.

    Neither payload is modelled on a wire format, because neither format is
    published. They are modelled on what Lao statute requires the document to
    contain, which is knowable and stable. Mapping either onto a wire format is a
    serialiser's job, so that a format change never reaches the accounting code.

See docs/BERP-LAO-TAXRIS-001.md, which keeps its number — it is a published
identifier — and carries the amendment.
"""

from berp_lao.lao_regional.e_filing.client import (
	EInvoiceTransport,
	LaoFilingClient,
	LaoFilingError,
	LaoFilingNotConfigured,
	RecordingClient,
	VatReturnTransport,
	get_client,
)
from berp_lao.lao_regional.e_filing.e_invoice import (
	EInvoiceLine,
	EInvoicePayload,
	build_e_invoice_payload,
)
from berp_lao.lao_regional.e_filing.vat_return import (
	VatReturnPayload,
	build_vat_return_payload,
)

__all__ = [
	"EInvoiceLine",
	"EInvoicePayload",
	"EInvoiceTransport",
	"LaoFilingClient",
	"LaoFilingError",
	"LaoFilingNotConfigured",
	"RecordingClient",
	"VatReturnPayload",
	"VatReturnTransport",
	"build_e_invoice_payload",
	"build_vat_return_payload",
	"get_client",
]
