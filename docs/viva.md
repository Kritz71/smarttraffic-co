# Viva notes

**Q: What is the fetch-decode-execute cycle in your project?**
Press SPACE then S. FETCH copies ROM[PC] into IR and increments PC, DECODE splits the
16-bit word into opcode and operands, EXECUTE performs it. The dashboard tags light up.

**Q: Where is the ALU used?** ADD (green time, adding age), CMP (flags), MAX (busiest road).

**Q: What are flags for?** CMP and MAX compare numbers and set ZERO/GREATER/LESS.
Our ISA has no conditional jump, so flags are shown for demonstration.

**Q: Why is your cache hit rate about 50%?** Direct-mapped with 4 lines: addresses 0
and 4 share line 0, 1 and 5 share line 1, so they evict each other (conflict misses).

**Q: Write-through or write-back?** Write-through, no write-allocate: every STORE goes to RAM.

**Q: What does an interrupt do?** Hardware finishes the current instruction, saves PC,
registers and flags, jumps to the ISR, and IRET restores them. Press A to watch it.

**Q: Polling vs interrupt?** The sensors are polled in a loop; the ambulance uses an
interrupt because it must not wait for the loop.

**Q: Why not nest interrupts?** Simplicity: one shared AMB_DIR word. Extra IRQs queue.

**Q: What are the buses?** Address, data and control lines light on every LOAD/STORE and
I/O instruction (control shows READ HIT / READ MISS / WRITE / IO READ / IO WRITE).

**Q: Why a separate program ROM?** Simplified Harvard architecture.

**Q: How do you know it is correct?** 67 unit tests, including CPU vs a plain-Python
reference on 200 random inputs, and 4-minute simulations with zero red-light
violations and zero collisions in every mode.

**Q: Where is a CPI of about 3.9 from?** 3 cycles per instruction plus memory/I-O stalls.

## 5-minute demo script
1. Run `python main.py`, explain the two halves of the screen.
2. Press SPACE, then S repeatedly: show PC, IR, registers changing.
3. Press SPACE, UP: run fast; point at the cache and hit rate.
4. Press 2 (Rush Hour): N/S get longer greens, ages stop E/W starving.
5. Press A: banner, ISR in orange, registers restored after IRET.
6. Run `python -m unittest discover`.
