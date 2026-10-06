"""Interrupt controller and the ambulance emergency routine (ISR).

How an ambulance interrupt works
--------------------------------
1. The ambulance siren is detected  -> the controller raises an IRQ.
2. At the next instruction boundary the CPU saves PC, registers and flags,
   and jumps to the ISR (hardware does this, it takes IRQ_CYCLES clock ticks).
3. The controller writes the ambulance's road into RAM (AMB_DIR).
4. The ISR loads it, asks for a priority green with WRITE_SIGNAL, and runs IRET.
5. IRET restores PC, registers and flags - the main program carries on as if
   nothing happened.

Interrupts are not nested: a second IRQ waits in a queue until IRET.
"""
from collections import deque

from .memory import ADDR_AMB_DIR

# The routine the CPU runs. It uses R4/R5, which the hardware has saved.
ISR_SOURCE = """
ISR:
    LOAD  R4, [AMB_DIR]          ; which road has the ambulance?
    LOAD  R5, [EMERGENCY_GREEN]  ; how long should it stay green?
    STORE R4, [LAST_SEL]         ; remember the choice
    WRITE_SIGNAL R4, R5          ; inside an ISR the lights treat this as priority
    IRET                         ; restore PC, registers, flags
"""


class InterruptController:
    def __init__(self, memory):
        self.memory = memory
        self.pending = deque()
        self.in_service = None       # road being served right now
        self.raised = 0
        self.serviced = 0

    def raise_irq(self, direction):
        """Called by the ambulance detector."""
        self.pending.append(direction)
        self.raised += 1

    def has_pending(self):
        return bool(self.pending)

    def acknowledge(self):
        """CPU accepts the interrupt: the device puts its data in RAM."""
        direction = self.pending.popleft()
        self.memory.device_write(ADDR_AMB_DIR, direction)
        self.in_service = direction
        self.serviced += 1
        return direction

    def end_of_interrupt(self):
        self.in_service = None
