"""The virtual CPU: registers, PC, IR, ALU, control unit and instruction set.

Instruction word (16 bits):   [ opcode:4 | A:4 | B:8 ]

    HALT                          stop the CPU
    READ_SENSOR Rd, port          Rd <- sensor count of road `port`        (I/O read)
    LOAD  Rd, [addr]              Rd <- RAM[addr]                          (via cache)
    STORE Rs, [addr]              RAM[addr] <- Rs                          (write-through)
    ADD   Rd, Rs                  Rd <- Rd + Rs
    CMP   Ra, Rb                  set flags ZERO / GREATER / LESS from Ra - Rb
    MAX   Rd, Rv                  ALU compares R0..R3: Rd <- index, Rv <- value of the largest
    JMP   target                  PC <- target
    WRITE_SIGNAL Rdir, Rgreen     ask the lights for a green phase         (I/O write)
    IRET                          return from the interrupt routine

The control unit runs one phase per clock tick: FETCH, DECODE, EXECUTE
(plus extra MEMORY ticks while the cache or I/O is slow). Interrupts are
checked at the start of every FETCH.
"""
from . import config as C
from .memory import ADDR_NAMES, WORD_MASK

REG_COUNT = C.NUM_REGISTERS

OPCODES = {"HALT": 0, "READ_SENSOR": 1, "LOAD": 2, "STORE": 3, "ADD": 4,
           "CMP": 5, "MAX": 6, "JMP": 7, "WRITE_SIGNAL": 8, "IRET": 9}
MNEMONICS = {code: name for name, code in OPCODES.items()}
FORMATS = {
    "HALT": (), "IRET": (), "JMP": ("target",),
    "READ_SENSOR": ("reg", "port"), "LOAD": ("reg", "mem"), "STORE": ("reg", "mem"),
    "ADD": ("reg", "reg"), "CMP": ("reg", "reg"), "MAX": ("reg", "reg"),
    "WRITE_SIGNAL": ("reg", "reg"),
}

# Phases shown on the dashboard
FETCH, DECODE, EXECUTE, MEMORY, IRQ, HALTED = (
    "FETCH", "DECODE", "EXECUTE", "MEMORY", "IRQ", "HALTED")


class AssemblerError(Exception):
    pass


class CPUError(Exception):
    pass


# ------------------------------------------------------------------- ALU ----
class Flags:
    __slots__ = ("zero", "greater", "less")

    def __init__(self, zero=False, greater=False, less=False):
        self.zero, self.greater, self.less = zero, greater, less

    def copy(self):
        return Flags(self.zero, self.greater, self.less)

    def as_tuple(self):
        return (self.zero, self.greater, self.less)


class ALU:
    """Arithmetic/logic unit with the flag register."""

    def __init__(self):
        self.flags = Flags()

    def add(self, a, b):
        return (a + b) & WORD_MASK

    def compare(self, a, b):
        self.flags = Flags(zero=a == b, greater=a > b, less=a < b)
        return self.flags

    def maximum(self, values):
        """Return (index, value) of the largest value. Ties keep the lowest
        index. Uses compare(), so the flags show the last comparison made."""
        best = 0
        for i in range(1, len(values)):
            if self.compare(values[i], values[best]).greater:
                best = i
        return best, values[best]


# ------------------------------------------------------ assembler / disasm --
def encode(opcode, a=0, b=0):
    return (opcode << 12) | (a << 8) | b


def decode(word):
    opcode, a, b = (word >> 12) & 0xF, (word >> 8) & 0xF, word & 0xFF
    if opcode not in MNEMONICS:
        raise CPUError(f"illegal opcode {opcode} in word 0x{word:04X}")
    return opcode, a, b


def disassemble(word):
    opcode, a, b = decode(word)
    name = MNEMONICS[opcode]
    mem = lambda addr: f"[{ADDR_NAMES.get(addr, addr)}]"
    kinds = FORMATS[name]
    if not kinds:
        return name
    if kinds == ("target",):
        return f"{name} {b}"
    first = f"R{a}"
    second = {"reg": f"R{b}", "port": str(b), "mem": mem(b)}[kinds[1]]
    return f"{name} {first}, {second}"


