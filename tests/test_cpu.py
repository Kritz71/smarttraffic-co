"""Tests for the assembler, the fetch-decode-execute cycle, I/O and interrupts."""
import random
import unittest

from src import config as C
from src.controller import PythonController, build_program, load_defaults
from src.cpu import (CPU, DECODE, EXECUTE, FETCH, AssemblerError, CPUError,
                     assemble, disassemble)
from src.interrupts import InterruptController
from src.memory import (ADDR_AGE_N, SYMBOLS, Bus, Memory)


class FakeIO:
    """Stands in for the traffic world."""

    def __init__(self, sensors=(0, 0, 0, 0)):
        self.sensors = list(sensors)
        self.writes = []

    def read_sensor(self, port):
        return self.sensors[port]

    def write_signal(self, direction, green, emergency):
        self.writes.append((direction, green, emergency))


def make_cpu(source, io=None, with_irq=False):
    words, labels = assemble(source, SYMBOLS)
    mem = Memory(bus=Bus())
    load_defaults(mem)
    irq = InterruptController(mem) if with_irq else None
    isr = labels.get("ISR")
    cpu = CPU(mem, words, io or FakeIO(), irq, isr)
    return cpu, mem, irq


def run_until_halt(cpu, limit=2000):
    for _ in range(limit):
        if cpu.halted:
            return
        cpu.tick()
    raise AssertionError("CPU did not halt")


class TestAssembler(unittest.TestCase):
    def test_encoding(self):
        words, _ = assemble("ADD R1, R2\nLOAD R4, [AGE_N]\nJMP 5\nHALT", SYMBOLS)
        self.assertEqual(words, [0x4102, 0x2400, 0x7005, 0x0000])

    def test_labels_and_comments(self):
        words, labels = assemble("; comment\nSTART: ADD R0, R1  ; trailing\n  JMP START", SYMBOLS)
        self.assertEqual(labels, {"START": 0})
        self.assertEqual(words[1], 0x7000)

    def test_disassemble_round_trip_of_the_real_program(self):
        words, _ = build_program()
        for word in words:
            again, _ = assemble(disassemble(word), SYMBOLS)
            self.assertEqual(again, [word])

    def test_errors(self):
        bad = ["FLY R0, R1", "ADD R9, R1", "ADD R1", "LOAD R1, 5", "JMP nowhere",
               "MAX R2, R2", "LOAD R1, [300]", "X: HALT\nX: HALT"]
        for source in bad:
            with self.subTest(source=source):
                with self.assertRaises(AssemblerError):
                    assemble(source, SYMBOLS)

    def test_main_program_fits_the_plan(self):
        words, labels = build_program()
        self.assertEqual(len(words), 24)
        self.assertEqual(labels, {"START": 0, "ISR": 19})
        opcodes = {w >> 12 for w in words}
        self.assertEqual(opcodes, {1, 2, 3, 4, 5, 6, 7, 8, 9})   # every instruction but HALT


class TestInstructionCycle(unittest.TestCase):
    def test_fetch_decode_execute_phases(self):
        cpu, _, _ = make_cpu("ADD R0, R1\nHALT")
        cpu.regs[0], cpu.regs[1] = 2, 3
        self.assertEqual(cpu.phase, FETCH)
        cpu.tick()                                   # FETCH
        self.assertEqual((cpu.phase, cpu.pc, cpu.ir), (DECODE, 1, 0x4001))
        cpu.tick()                                   # DECODE
        self.assertEqual((cpu.phase, cpu.decoded), (EXECUTE, (4, 0, 1)))
        cpu.tick()                                   # EXECUTE
        self.assertEqual(cpu.phase, FETCH)
        self.assertEqual((cpu.regs[0], cpu.instructions, cpu.cycles), (5, 1, 3))

    def test_load_miss_then_hit_cycle_counts(self):
        cpu, _, _ = make_cpu("LOAD R0, [BASE_GREEN]\nLOAD R1, [BASE_GREEN]\nHALT")
        run_until_halt(cpu)
        # LOAD miss = 2 + 5, LOAD hit = 2 + 1, HALT = 3
        self.assertEqual(cpu.cycles, 7 + 3 + 3)
        self.assertEqual((cpu.regs[0], cpu.regs[1]), (C.BASE_GREEN, C.BASE_GREEN))
        self.assertEqual(cpu.instructions, 3)

    def test_store_then_load(self):
        cpu, mem, _ = make_cpu("ADD R0, R1\nSTORE R0, [LAST_SEL]\nLOAD R2, [LAST_SEL]\nHALT")
        cpu.regs[0], cpu.regs[1] = 20, 22
        run_until_halt(cpu)
        self.assertEqual(mem.peek(5), 42)
        self.assertEqual(cpu.regs[2], 42)

    def test_max_writes_index_and_value(self):
        cpu, _, _ = make_cpu("MAX R4, R5\nHALT")
        cpu.regs[0:4] = [3, 9, 9, 1]
        run_until_halt(cpu)
        self.assertEqual((cpu.regs[4], cpu.regs[5]), (1, 9))

    def test_cmp_sets_flags(self):
        cpu, _, _ = make_cpu("CMP R0, R1\nHALT")
        cpu.regs[0], cpu.regs[1] = 7, 3
        run_until_halt(cpu)
        self.assertEqual(cpu.flags.as_tuple(), (False, True, False))

    def test_jmp(self):
        cpu, _, _ = make_cpu("JMP 2\nHALT\nADD R0, R1\nHALT")
        cpu.regs[0], cpu.regs[1] = 1, 1
        run_until_halt(cpu)
        self.assertEqual(cpu.regs[0], 2)

    def test_io_instructions(self):
        io = FakeIO(sensors=(4, 5, 6, 7))
        cpu, mem, _ = make_cpu("READ_SENSOR R2, 3\nWRITE_SIGNAL R0, R1\nHALT", io)
        cpu.regs[0], cpu.regs[1] = 1, 9
        run_until_halt(cpu)
        self.assertEqual(cpu.regs[2], 7)
        self.assertEqual(io.writes, [(1, 9, False)])
        self.assertEqual(mem.bus.control, "IO WRITE")

    def test_single_step(self):
        cpu, _, _ = make_cpu("LOAD R0, [BASE_GREEN]\nHALT")
        cpu.step_instruction()
        self.assertEqual(cpu.instructions, 1)
        self.assertEqual(cpu.phase, FETCH)

    def test_illegal_opcode_and_runaway_pc(self):
        cpu, _, _ = make_cpu("HALT")
        cpu.program = [0xF000]
        with self.assertRaises(CPUError):
            for _ in range(5):
                cpu.tick()
        cpu, _, _ = make_cpu("ADD R0, R1")      # no HALT: runs off the end
        with self.assertRaises(CPUError):
            for _ in range(20):
                cpu.tick()


