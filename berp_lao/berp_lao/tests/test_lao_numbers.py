# Copyright (c) 2026, BizEra / BSTBizEra and contributors
# License: GNU General Public License v3. See license.txt

"""
Tests for Lao numerals in words.

These pin every irregularity in the Lao numeral system explicitly, so that a native
speaker reviewing `lao_numbers.py` can see exactly which readings the code commits to
and correct any that are wrong — a failing assertion names the number and both
readings. See BERP-LAO-ROADMAP-001 §1.1.
"""

try:  # Frappe v16+
	from frappe.tests import IntegrationTestCase as _TestCase
except ImportError:  # Frappe v15
	from frappe.tests.utils import FrappeTestCase as _TestCase

from berp_lao.lao_regional.lao_numbers import (
	MILLION_VALUE,
	lao_in_words,
	lao_money_in_words,
)


class TestLaoDigits(_TestCase):
	def test_zero(self):
		self.assertEqual(lao_in_words(0), "ສູນ")

	def test_one_to_nine(self):
		expected = ["ໜຶ່ງ", "ສອງ", "ສາມ", "ສີ່", "ຫ້າ", "ຫົກ", "ເຈັດ", "ແປດ", "ເກົ້າ"]
		for number, word in enumerate(expected, start=1):
			with self.subTest(number=number):
				self.assertEqual(lao_in_words(number), word)


class TestLaoIrregularities(_TestCase):
	"""The three rules that make this more than a table lookup."""

	def test_ten_drops_the_leading_one(self):
		"""10 is ສິບ, never ໜຶ່ງສິບ."""
		self.assertEqual(lao_in_words(10), "ສິບ")
		self.assertNotIn("ໜຶ່ງສິບ", lao_in_words(10))

	def test_twenty_has_its_own_word(self):
		"""20 is ຊາວ, never ສອງສິບ."""
		self.assertEqual(lao_in_words(20), "ຊາວ")
		self.assertNotIn("ສອງສິບ", lao_in_words(20))

	def test_thirty_onwards_is_regular(self):
		for number, word in ((30, "ສາມສິບ"), (40, "ສີ່ສິບ"), (90, "ເກົ້າສິບ")):
			with self.subTest(number=number):
				self.assertEqual(lao_in_words(number), word)

	def test_trailing_one_becomes_et(self):
		"""A trailing 1 is ເອັດ whenever anything precedes it."""
		for number, word in (
			(1, "ໜຶ່ງ"),  # nothing precedes it
			(11, "ສິບເອັດ"),
			(21, "ຊາວເອັດ"),
			(31, "ສາມສິບເອັດ"),
			(101, "ໜຶ່ງຮ້ອຍເອັດ"),
			(1001, "ໜຶ່ງພັນເອັດ"),
		):
			with self.subTest(number=number):
				self.assertEqual(lao_in_words(number), word)


class TestLaoPlaces(_TestCase):
	def test_each_power_of_ten_has_its_own_word(self):
		for number, word in (
			(100, "ໜຶ່ງຮ້ອຍ"),
			(1_000, "ໜຶ່ງພັນ"),
			(10_000, "ໜຶ່ງໝື່ນ"),
			(100_000, "ໜຶ່ງແສນ"),
			(1_000_000, "ໜຶ່ງລ້ານ"),
		):
			with self.subTest(number=number):
				self.assertEqual(lao_in_words(number), word)

	def test_compound_numbers(self):
		for number, word in (
			(111, "ໜຶ່ງຮ້ອຍສິບເອັດ"),
			(120, "ໜຶ່ງຮ້ອຍຊາວ"),
			(1_200, "ໜຶ່ງພັນສອງຮ້ອຍ"),
			(120_000, "ໜຶ່ງແສນສອງໝື່ນ"),
			(1_200_000, "ໜຶ່ງລ້ານສອງແສນ"),
		):
			with self.subTest(number=number):
				self.assertEqual(lao_in_words(number), word)

	def test_zero_digits_are_skipped_not_spoken(self):
		"""1,000,001 must not read a string of ສູນ between the places."""
		self.assertEqual(lao_in_words(1_000_001), "ໜຶ່ງລ້ານເອັດ")
		self.assertNotIn("ສູນ", lao_in_words(1_000_001))

	def test_above_a_million_counts_millions(self):
		"""The system repeats in multiples of ລ້ານ rather than naming a new power."""
		self.assertEqual(lao_in_words(12_000_000), "ສິບສອງລ້ານ")
		self.assertEqual(lao_in_words(2 * MILLION_VALUE), "ສອງລ້ານ")

	def test_very_large_numbers_recurse(self):
		result = lao_in_words(1_000_000_000_000)
		self.assertTrue(result.endswith("ລ້ານ"))
		self.assertNotIn("None", result)


class TestLaoMoney(_TestCase):
	def test_whole_amounts_close_with_exactly(self):
		self.assertEqual(lao_money_in_words(1_200_000), "ໜຶ່ງລ້ານສອງແສນກີບຖ້ວນ")
		self.assertEqual(lao_money_in_words(500_000), "ຫ້າແສນກີບຖ້ວນ")

	def test_zero(self):
		self.assertEqual(lao_money_in_words(0), "ສູນກີບຖ້ວນ")

	def test_att_are_read_when_present(self):
		result = lao_money_in_words(1_500.50)
		self.assertIn("ອັດ", result)
		self.assertNotIn("ຖ້ວນ", result)  # not a whole amount
		self.assertEqual(result, "ໜຶ່ງພັນຫ້າຮ້ອຍກີບຫ້າສິບອັດ")

	def test_rounding_carries_into_the_kip(self):
		"""0.999 rounds to 1.00 — the att must not read as 100."""
		result = lao_money_in_words(0.999)
		self.assertEqual(result, "ໜຶ່ງກີບຖ້ວນ")

	def test_rejects_other_currencies(self):
		with self.assertRaises(ValueError):
			lao_money_in_words(100, currency="USD")

	def test_rejects_negative_amounts(self):
		with self.assertRaises(ValueError):
			lao_money_in_words(-1)
		with self.assertRaises(ValueError):
			lao_in_words(-1)


class TestAgainstTheEnglishFallback(_TestCase):
	def test_output_is_lao_script_not_latin(self):
		"""
		The whole point: num2words has no Lao, so Frappe's in_words() falls back to
		English. Anything Latin in the output means the fallback leaked through.
		"""
		for number in (0, 11, 1_200_000):
			result = lao_in_words(number)
			with self.subTest(number=number):
				self.assertTrue(all(not c.isascii() or not c.isalpha() for c in result))
				self.assertTrue(any("຀" <= c <= "໿" for c in result))
