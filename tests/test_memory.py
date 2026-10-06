"""Tests for RAM, the direct-mapped cache and the buses."""
import unittest

from src.memory import Bus, Memory, MemoryAccessError


class TestMemory(unittest.TestCase):
    def setUp(self):
        self.mem = Memory(size=16, lines=4, bus=Bus(), hit_cycles=1, miss_cycles=5)
        for i in range(16):
            self.mem.ram[i] = i * 10

    def test_first_read_misses_second_hits(self):
        value, cycles = self.mem.read(3)
        self.assertEqual((value, cycles), (30, 5))
        value, cycles = self.mem.read(3)
        self.assertEqual((value, cycles), (30, 1))
        self.assertEqual((self.mem.hits, self.mem.misses), (1, 1))

    def test_direct_mapped_conflict(self):
        """Addresses 0 and 4 share cache line 0, so they evict each other."""
        self.mem.read(0)                       # miss
        self.assertEqual(self.mem.read(0)[1], 1)   # hit
        self.mem.read(4)                       # miss, evicts address 0
        self.assertEqual(self.mem.read(0)[1], 5)   # miss again
        self.assertEqual((self.mem.hits, self.mem.misses), (1, 3))

    def test_different_lines_do_not_conflict(self):
        for addr in (0, 1, 2, 3):
            self.mem.read(addr)
        for addr in (0, 1, 2, 3):
            self.assertEqual(self.mem.read(addr)[1], 1)

    def test_write_is_write_through(self):
        self.mem.read(2)                       # bring the line into the cache
        cycles = self.mem.write(2, 99)
        self.assertEqual(cycles, 5)            # writes always pay the RAM time
        self.assertEqual(self.mem.ram[2], 99)
        self.assertEqual(self.mem.read(2)[0], 99)   # cache line was updated too

    def test_write_miss_does_not_fill_the_cache(self):
        self.mem.write(6, 5)
        self.assertEqual(self.mem.ram[6], 5)
        self.assertEqual(self.mem.read(6)[1], 5)    # still a miss on the first read

    def test_hit_rate(self):
        self.assertEqual(self.mem.hit_rate, 0.0)
        self.mem.read(1)
        self.mem.read(1)
        self.mem.read(1)
        self.mem.read(1)
        self.assertAlmostEqual(self.mem.hit_rate, 0.75)

    def test_out_of_range_access_raises(self):
        with self.assertRaises(MemoryAccessError):
            self.mem.read(16)
        with self.assertRaises(MemoryAccessError):
            self.mem.write(-1, 0)

    def test_values_are_16_bit(self):
        self.mem.write(0, 0x12345)
        self.assertEqual(self.mem.ram[0], 0x2345)

    def test_device_write_keeps_cache_coherent_and_uncounted(self):
        self.mem.read(5)                       # cached
        before = (self.mem.hits, self.mem.misses)
        self.mem.device_write(5, 77)
        self.assertEqual((self.mem.hits, self.mem.misses), before)
        self.assertEqual(self.mem.read(5)[0], 77)

    def test_bus_records_last_transfer(self):
        self.mem.read(3)
        bus = self.mem.bus
        self.assertEqual((bus.address, bus.data, bus.control), (3, 30, "READ MISS"))
        self.mem.write(3, 8)
        self.assertEqual((bus.address, bus.data, bus.control), (3, 8, "WRITE HIT"))
        self.assertEqual(bus.flash, 1.0)
        bus.decay(1.0)
        self.assertEqual(bus.flash, 0.0)


if __name__ == "__main__":
    unittest.main()
