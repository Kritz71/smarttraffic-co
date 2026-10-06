# Architecture

    Vehicles -> Sensors --READ_SENSOR--> CPU (PC, IR, Control Unit, R0-R5, ALU+flags)
                                          |  \__ Address/Data/Control bus __ RAM + Cache
    Ambulance -> Interrupt Controller --IRQ-> CPU --WRITE_SIGNAL--> Traffic Signals

## Instruction word (16 bit): `[opcode:4 | A:4 | B:8]`

| Op | Instruction | Effect |
|----|-------------|--------|
| 0 | HALT | stop |
| 1 | READ_SENSOR Rd, port | Rd = vehicles waiting on road `port` (I/O read) |
| 2 | LOAD Rd, [addr] | Rd = RAM[addr] through the cache |
| 3 | STORE Rs, [addr] | RAM[addr] = Rs (write-through) |
| 4 | ADD Rd, Rs | Rd = Rd + Rs |
| 5 | CMP Ra, Rb | set ZERO / GREATER / LESS |
| 6 | MAX Rd, Rv | ALU scans R0-R3: Rd = index, Rv = value of the largest |
| 7 | JMP t | PC = t |
| 8 | WRITE_SIGNAL Rdir, Rgreen | ask the lights for a green phase (I/O write) |
| 9 | IRET | restore PC, registers, flags |

Registers: R0-R3 road scores (N,S,E,W), R4 chosen road, R5 green time. 16-bit, wrap on overflow.

## Control unit
One phase per clock tick: FETCH (IR = ROM[PC], PC++), DECODE (split the word),
EXECUTE. Slow operations add MEMORY ticks: cache hit 1 cycle, miss 5, every write 5
(write-through), I/O 2. Entering an interrupt costs 3 ticks. CPI is about 3.9.

## Memory
Program ROM is separate from data RAM (simplified Harvard design), so instruction
fetches do not use the data buses. RAM has 16 words: 0-3 ages, 4 BASE_GREEN,
5 LAST_SEL, 6 AMB_DIR, 7 EMERGENCY_GREEN. Cache: 4 lines, direct-mapped
(`index = addr mod 4`, `tag = addr div 4`). Addresses 0 and 4 collide, which is why
the hit rate sits near 50%: a real conflict-miss example.

## Decision rule
`score = vehicles waiting + age`; busiest = highest score (ties: North first);
`green = score + BASE_GREEN` seconds, clamped to 4-20 s by the lights.
Age is the anti-starvation bonus: a timer peripheral adds 1 every 2 s a road waits
and writes it to RAM. `tests/test_cpu.py` proves the CPU program always matches
`PythonController.decide`.

## Interrupts
Ambulance spawns -> `raise_irq(road)`. At the next FETCH the CPU saves PC, registers
and flags, the controller writes the road to RAM[AMB_DIR], the CPU jumps to `ISR`.
The ISR loads the road and time, `WRITE_SIGNAL` (treated as priority because the CPU
is in an ISR), `IRET`. No nesting: extra IRQs queue.

## Signal behaviour
GREEN -> YELLOW (1.5 s) -> ALL RED (1 s) -> next request. The CPU only *requests*;
the lights finish their cycle first. An emergency request cuts the green short,
holds the ambulance's green until it clears, then releases it. Green also ends
early if its queue is empty while others wait (gap-out).

## Simplifications (say these in the viva)
One lane per direction, straight-through only, 16-bit words, no conditional jumps
(MAX does the selection), CMP only sets flags shown on the dashboard.
