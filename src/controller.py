"""The traffic program the CPU runs, and the glue that wires everything together.

Decision rule (same in the CPU program and in PythonController):

    score(road) = vehicles waiting + age of the road      (age = anti-starvation)
    busiest     = road with the highest score             (ties -> lowest index)
    green time  = score of busiest + BASE_GREEN seconds   (the lights clamp it)
"""
from . import config as C
from .cpu import CPU, assemble
from .interrupts import ISR_SOURCE, InterruptController
from .memory import (ADDR_AGE_N, ADDR_BASE_GREEN, ADDR_EMERGENCY_GREEN,
                     SYMBOLS, Bus, Memory)
from .traffic import World

MAIN_SOURCE = """
START:
    READ_SENSOR R0, 0            ; R0 <- cars waiting North
    READ_SENSOR R1, 1            ; R1 <- South
    READ_SENSOR R2, 2            ; R2 <- East
    READ_SENSOR R3, 3            ; R3 <- West
    LOAD  R4, [AGE_N]            ; add the waiting-time bonus to each road
    ADD   R0, R4
    LOAD  R4, [AGE_S]
    ADD   R1, R4
    LOAD  R4, [AGE_E]
    ADD   R2, R4
    LOAD  R4, [AGE_W]
    ADD   R3, R4
    MAX   R4, R5                 ; ALU: R4 <- busiest road, R5 <- its score
    LOAD  R0, [BASE_GREEN]       ; R0 is free now, reuse it
    ADD   R5, R0                 ; R5 <- green time = score + base
    CMP   R5, R0                 ; flags: is the green time above the base?
    STORE R4, [LAST_SEL]         ; remember the decision in RAM
    WRITE_SIGNAL R4, R5          ; I/O: ask the lights for this green phase
    JMP   START                  ; and do it all again
"""


def build_program():
    """Assemble main program + ISR. Returns (words, labels)."""
    return assemble(MAIN_SOURCE + ISR_SOURCE, SYMBOLS)


def load_defaults(memory):
    """Initial RAM contents (the 'data segment')."""
    memory.device_write(ADDR_BASE_GREEN, C.BASE_GREEN)
    memory.device_write(ADDR_EMERGENCY_GREEN, C.EMERGENCY_GREEN)


class PythonController:
    """Plain-Python version of the decision rule.

    It is not used by the simulation. It is the reference we test the CPU
    program against: both must always pick the same road and green time.
    """

    @staticmethod
    def decide(counts, ages, base_green=C.BASE_GREEN):
        scores = [c + a for c, a in zip(counts, ages)]
        best = 0
        for i in range(1, 4):
            if scores[i] > scores[best]:
                best = i
        return best, scores[best] + base_green


class WorldIO:
    """The CPU's I/O ports: sensors in, traffic signal out."""

    def __init__(self, world):
        self.world = world

    def read_sensor(self, port):
        return self.world.sensor_count(port)

    def write_signal(self, direction, green, emergency):
        self.world.signal.request(direction, green, emergency)


class SmartTrafficSystem:
    """Traffic world + CPU + memory + interrupt controller, wired together."""

    def __init__(self, mode="Normal", seed=None):
        self.mode = mode
        self.seed = seed
        self._build()

    def _build(self):
        self.bus = Bus()
        self.memory = Memory(bus=self.bus)
        load_defaults(self.memory)
        self.interrupts = InterruptController(self.memory)
        self.world = World(self.mode, self.seed, on_ambulance=self.interrupts.raise_irq)
        self.words, self.labels = build_program()
        self.cpu = CPU(self.memory, self.words, WorldIO(self.world),
                       self.interrupts, self.labels["ISR"])

    def reset(self):
        self._build()

    def set_mode(self, name):
        self.mode = name
        self.world.set_mode(name)

    def spawn_ambulance(self, direction=None):
        return self.world.spawn_ambulance(direction)

    def update(self, dt, cpu_ticks):
        """One frame: move the traffic, update timers, run the CPU."""
        self.world.update(dt)
        for d in range(4):                                  # age timer -> RAM
            self.memory.device_write(ADDR_AGE_N + d, self.world.ages[d])
        for _ in range(cpu_ticks):
            self.cpu.tick()
        self.bus.decay(dt)

    def step_instruction(self):
        """Single-step the CPU by one instruction (used while paused)."""
        self.cpu.step_instruction()
