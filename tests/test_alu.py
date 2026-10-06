"""Tests for the ALU: add, compare (flags) and maximum."""
import unittest

from src.cpu import ALU


class TestALU(unittest.TestCase):
    def setUp(self):
        self.alu = ALU()

    def test_add(self):
        self.assertEqual(self.alu.add(3, 4), 7)

    def test_add_wraps_at_16_bits(self):
        self.assertEqual(self.alu.add(0xFFFF, 1), 0)
        self.assertEqual(self.alu.add(0xFFFF, 2), 1)

    def test_compare_equal_sets_zero(self):
        f = self.alu.compare(5, 5)
        self.assertEqual(f.as_tuple(), (True, False, False))

    def test_compare_greater(self):
        f = self.alu.compare(9, 2)
        self.assertEqual(f.as_tuple(), (False, True, False))

    def test_compare_less(self):
        f = self.alu.compare(2, 9)
        self.assertEqual(f.as_tuple(), (False, False, True))

    def test_compare_replaces_old_flags(self):
        self.alu.compare(9, 2)
        self.alu.compare(1, 1)
        self.assertEqual(self.alu.flags.as_tuple(), (True, False, False))

    def test_maximum_returns_index_and_value(self):
        self.assertEqual(self.alu.maximum([3, 8, 5, 1]), (1, 8))
        self.assertEqual(self.alu.maximum([0, 0, 0, 7]), (3, 7))

    def test_maximum_tie_keeps_lowest_index(self):
        self.assertEqual(self.alu.maximum([4, 9, 9, 2]), (1, 9))
        self.assertEqual(self.alu.maximum([0, 0, 0, 0]), (0, 0))

    def test_maximum_uses_the_comparator(self):
        self.alu.maximum([1, 2, 3, 4])
        self.assertTrue(self.alu.flags.greater)       # last comparison: 4 > 3


if __name__ == "__main__":
    unittest.main()
