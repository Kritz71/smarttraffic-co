"""RAM, a small direct-mapped cache, and the buses.

Memory map (data RAM, 16 words):

    0-3  AGE_N .. AGE_W   how long each road has been waiting (written by a timer)
    4    BASE_GREEN       seconds added to every green time
    5    LAST_SEL         the last road the CPU chose
    6    AMB_DIR          road with the ambulance (written by the interrupt controller)
    7    EMERGENCY_GREEN  seconds of priority green

Instructions live in a separate program ROM (a simplified Harvard design), so
instruction fetches do not use these data buses.
"""
from . import config as C

ADDR_AGE_N, ADDR_AGE_S, ADDR_AGE_E, ADDR_AGE_W = 0, 1, 2, 3
ADDR_BASE_GREEN = 4
ADDR_LAST_SEL = 5
ADDR_AMB_DIR = 6
ADDR_EMERGENCY_GREEN = 7

SYMBOLS = {
    "AGE_N": ADDR_AGE_N, "AGE_S": ADDR_AGE_S,
    "AGE_E": ADDR_AGE_E, "AGE_W": ADDR_AGE_W,
    "BASE_GREEN": ADDR_BASE_GREEN, "LAST_SEL": ADDR_LAST_SEL,
    "AMB_DIR": ADDR_AMB_DIR, "EMERGENCY_GREEN": ADDR_EMERGENCY_GREEN,
}
ADDR_NAMES = {addr: name for name, addr in SYMBOLS.items()}

WORD_MASK = 0xFFFF


class MemoryAccessError(Exception):
    """Raised when a program touches an address that does not exist."""


class Bus:
    """The address / data / control buses. Records the latest transfer."""

    def __init__(self):
        self.address = 0
        self.data = 0
        self.control = "IDLE"
        self.flash = 0.0        # 1.0 right after a transfer, fades to 0

    def record(self, address, data, control):
        self.address, self.data, self.control = address, data, control
        self.flash = 1.0

    def decay(self, dt):
        self.flash = max(0.0, self.flash - dt * 3.0)


class CacheLine:
    __slots__ = ("valid", "tag", "data")

    def __init__(self):
        self.valid = False
        self.tag = 0
        self.data = 0


class Memory:
    """RAM + cache. Direct-mapped, one word per line, write-through.

    index = address mod lines, tag = address div lines.
    Reads: hit costs 1 cycle, miss costs 5 (the line is then loaded).
    Writes: always go to RAM (5 cycles); a hit also updates the cache line;
    a write miss does not load the line (no write-allocate).
    """

    def __init__(self, size=C.RAM_SIZE, lines=C.CACHE_LINES, bus=None,
                 hit_cycles=C.CACHE_HIT_CYCLES, miss_cycles=C.CACHE_MISS_CYCLES):
        self.size = size
        self.ram = [0] * size
        self.cache = [CacheLine() for _ in range(lines)]
        self.bus = bus if bus is not None else Bus()
        self.hit_cycles = hit_cycles
        self.miss_cycles = miss_cycles
        self.hits = 0
        self.misses = 0
        self.last_hit = None

    # ---- helpers ----
    def _check(self, addr):
        if not 0 <= addr < self.size:
            raise MemoryAccessError(f"address {addr} is outside RAM (0-{self.size - 1})")

    def _slot(self, addr):
        n = len(self.cache)
        return self.cache[addr % n], addr // n

    # ---- CPU accesses ----
    def read(self, addr):
        """Return (value, cycles)."""
        self._check(addr)
        line, tag = self._slot(addr)
        if line.valid and line.tag == tag:
            self.hits += 1
            hit, value, cycles = True, line.data, self.hit_cycles
        else:
            self.misses += 1
            hit, value, cycles = False, self.ram[addr], self.miss_cycles
            line.valid, line.tag, line.data = True, tag, value
        self.last_hit = hit
        self.bus.record(addr, value, "READ HIT" if hit else "READ MISS")
        return value, cycles

    def write(self, addr, value):
        """Write-through. Returns cycles."""
        self._check(addr)
        value &= WORD_MASK
        line, tag = self._slot(addr)
        hit = line.valid and line.tag == tag
        self.ram[addr] = value
        if hit:
            line.data = value
            self.hits += 1
        else:
            self.misses += 1
        self.last_hit = hit
        self.bus.record(addr, value, "WRITE HIT" if hit else "WRITE MISS")
        return self.miss_cycles

    # ---- device accesses (timer, interrupt controller) ----
    def device_write(self, addr, value):
        """A peripheral updates RAM directly. Keeps the cache coherent and
        does not count as a CPU access."""
        self._check(addr)
        value &= WORD_MASK
        self.ram[addr] = value
        line, tag = self._slot(addr)
        if line.valid and line.tag == tag:
            line.data = value

    def peek(self, addr):
        self._check(addr)
        return self.ram[addr]

    # ---- statistics ----
    @property
    def accesses(self):
        return self.hits + self.misses

    @property
    def hit_rate(self):
        return self.hits / self.accesses if self.accesses else 0.0