class TestTrafficProgram(unittest.TestCase):
    def test_cpu_program_matches_the_python_reference(self):
        """The CPU must pick the same road and green time as plain Python."""
        rng = random.Random(42)
        words, labels = build_program()
        for _ in range(200):
            counts = [rng.randint(0, 9) for _ in range(4)]
            ages = [rng.randint(0, C.MAX_AGE) for _ in range(4)]
            io = FakeIO(counts)
            mem = Memory(bus=Bus())
            load_defaults(mem)
            for d in range(4):
                mem.device_write(ADDR_AGE_N + d, ages[d])
            cpu = CPU(mem, words, io, None, labels["ISR"])
            for _ in range(2000):
                cpu.tick()
                if io.writes:
                    break
            self.assertTrue(io.writes, "program never wrote the signal")
            direction, green, emergency = io.writes[0]
            self.assertEqual((direction, green), PythonController.decide(counts, ages))
            self.assertFalse(emergency)

    def test_program_loops_forever(self):
        io = FakeIO([1, 2, 3, 4])
        words, labels = build_program()
        cpu = CPU(Memory(bus=Bus()), words, io, None, labels["ISR"])
        for _ in range(5000):
            cpu.tick()
        self.assertGreater(len(io.writes), 20)
        self.assertEqual({w[0] for w in io.writes}, {3})     # road 3 (West) is busiest


ISR_PROGRAM = """
START: ADD R0, R1
       JMP START
ISR:   LOAD R4, [AMB_DIR]
       LOAD R5, [EMERGENCY_GREEN]
       WRITE_SIGNAL R4, R5
       IRET
"""


class TestInterrupts(unittest.TestCase):
    def run_until(self, cpu, condition, limit=500):
        for _ in range(limit):
            if condition():
                return
            cpu.tick()
        raise AssertionError("condition never became true")

    def test_state_is_saved_and_restored(self):
        io = FakeIO()
        cpu, mem, irq = make_cpu(ISR_PROGRAM, io, with_irq=True)
        cpu.regs[:] = [1, 2, 0, 0, 7, 9]
        for _ in range(10):
            cpu.tick()
        cpu.alu.compare(5, 5)                       # flags: ZERO
        irq.raise_irq(2)
        self.run_until(cpu, lambda: cpu.in_isr)
        saved_pc = cpu.saved["pc"]
        self.assertEqual(cpu.pc, 2)                 # jumped to the ISR
        self.run_until(cpu, lambda: not cpu.in_isr)
        # ISR did its job ...
        self.assertEqual(io.writes, [(2, C.EMERGENCY_GREEN, True)])
        # ... and IRET restored everything it had touched
        self.assertEqual((cpu.regs[4], cpu.regs[5]), (7, 9))
        self.assertEqual(cpu.pc, saved_pc)
        self.assertTrue(cpu.flags.zero)
        self.assertEqual((cpu.interrupt_count, irq.serviced), (1, 1))
        self.assertIsNone(irq.in_service)

    def test_main_program_resumes_after_iret(self):
        cpu, _, irq = make_cpu(ISR_PROGRAM, with_irq=True)
        cpu.regs[0], cpu.regs[1] = 0, 1
        irq.raise_irq(0)
        for _ in range(200):
            cpu.tick()
        self.assertGreater(cpu.regs[0], 5)          # ADD loop kept running

    def test_interrupts_are_not_nested_and_keep_order(self):
        io = FakeIO()
        cpu, _, irq = make_cpu(ISR_PROGRAM, io, with_irq=True)
        irq.raise_irq(1)
        irq.raise_irq(3)
        for _ in range(300):
            cpu.tick()
        self.assertEqual([w[0] for w in io.writes], [1, 3])
        self.assertEqual(cpu.interrupt_count, 2)
        self.assertFalse(irq.has_pending())

    def test_entering_the_isr_costs_cycles(self):
        cpu, _, irq = make_cpu(ISR_PROGRAM, with_irq=True)
        irq.raise_irq(0)
        cpu.tick()                                   # accepts the interrupt
        self.assertTrue(cpu.in_isr)
        self.assertEqual(cpu.phase, "IRQ")
        self.assertEqual(cpu.stall, C.IRQ_CYCLES - 1)

    def test_iret_outside_an_isr_is_an_error(self):
        cpu, _, _ = make_cpu("IRET")
        with self.assertRaises(CPUError):
            for _ in range(5):
                cpu.tick()


if __name__ == "__main__":
    unittest.main()
