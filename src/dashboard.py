"""All drawing code: the traffic area (left) and the CPU dashboard (right)."""
import pygame

from . import config as C
from .cpu import DECODE, EXECUTE, FETCH, IRQ, MEMORY, disassemble
from .memory import ADDR_LAST_SEL
from .traffic import APPROACH, S_ALL_RED, S_GREEN, S_YELLOW

PHASE_TAGS = (FETCH, DECODE, EXECUTE, MEMORY, IRQ)
PHASE_COLORS = {FETCH: C.ACCENT_COLOR, DECODE: C.ACCENT_COLOR, EXECUTE: C.ACCENT_COLOR,
                MEMORY: C.WARN_COLOR, IRQ: C.DANGER_COLOR}
REG_ROLES = ("N", "S", "E", "W", "dir", "green")
RAM_SHORT = {0: "ageN", 1: "ageS", 2: "ageE", 3: "ageW", 4: "base", 5: "sel",
             6: "amb", 7: "emrg"}

PX = C.SIM_W + 14             # left edge of dashboard content
PW = C.WIDTH - C.SIM_W - 28   # width of dashboard content


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Dashboard:
    def __init__(self, screen):
        self.screen = screen
        names = "consolas,menlo,dejavusansmono,couriernew,monospace"
        self.f_title = pygame.font.SysFont(names, 20, bold=True)
        self.f_big = pygame.font.SysFont(names, 18, bold=True)
        self.f = pygame.font.SysFont(names, 16)
        self.f_prog = pygame.font.SysFont(names, 15)
        self.f_small = pygame.font.SysFont(names, 13)

    # ------------------------------------------------------------ helpers --
    def text(self, s, font, color, pos, anchor="topleft"):
        img = font.render(str(s), True, color)
        rect = img.get_rect(**{anchor: pos})
        self.screen.blit(img, rect)
        return rect

    def box(self, rect, fill=C.PANEL_BOX, border=C.PANEL_BORDER, width=1, radius=5):
        pygame.draw.rect(self.screen, fill, rect, border_radius=radius)
        if width:
            pygame.draw.rect(self.screen, border, rect, width, border_radius=radius)

    def tag(self, rect, label, active, color, font=None):
        font = font or self.f_small
        fill = _mix(C.PANEL_BOX, color, 0.85) if active else C.PANEL_BOX
        self.box(rect, fill, color if active else C.PANEL_BORDER)
        self.text(label, font, (15, 20, 28) if active else C.MUTED_COLOR,
                  rect.center, "center")

    # --------------------------------------------------------------- main --
    def draw(self, system, ui):
        self.screen.fill(C.BG_COLOR)
        self.draw_world(system, ui)
        self.draw_panel(system, ui)

    # ============================================================ TRAFFIC ==
    def draw_world(self, system, ui):
        scr, world = self.screen, system.world
        scr.set_clip(pygame.Rect(0, 0, C.SIM_W, C.HEIGHT))
        scr.fill(C.GRASS_COLOR, (0, 0, C.SIM_W, C.HEIGHT))
        H = C.ROAD_HALF
        pygame.draw.rect(scr, C.ROAD_COLOR, (C.CX - H, 0, 2 * H, C.HEIGHT))
        pygame.draw.rect(scr, C.ROAD_COLOR, (0, C.CY - H, C.SIM_W, 2 * H))

        # dashed centre lines (not inside the junction box)
        for y in range(0, C.HEIGHT, 30):
            if y + 16 < C.CY - H or y > C.CY + H:
                pygame.draw.rect(scr, C.ROAD_LINE_COLOR, (C.CX - 1, y, 2, 16))
        for x in range(0, C.SIM_W, 30):
            if x + 16 < C.CX - H or x > C.CX + H:
                pygame.draw.rect(scr, C.ROAD_LINE_COLOR, (x, C.CY - 1, 16, 2))

        # stop lines (one per approach, across that approach's lane only)
        g = H + C.STOP_GAP
        for a, b in (((C.CX - H, C.CY - g), (C.CX, C.CY - g)),
                     ((C.CX, C.CY + g), (C.CX + H, C.CY + g)),
                     ((C.CX + g, C.CY - H), (C.CX + g, C.CY)),
                     ((C.CX - g, C.CY), (C.CX - g, C.CY + H))):
            pygame.draw.line(scr, C.STOP_LINE_COLOR, a, b, 4)

        # vehicles
        for lane in world.vehicles:
            for v in lane:
                self._draw_vehicle(v, world.time)

        # signal lamps, sensor counts and ages
        counts = world.counts()
        for d in range(4):
            ap = APPROACH[d]
            colour = C.LIGHT_COLORS[world.signal.color_for(d)]
            lamp = (int(ap.lamp[0]), int(ap.lamp[1]))
            pygame.draw.circle(scr, (12, 14, 18), lamp, 12)
            pygame.draw.circle(scr, colour, lamp, 9)
            lx, ly = lamp[0] - ap.dx * 34, lamp[1] - ap.dy * 34
            self.text(f"{C.DIRECTIONS[d]}: {counts[d]}", self.f_big, C.TEXT_COLOR,
                      (lx, ly - 8), "center")
            self.text(f"age {world.ages[d]}", self.f_small, C.MUTED_COLOR,
                      (lx, ly + 10), "center")
        scr.set_clip(None)

        self._draw_world_overlays(system, ui)

    def _draw_vehicle(self, v, t):
        x0, y0, x1, y1 = v.rect()
        rect = pygame.Rect(int(x0), int(y0), max(2, int(x1 - x0)), max(2, int(y1 - y0)))
        scr = self.screen
        pygame.draw.rect(scr, v.color, rect, border_radius=5)
        pygame.draw.rect(scr, _mix(v.color, (0, 0, 0), 0.5), rect, 1, border_radius=5)
        if v.kind == "ambulance":
            cx, cy = rect.center
            pygame.draw.rect(scr, C.DANGER_COLOR, (cx - 5, cy - 1, 10, 3))
            pygame.draw.rect(scr, C.DANGER_COLOR, (cx - 1, cy - 5, 3, 10))
            flash = C.DANGER_COLOR if int(t * 6) % 2 == 0 else C.INFO_COLOR
            pygame.draw.circle(scr, flash, (cx, cy), 3)
        elif v.kind == "bus":
            inner = rect.inflate(-8, -8) if rect.width > 12 and rect.height > 12 else rect
            pygame.draw.rect(scr, _mix(v.color, (255, 255, 255), 0.35), inner, 1,
                             border_radius=3)

    def _draw_world_overlays(self, system, ui):
        world, sig = system.world, system.world.signal
        self.text(f"Mode: {world.mode}    Time: {world.time:5.0f}s", self.f_big,
                  C.TEXT_COLOR, (12, 10))
        if sig.phase == S_GREEN:
            status = f"GREEN  {C.DIR_NAMES[sig.direction]}  {max(sig.timer, 0):4.1f}s"
            colour = C.LIGHT_COLORS["green"]
        elif sig.phase == S_YELLOW:
            status = f"YELLOW  {C.DIR_NAMES[sig.direction]}"
            colour = C.LIGHT_COLORS["yellow"]
        elif sig.phase == S_ALL_RED:
            status = "ALL RED (clearing the junction)"
            colour = C.LIGHT_COLORS["red"]
        else:
            status = "waiting for the CPU..."
            colour = C.MUTED_COLOR
        self.text(status, self.f, colour, (12, 34))

        # emergency banner
        parts = []
        if sig.emergency and sig.direction is not None:
            parts.append(f"PRIORITY GREEN: {C.DIR_NAMES[sig.direction].upper()}")
        if system.cpu.in_isr:
            parts.append("CPU IN ISR")
        if system.interrupts.pending:
            parts.append(f"IRQ PENDING x{len(system.interrupts.pending)}")
        if parts:
            on = int(world.time * 3) % 2 == 0 or system.cpu.in_isr
            rect = pygame.Rect(0, 0, 440, 30)
            rect.midtop = (C.SIM_W // 2, 62)
            self.box(rect, C.DANGER_COLOR if on else (120, 40, 40), (255, 140, 140))
            self.text("AMBULANCE - " + " | ".join(parts), self.f, (255, 255, 255),
                      rect.center, "center")

        if ui.paused:
            self.text("PAUSED  (S = step one instruction)", self.f_big, C.WARN_COLOR,
                      (C.SIM_W // 2, 110), "center")
        hint = ("SPACE pause   S step   UP/DOWN cpu speed   1/2/3 mode   "
                "A ambulance   R reset   ESC quit")
        self.text(hint, self.f_small, C.MUTED_COLOR, (12, C.HEIGHT - 20))

    # ============================================================= PANEL ===
    def draw_panel(self, system, ui):
        scr, cpu, mem = self.screen, system.cpu, system.memory
        pygame.draw.rect(scr, C.PANEL_BG, (C.SIM_W, 0, C.WIDTH - C.SIM_W, C.HEIGHT))
        pygame.draw.line(scr, C.PANEL_BORDER, (C.SIM_W, 0), (C.SIM_W, C.HEIGHT), 2)

        # ---- title + clock ----
        self.text("VIRTUAL CPU", self.f_title, C.ACCENT_COLOR, (PX, 8))
        state = "PAUSED" if ui.paused else f"RUNNING  {ui.ticks_per_frame} ticks/frame"
        self.text(state, self.f_small, C.WARN_COLOR if ui.paused else C.MUTED_COLOR,
                  (PX + PW, 14), "topright")

        # ---- control-unit phase tags ----
        tw, gap = 84, 8
        for i, name in enumerate(PHASE_TAGS):
            rect = pygame.Rect(PX + i * (tw + gap), 38, tw, 22)
            self.tag(rect, name, cpu.phase == name, PHASE_COLORS[name])

        # ---- PC / IR / counters / flags ----
        shown = disassemble(cpu.ir) if (cpu.instructions or cpu.phase != FETCH) else "-"
        self.text(f"PC {cpu.pc:02d}   IR 0x{cpu.ir:04X}   {shown}", self.f_big,
                  C.TEXT_COLOR, (PX, 68))
        self.text(f"CYCLES {cpu.cycles}   INSTR {cpu.instructions}   CPI {cpu.cpi:.2f}",
                  self.f, C.MUTED_COLOR, (PX, 92))
        fl = cpu.flags
        for i, (label, on) in enumerate((("ZERO", fl.zero), ("GREATER", fl.greater),
                                         ("LESS", fl.less))):
            self.tag(pygame.Rect(PX + i * 78, 116, 72, 20), label, on, C.INFO_COLOR)
        mode_txt, mode_col = (("ISR: emergency routine", C.DANGER_COLOR) if cpu.in_isr
                              else ("main traffic program", C.ACCENT_COLOR))
        self.text(mode_txt, self.f, mode_col, (PX + PW, 118), "topright")

        # ---- registers ----
        self.text("REGISTERS", self.f_small, C.MUTED_COLOR, (PX, 146))
        rw, rg = 68, 8.8
        for i, val in enumerate(cpu.regs):
            rect = pygame.Rect(int(PX + i * (rw + rg)), 162, rw, 42)
            self.box(rect)
            self.text(f"R{i} {REG_ROLES[i]}", self.f_small, C.MUTED_COLOR,
                      (rect.centerx, rect.y + 4), "midtop")
            self.text(val, self.f_big, C.TEXT_COLOR, (rect.centerx, rect.y + 20), "midtop")

        # ---- program window ----
        self.text(f"PROGRAM ROM   (START={system.labels['START']}, ISR={system.labels['ISR']})",
                  self.f_small, C.MUTED_COLOR, (PX, 214))
        words, rows, lh = system.words, 9, 17
        cur = cpu.current_index()
        top = max(0, min(cur - 4, len(words) - rows))
        self.box(pygame.Rect(PX, 230, PW, rows * lh + 8), C.PANEL_BOX)
        label_at = {addr: name for name, addr in system.labels.items()}
        for row in range(rows):
            addr = top + row
            y = 234 + row * lh
            if addr == cur:
                color = PHASE_COLORS.get(cpu.phase, C.ACCENT_COLOR)
                pygame.draw.rect(scr, _mix(C.PANEL_BOX, color, 0.45),
                                 (PX + 3, y - 1, PW - 6, lh), border_radius=3)
            in_isr_code = addr >= system.labels["ISR"]
            colour = C.WARN_COLOR if in_isr_code else C.TEXT_COLOR
            self.text(f"{addr:02d}  0x{words[addr]:04X}  {disassemble(words[addr])}",
                      self.f_prog, colour, (PX + 8, y))
            if addr in label_at:
                self.text(label_at[addr], self.f_small, C.MUTED_COLOR,
                          (PX + PW - 8, y + 1), "topright")

        # ---- buses ----
        self.text("BUSES", self.f_small, C.MUTED_COLOR, (PX, 394))
        bus = system.bus
        items = (("ADDRESS", f"0x{bus.address:02X}"), ("DATA", f"0x{bus.data:04X}"),
                 ("CONTROL", bus.control))
        bw, bg = 144, 10
        for i, (name, val) in enumerate(items):
            rect = pygame.Rect(PX + i * (bw + bg), 410, bw, 44)
            fill = _mix(C.PANEL_BOX, C.INFO_COLOR, 0.6 * bus.flash)
            self.box(rect, fill, _mix(C.PANEL_BORDER, C.INFO_COLOR, bus.flash))
            self.text(name, self.f_small, C.MUTED_COLOR, (rect.centerx, rect.y + 4), "midtop")
            self.text(val, self.f_big, C.TEXT_COLOR, (rect.centerx, rect.y + 21), "midtop")

        # ---- RAM ----
        mem_op = bus.control.startswith(("READ", "WRITE"))
        hit = mem.last_hit
        self.text(f"RAM  ({mem.size} words)", self.f_small, C.MUTED_COLOR, (PX, 464))
        for addr in range(mem.size):
            rect = pygame.Rect(PX + (addr % 8) * 56, 480 + (addr // 8) * 38, 54, 36)
            hot = mem_op and bus.address == addr
            border = (C.ACCENT_COLOR if hit else C.DANGER_COLOR) if hot else C.PANEL_BORDER
            self.box(rect, C.PANEL_BOX, border, 2 if hot else 1)
            self.text(f"{addr}:{RAM_SHORT.get(addr, '-')}", self.f_small, C.MUTED_COLOR,
                      (rect.centerx, rect.y + 3), "midtop")
            self.text(mem.ram[addr], self.f, C.TEXT_COLOR, (rect.centerx, rect.y + 17), "midtop")

        # ---- cache ----
        n = len(mem.cache)
        self.text(f"CACHE  ({n} lines, direct-mapped: index = address mod {n})",
                  self.f_small, C.MUTED_COLOR, (PX, 560))
        cw = (PW - 6 * (n - 1)) // n
        for i, line in enumerate(mem.cache):
            rect = pygame.Rect(PX + i * (cw + 6), 576, cw, 44)
            hot = mem_op and bus.address % n == i
            border = (C.ACCENT_COLOR if hit else C.DANGER_COLOR) if hot else C.PANEL_BORDER
            self.box(rect, C.PANEL_BOX, border, 2 if hot else 1)
            self.text(f"line {i}", self.f_small, C.MUTED_COLOR, (rect.centerx, rect.y + 4), "midtop")
            body = f"V tag{line.tag} d={line.data}" if line.valid else "empty"
            self.text(body, self.f_small, C.TEXT_COLOR if line.valid else C.MUTED_COLOR,
                      (rect.centerx, rect.y + 24), "midtop")
        self.text(f"HITS {mem.hits}   MISSES {mem.misses}   HIT RATE {mem.hit_rate:.0%}",
                  self.f, C.TEXT_COLOR, (PX, 628))

        # ---- traffic statistics ----
        w = system.world
        self.text(f"PASSED {w.passed}   AVG WAIT {w.avg_wait:.1f}s   MAX WAIT {w.max_wait:.0f}s",
                  self.f, C.MUTED_COLOR, (PX, 654))
        last = mem.peek(ADDR_LAST_SEL) % 4
        self.text(f"AMBULANCES {w.ambulances_served}   IRQ {system.interrupts.raised}/"
                  f"{system.interrupts.serviced}   LAST CHOICE {C.DIRECTIONS[last]}",
                  self.f, C.MUTED_COLOR, (PX, 676))
