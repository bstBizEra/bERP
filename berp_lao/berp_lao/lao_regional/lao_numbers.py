# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Lao numerals in words.

Frappe renders an invoice's amount in words through `frappe.utils.in_words`, which
calls `num2words(n, lang=frappe.local.lang)` and silently falls back to English when
the language is unsupported. num2words ships 56 languages; Lao is not one of them
(Thai and Vietnamese are). So a Lao statutory tax invoice prints its amount in
English words, which is not what a Lao invoice is expected to carry.

This module supplies the missing conversion.

Structure of the Lao numeral system
-----------------------------------
Lao names each power of ten up to a million, like Thai and unlike English:

    ສິບ 10   ຮ້ອຍ 100   ພັນ 1,000   ໝື່ນ 10,000   ແສນ 100,000   ລ້ານ 1,000,000

Above a million the system repeats in multiples of ລ້ານ, so 12,000,000 is
"ສິບສອງລ້ານ" — twelve million — rather than a new word.

Three irregularities matter, and all three are why this cannot be a table lookup:

1. **10 is ສິບ, not ໜຶ່ງສິບ.** The leading "one" is dropped in the tens.
2. **20 is ຊາວ, not ສອງສິບ.** Twenty has its own word.
3. **A trailing 1 becomes ເອັດ, not ໜຶ່ງ**, whenever anything precedes it —
   11 is ສິບເອັດ, 21 is ຊາວເອັດ, 101 is ໜຶ່ງຮ້ອຍເອັດ.

Provenance
----------
Written from the structure of the Lao numeral system, which follows the Thai pattern
closely. It has **not** been reviewed by a native speaker. `tests/test_lao_numbers.py`
pins the behaviour so a reviewer can correct the table and see exactly what changes.
See BERP-LAO-ROADMAP-001 §1.1.
"""

from __future__ import annotations

from frappe.utils import flt

from berp_lao.lao_regional.country import is_lao_company

#: Digits 1-9. Index 0 is unused: a zero digit contributes nothing to the reading.
UNITS = ("", "ໜຶ່ງ", "ສອງ", "ສາມ", "ສີ່", "ຫ້າ", "ຫົກ", "ເຈັດ", "ແປດ", "ເກົ້າ")

#: Powers of ten below one million, by digit position.
PLACES = ("", "ສິບ", "ຮ້ອຍ", "ພັນ", "ໝື່ນ", "ແສນ")

ZERO = "ສູນ"
TEN = "ສິບ"
TWENTY = "ຊາວ"
ONE_TRAILING = "ເອັດ"
MILLION = "ລ້ານ"

#: Currency words. LAK subdivides into 100 att, though att are not in circulation.
KIP = "ກີບ"
ATT = "ອັດ"
EXACTLY = "ຖ້ວນ"

MILLION_VALUE = 1_000_000


def _below_million(number: int, has_preceding: bool = False) -> str:
	"""
	Read an integer in 1..999,999.

	`has_preceding` says whether a higher group (a ລ້ານ count) was already read. It
	matters because the ເອັດ rule is about the whole number, not this group: the 1 in
	1,000,001 is ເອັດ even though it stands alone within its own group.
	"""
	digits = str(number)
	length = len(digits)
	out = []

	for index, digit_char in enumerate(digits):
		digit = int(digit_char)
		if digit == 0:
			continue

		position = length - index - 1  # 0 = units, 1 = tens, ...

		if position == 0:
			# A trailing 1 is ເອັດ whenever anything at all precedes it, here or in a
			# higher group.
			trailing_one = digit == 1 and (length > 1 or has_preceding)
			out.append(ONE_TRAILING if trailing_one else UNITS[digit])
		elif position == 1:
			if digit == 1:
				out.append(TEN)  # ສິບ, never ໜຶ່ງສິບ
			elif digit == 2:
				out.append(TWENTY)  # ຊາວ, never ສອງສິບ
			else:
				out.append(UNITS[digit] + TEN)
		else:
			out.append(UNITS[digit] + PLACES[position])

	return "".join(out)


def lao_in_words(number: int) -> str:
	"""
	Return `number` written out in Lao.

	Handles zero, and any magnitude: above a million the number is read as a count
	of ລ້ານ followed by the remainder, which recurses for very large values.

	    >>> lao_in_words(0)
	    'ສູນ'
	    >>> lao_in_words(11)
	    'ສິບເອັດ'
	    >>> lao_in_words(1200000)
	    'ໜຶ່ງລ້ານສອງແສນ'
	"""
	number = int(number)
	if number < 0:
		raise ValueError("lao_in_words does not read negative numbers")
	if number == 0:
		return ZERO

	if number < MILLION_VALUE:
		return _below_million(number)

	millions, remainder = divmod(number, MILLION_VALUE)
	out = lao_in_words(millions) + MILLION
	if remainder:
		out += _below_million(remainder, has_preceding=True)
	return out


def lao_money_in_words(amount: float, currency: str = "LAK") -> str:
	"""
	Return a monetary amount written out in Lao, for an invoice.

	A whole amount is closed with ຖ້ວນ ("exactly"), which is what a Lao invoice
	carries in place of the English "only". Att are read when present, even though
	they are not in circulation, because ERPNext permits two decimal places on LAK.

	    >>> lao_money_in_words(1200000)
	    'ໜຶ່ງລ້ານສອງແສນກີບຖ້ວນ'
	    >>> lao_money_in_words(1500.50)
	    'ໜຶ່ງພັນຫ້າຮ້ອຍກີບຫ້າສິບອັດ'
	"""
	if currency != "LAK":
		raise ValueError(f"lao_money_in_words handles LAK only, not {currency}")

	amount = flt(amount, 2)
	if amount < 0:
		raise ValueError("lao_money_in_words does not read negative amounts")

	whole = int(amount)
	att = round((amount - whole) * 100)
	if att == 100:  # rounding carried into the whole part
		whole += 1
		att = 0

	out = lao_in_words(whole) + KIP
	if att:
		return out + lao_in_words(att) + ATT
	return out + EXACTLY


def set_lao_in_words(doc, method=None):
	"""
	doc_events hook: rewrite `in_words` in Lao on a Lao company's LAK invoice.

	Runs after the controller's own `validate`, because Frappe composes doc_events
	hooks to run after the document's method — so ERPNext has already set the English
	text by this point and this replaces it.

	Only touches documents that are both a Lao company's and denominated in LAK. A
	Lao company invoicing in USD keeps ERPNext's English wording, which is correct:
	the Lao reading is specific to kip.
	"""
	if not is_lao_company(doc.get("company")):
		return

	if doc.get("currency") == "LAK":
		total = doc.get("rounded_total") or doc.get("grand_total")
		if total:
			doc.in_words = lao_money_in_words(total)

	base_total = doc.get("base_rounded_total") or doc.get("base_grand_total")
	if base_total:
		doc.base_in_words = lao_money_in_words(base_total)