def _number(token, labels, symbols, lineno):
    try:
        value = int(token, 0)
    except ValueError:
        key = token.upper()
        if key in labels:
            value = labels[key]
        elif key in symbols:
            value = symbols[key]
        else:
            raise AssemblerError(f"line {lineno}: unknown name '{token}'")
    if not 0 <= value <= 255:
        raise AssemblerError(f"line {lineno}: value {value} does not fit in 8 bits")
    return value


def _operand(kind, token, labels, symbols, lineno):
    if kind == "reg":
        t = token.upper()
        if len(t) > 1 and t[0] == "R" and t[1:].isdigit() and int(t[1:]) < REG_COUNT:
            return int(t[1:])
        raise AssemblerError(f"line {lineno}: '{token}' is not a register (R0-R{REG_COUNT - 1})")
    if kind == "mem":
        if not (token.startswith("[") and token.endswith("]")):
            raise AssemblerError(f"line {lineno}: memory operand must look like [ADDR], got '{token}'")
        return _number(token[1:-1], labels, symbols, lineno)
    return _number(token, labels, symbols, lineno)       # port / target


def assemble(source, symbols=None):
    """Turn assembly text into a list of 16-bit words.

    Returns (words, labels). Labels map NAME -> instruction address.
    """
    symbols = {k.upper(): v for k, v in (symbols or {}).items()}
    items, labels = [], {}
    for lineno, raw in enumerate(source.splitlines(), 1):       # pass 1
        line = raw.split(";")[0].strip()
        while ":" in line:
            label, _, line = line.partition(":")
            label = label.strip().upper()
            if not label.isidentifier():
                raise AssemblerError(f"line {lineno}: bad label '{label}'")
            if label in labels:
                raise AssemblerError(f"line {lineno}: label '{label}' defined twice")
            labels[label] = len(items)
            line = line.strip()
        if line:
            parts = line.replace(",", " ").split()
            items.append((lineno, parts[0].upper(), parts[1:]))

    words = []
    for lineno, mnemonic, ops in items:                         # pass 2
        if mnemonic not in OPCODES:
            raise AssemblerError(f"line {lineno}: unknown instruction '{mnemonic}'")
        kinds = FORMATS[mnemonic]
        if len(ops) != len(kinds):
            raise AssemblerError(
                f"line {lineno}: {mnemonic} needs {len(kinds)} operand(s), got {len(ops)}")
        values = [_operand(k, t, labels, symbols, lineno) for k, t in zip(kinds, ops)]
        if not values:
            a = b = 0
        elif len(values) == 1:
            a, b = 0, values[0]
        else:
            a, b = values
        if mnemonic == "MAX" and a == b:
            raise AssemblerError(f"line {lineno}: MAX needs two different registers")
        words.append(encode(OPCODES[mnemonic], a, b))
    return words, labels


