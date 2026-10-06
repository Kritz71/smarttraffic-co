# SmartTraffic-CO

Smart Traffic Intersection Simulator (Computer Organization & Architecture Demo)smarttraffic-co is an interactive 2D simulation that visualizes fundamental Computer Organization & Architecture (COA) concepts using a smart four-way traffic intersection setup.   

Key Features:


1.CPU & Instruction Cycle: Simulates fetch-decode-execute cycles for controlling traffic signal timings. 

2.ALU & Registers: Performs arithmetic/logic operations to compute traffic density and queue lengths in real-time. 
3.Memory Hierarchy: Demonstrates cache vs. RAM storage for active vehicle positions and state memory.  
4.Interrupt Handling: Simulates emergency vehicle priorities via hardware interrupt requests (IRQ).  
5.Interactive Dashboard: Visualizes system metrics, clock cycles, and real-time component states alongside the 2D Pygame simulation.

> Simulation only. It does not control real traffic.

![Rush hour](screenshots/rush_hour.png)
![Ambulance interrupt](screenshots/isr_interrupt.png)

## Run

    python -m venv .venv
    # activate: Windows  .venv\Scripts\activate    macOS/Linux  source .venv/bin/activate
    pip install -r requirements.txt
    python main.py

Options: `python main.py --mode "Rush Hour"`, `--seed 5` (repeatable run),
`--frames 600 --screenshot screenshots/x.png` (save a picture and quit).

## Controls

| Key | Action |
|-----|--------|
| SPACE | pause / resume everything |
| S | while paused: execute ONE instruction (great for the viva) |
| UP / DOWN | CPU speed: 1 to 100 clock ticks per frame |
| 1 / 2 / 3 | Normal / Rush Hour / Emergency mode |
| A | send an ambulance from a random road |
| R | reset |
| ESC | quit |

## How it works

1. Vehicles arrive on four roads. **Sensors** count vehicles before each stop line.
2. A **virtual CPU** loops through a 19-instruction program: `READ_SENSOR` the
   four counts, `LOAD`/`ADD` a waiting-time bonus from RAM, `MAX` (ALU) picks the
   busiest road, `WRITE_SIGNAL` asks the lights for a green phase.
3. An **ambulance** raises an interrupt. The CPU saves its state, runs the 5-line
   ISR (priority green), and `IRET` restores the state.
4. The dashboard shows PC, IR, phase, registers, flags, buses, RAM, cache and stats live.

## Files

    main.py             window, keyboard, game loop
    src/config.py       every setting
    src/traffic.py      roads, vehicles, signal, sensors (no pygame)
    src/cpu.py          registers, ALU, assembler, fetch-decode-execute
    src/memory.py       RAM, 4-line cache, buses
    src/interrupts.py   interrupt controller + ambulance ISR
    src/controller.py   the traffic program + wiring (SmartTrafficSystem)
    src/dashboard.py    all drawing
    tests/              67 unit tests

## Tests

    python -m unittest discover -v

See `docs/architecture.md`, `docs/viva.md` and `docs/git.md`.
