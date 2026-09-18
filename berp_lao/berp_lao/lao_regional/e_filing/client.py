# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Transport for Lao government submissions.

No live transport ships with this app. What ships is the contract a transport has
to satisfy, plus a recording implementation that writes what would have been sent.

Configure per surface in site_config.json:

    "berp_lao_dtax_client":      "some.module.DTaxClient"
    "berp_lao_e_invoice_client": "some.module.EInvoiceClient"

THE SAFETY PROPERTY
    Anything not explicitly configured resolves to :class:`RecordingClient`. A
    misspelt key, a missing key, an empty string — all of them land on the inert
    recorder. A configuration mistake must never be able to submit to a tax
    authority, so the failure direction is chosen deliberately: unconfigured means
    *record*, never *send*.

    The one case that raises rather than falling back is a key that names something
    real but wrong — a dotted path that does not import, or that is not a transport
    of the required kind. Silently recording there would hide a genuine
    misconfiguration behind the same quiet success as the default.

TWO INTERFACES, NOT ONE
    A transport that can file a VAT return to DTax has no reason to also issue
    e-tax invoices, and vice versa. Splitting the abstract classes means a future
    implementer satisfies exactly the one they are building, rather than stubbing
    the other to get the import to work.
"""

from __future__ import annotations

import abc
import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

from berp_lao.lao_regional.e_filing.e_invoice import EInvoicePayload
from berp_lao.lao_regional.e_filing.vat_return import VatReturnPayload

DEFAULT_CLIENT = "berp_lao.lao_regional.e_filing.client.RecordingClient"

#: Site-config key per surface. Both default to the inert recorder.
CONFIG_KEYS = {
	"vat_return": "berp_lao_dtax_client",
	"e_invoice": "berp_lao_e_invoice_client",
}


class LaoFilingError(frappe.ValidationError):
	"""A submission was attempted and did not succeed."""


class LaoFilingNotConfigured(LaoFilingError):
	"""A transport was named in site config and could not be used."""


class LaoFilingClient:
	"""What every transport has, whichever surface it serves.

	Not an ABC. It declares no obligation, so making it one would only produce a
	class that is abstract in name and instantiable in fact. The obligations live on
	the two interfaces below, each an ABC in its own right; this carries the shared
	state and the one method both want.
	"""

	#: Set True only on a transport that actually reaches a Lao government system.
	is_live = False

	def describe(self) -> str:
		"""A dotted path a support engineer can act on."""
		return f"{type(self).__module__}.{type(self).__qualname__}"


class VatReturnTransport(LaoFilingClient, abc.ABC):
	"""Files a periodic VAT return (DTax).

	``submit_vat_return`` must be idempotent on ``(company, period_from,
	period_to)``: the Lao return is filed once per period, and a retry after a
	network failure must not create a second filing.
	"""

	@abc.abstractmethod
	def submit_vat_return(self, payload: VatReturnPayload) -> dict[str, Any]:
		"""Submit one VAT return. Returns a receipt dict; raises LaoFilingError."""


class EInvoiceTransport(LaoFilingClient, abc.ABC):
	"""Issues one e-tax invoice (E-Tax Invoice system).

	``issue_e_invoice`` must be idempotent on the invoice name. An issued invoice
	that is later cancelled is a credit note in Lao practice, not a re-issue, so a
	transport must never treat a retry as a new document.
	"""

	@abc.abstractmethod
	def issue_e_invoice(self, payload: EInvoicePayload) -> dict[str, Any]:
		"""Issue one e-tax invoice. Returns a receipt dict; raises LaoFilingError."""


class RecordingClient(VatReturnTransport, EInvoiceTransport):
	"""Records what would be submitted, and submits nothing.

	This is the default, and it is what makes the rest of the pipeline testable: the
	payload is built, checked and logged exactly as it would be for a real filing,
	and the only missing step is the one that has no published interface.
	"""

	is_live = False

	def submit_vat_return(self, payload: VatReturnPayload) -> dict[str, Any]:
		self._refuse_if_unfit(payload, _("This VAT return is not fit to file:"))
		return self._record(
			"vat_return",
			{
				"company": payload.company,
				"period": [payload.period_from, payload.period_to],
				"net_vat_payable": payload.net_vat_payable,
			},
		)

	def issue_e_invoice(self, payload: EInvoicePayload) -> dict[str, Any]:
		self._refuse_if_unfit(payload, _("This invoice is not fit to issue:"))
		return self._record(
			"e_invoice",
			{
				"company": payload.company,
				"invoice_no": payload.invoice_no,
				"invoice_date": payload.invoice_date,
				"grand_total": payload.grand_total,
			},
		)

	@staticmethod
	def _refuse_if_unfit(payload, preamble: str) -> None:
		problems = payload.check()
		if problems:
			raise LaoFilingError(preamble + "\n- " + "\n- ".join(problems))

	def _record(self, kind: str, detail: dict[str, Any]) -> dict[str, Any]:
		receipt = {
			"status": "recorded",
			"kind": kind,
			"transport": self.describe(),
			"recorded_at": str(now_datetime()),
			**detail,
		}
		frappe.logger("berp_lao").info(
			f"berp_lao.e_filing: recorded {kind} " + json.dumps(receipt, ensure_ascii=False, default=str)
		)
		return receipt


_INTERFACES: dict[str, type[LaoFilingClient]] = {
	"vat_return": VatReturnTransport,
	"e_invoice": EInvoiceTransport,
}


def get_client(kind: str = "vat_return") -> LaoFilingClient:
	"""Resolve the configured transport for `kind`, defaulting to RecordingClient."""
	interface = _INTERFACES.get(kind)
	if interface is None:
		raise LaoFilingNotConfigured(
			_("Unknown filing surface {0}; expected one of {1}.").format(kind, ", ".join(sorted(_INTERFACES)))
		)

	dotted = frappe.conf.get(CONFIG_KEYS[kind]) or DEFAULT_CLIENT

	try:
		cls = frappe.get_attr(dotted)
	except Exception as exc:
		raise LaoFilingNotConfigured(
			_("Lao filing transport {0} could not be loaded: {1}").format(dotted, exc)
		) from exc

	if not (isinstance(cls, type) and issubclass(cls, interface)):
		raise LaoFilingNotConfigured(
			_("Lao filing transport {0} is not a {1}.").format(dotted, interface.__name__)
		)

	return cls()


@frappe.whitelist()
def preview_vat_return(company: str, from_date: str, to_date: str) -> dict[str, Any]:
	"""Build the filing payload and report what would stop it being filed.

	Read-only: submits nothing, writes nothing. This is the call to wire to a
	"Check VAT return" button.
	"""
	frappe.only_for(("System Manager", "Accounts Manager"))

	from berp_lao.lao_regional.e_filing.vat_return import build_vat_return_payload

	payload = build_vat_return_payload(company, from_date, to_date)
	client = get_client("vat_return")
	return {
		"payload": payload.as_dict(),
		"problems": payload.check(),
		"transport": client.describe(),
		"is_live": client.is_live,
	}


@frappe.whitelist()
def preview_e_invoice(sales_invoice: str) -> dict[str, Any]:
	"""Build the e-tax-invoice payload for one Sales Invoice and check it.

	Read-only. Wire this to a "Check e-tax invoice" button so the statutory content
	is verified while the invoice is still amendable, rather than at submission.
	"""
	frappe.only_for(("System Manager", "Accounts Manager", "Accounts User"))

	from berp_lao.lao_regional.e_filing.e_invoice import build_e_invoice_payload

	payload = build_e_invoice_payload(sales_invoice)
	client = get_client("e_invoice")
	return {
		"payload": payload.as_dict(),
		"problems": payload.check(),
		"transport": client.describe(),
		"is_live": client.is_live,
	}