# ------------------------------------------------------------------- CPU ----
class CPU:
    """Registers R0-R5, PC, IR, ALU + flags and the control unit."""

    def __init__(self, memory, program, io, interrupts=None, isr_addr=None):
        self.memory = memory
        self.program = list(program)
        self.io = io                     # needs read_sensor(port) and write_signal(dir, green, emergency)
        self.interrupts = interrupts
        self.isr_addr = isr_addr
        self.alu = ALU()
        self.reset()

    def reset(self):
        self.regs = [0] * REG_COUNT
        self.pc = 0
        self.ir = 0
        self.exec_pc = 0                 # address of the instruction being executed
        self.decoded = (0, 0, 0)
        self.phase = FETCH
        self.stall = 0
        self.halted = False
        self.in_isr = False
        self.saved = None                # state saved by the interrupt hardware
        self.cycles = 0
        self.instructions = 0
        self.interrupt_count = 0
        self.alu.flags = Flags()

    @property
    def flags(self):
        return self.alu.flags

    @property
    def cpi(self):
        return self.cycles / self.instructions if self.instructions else 0.0

    def current_index(self):
        """Program address to highlight on the dashboard."""
        if self.phase in (DECODE, EXECUTE, MEMORY):
            return self.exec_pc
        return self.pc

    # ---- one clock tick ----
    def tick(self):
        if self.halted:
            return
        self.cycles += 1
        if self.stall > 0:                       # waiting for memory / I/O / IRQ entry
            self.stall -= 1
            if self.stall == 0:
                self.phase = FETCH
            return
        if self.phase == FETCH:
            if (self.interrupts is not None and not self.in_isr
                    and self.interrupts.has_pending()):
                self._enter_isr()
                return
            if not 0 <= self.pc < len(self.program):
                raise CPUError(f"PC {self.pc} is outside the program")
            self.exec_pc = self.pc
            self.ir = self.program[self.pc]      # IR <- ROM[PC]
            self.pc += 1                         # PC <- PC + 1
            self.phase = DECODE
        elif self.phase == DECODE:
            self.decoded = decode(self.ir)       # control unit splits the word
            self.phase = EXECUTE
        elif self.phase == EXECUTE:
            latency = self._execute()
            self.instructions += 1
            if self.halted:
                self.phase = HALTED
            elif latency > 1:
                self.stall = latency - 1
                self.phase = MEMORY
            else:
                self.phase = FETCH

    def step_instruction(self, limit=200):
        """Run ticks until the next instruction boundary (for single-stepping)."""
        for _ in range(limit):
            self.tick()
            if self.halted or (self.phase == FETCH and self.stall == 0):
                return
        raise CPUError("instruction did not finish")

    # ---- execute stage ----
    def _execute(self):
        opcode, a, b = self.decoded
        name = MNEMONICS[opcode]
        regs = self.regs
        latency = 1
        if name == "HALT":
            self.halted = True
        elif name == "READ_SENSOR":
            if b >= 4:
                raise CPUError(f"no sensor on port {b}")
            value = self.io.read_sensor(b) & WORD_MASK
            regs[a] = value
            self.memory.bus.record(b, value, "IO READ")
            latency = C.IO_CYCLES
        elif name == "LOAD":
            regs[a], latency = self.memory.read(b)
        elif name == "STORE":
            latency = self.memory.write(b, regs[a])
        elif name == "ADD":
            regs[a] = self.alu.add(regs[a], regs[b])
        elif name == "CMP":
            self.alu.compare(regs[a], regs[b])
        elif name == "MAX":
            regs[a], regs[b] = self.alu.maximum(regs[0:4])
        elif name == "JMP":
            self.pc = b
        elif name == "WRITE_SIGNAL":
            self.io.write_signal(regs[a], regs[b], self.in_isr)
            self.memory.bus.record(regs[a], regs[b], "IO WRITE")
            latency = C.IO_CYCLES
        elif name == "IRET":
            self._iret()
        return latency

    # ---- interrupts ----
    def _enter_isr(self):
        """Hardware saves the state and jumps to the ISR (this tick + stall)."""
        self.saved = {"pc": self.pc, "regs": list(self.regs),
                      "flags": self.alu.flags.copy()}
        self.interrupts.acknowledge()
        self.in_isr = True
        self.interrupt_count += 1
        self.pc = self.isr_addr
        self.stall = C.IRQ_CYCLES - 1
        self.phase = IRQ if self.stall else FETCH

    def _iret(self):
        if not self.in_isr or self.saved is None:
            raise CPUError("IRET executed outside an interrupt routine")
        self.pc = self.saved["pc"]
        self.regs[:] = self.saved["regs"]
        self.alu.flags = self.saved["flags"]
        self.saved = None
        self.in_isr = False
        if self.interrupts is not None:
            self.interrupts.end_of_interrupt()
