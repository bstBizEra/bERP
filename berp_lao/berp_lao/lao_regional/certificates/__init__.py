# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Statutory certificates a Lao business has to hand to somebody else.

Not reports. A report is a grid an accountant reads on screen; a certificate is a
document that leaves the building, carries two tax identification numbers and a
signature, and is the counterparty's evidence. The distinction matters here
because it decides the failure mode: a wrong report is noticed, a wrong
certificate is filed by the recipient and surfaces at their assessment.

Everything in this package therefore follows the same shape as
``lao_regional/e_filing``: a frozen dataclass for the content, a ``check()`` that
reports why the document is not fit to issue while it can still be fixed, and a
renderer that adds nothing the dataclass does not already carry.
"""
