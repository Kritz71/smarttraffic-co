"""Tests for the traffic model and for the whole system working together."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from src import config as C
from src.controller import SmartTrafficSystem
from src.memory import ADDR_AGE_N
from src.traffic import S_ALL_RED, S_GREEN, S_IDLE, S_YELLOW, TrafficSignal, World

DT = 1 / 60


def run_signal(sig, seconds, **kw):
    for _ in range(int(seconds / DT)):
        sig.update(DT, **kw)


def overlap(a, b):
    return a[0] + 1 < b[2] and b[0] + 1 < a[2] and a[1] + 1 < b[3] and b[1] + 1 < a[3]


class TestSignal(unittest.TestCase):
    def test_full_cycle_green_yellow_allred_idle(self):
        sig = TrafficSignal()
        sig.request(2, 5)
        self.assertEqual((sig.phase, sig.direction), (S_GREEN, 2))
        run_signal(sig, 5.1)
        self.assertEqual(sig.phase, S_YELLOW)
        run_signal(sig, C.YELLOW_TIME + 0.05)
        self.assertEqual(sig.phase, S_ALL_RED)
        run_signal(sig, C.ALL_RED_TIME + 0.05)
        self.assertEqual(sig.phase, S_IDLE)

    def test_only_one_road_is_ever_green(self):
        sig = TrafficSignal()
        sig.request(0, 4)
        for _ in range(600):
            sig.update(DT)
            greens = [d for d in range(4) if sig.color_for(d) == "green"]
            self.assertLessEqual(len(greens), 1)

    def test_green_time_is_clamped(self):
        sig = TrafficSignal()
        sig.request(1, 1000)
        self.assertEqual(sig.timer, C.MAX_GREEN)
        sig = TrafficSignal()
        sig.request(1, 0)
        self.assertEqual(sig.timer, C.MIN_GREEN)

    def test_latest_request_is_served_after_the_cycle(self):
        sig = TrafficSignal()
        sig.request(0, 4)
        sig.request(1, 6)
        sig.request(3, 6)                       # the latest one wins
        run_signal(sig, 4 + C.YELLOW_TIME + C.ALL_RED_TIME + 0.2)
        self.assertEqual((sig.phase, sig.direction), (S_GREEN, 3))

    def test_same_road_keeps_green_without_a_yellow(self):
        sig = TrafficSignal()
        sig.request(0, 4)
        run_signal(sig, 3)
        sig.request(0, 6)
        run_signal(sig, 1.5)
        self.assertEqual((sig.phase, sig.direction), (S_GREEN, 0))

    def test_emergency_cuts_the_current_green_short(self):
        sig = TrafficSignal()
        sig.request(0, 20)
        run_signal(sig, 1)
        sig.request(2, 8, emergency=True)
        run_signal(sig, 0.1)
        self.assertEqual(sig.phase, S_YELLOW)
        run_signal(sig, C.YELLOW_TIME + C.ALL_RED_TIME + 0.2, hold=True)
        self.assertEqual((sig.phase, sig.direction, sig.emergency), (S_GREEN, 2, True))

    def test_emergency_on_an_idle_signal_starts_at_once(self):
        sig = TrafficSignal()
        sig.request(3, 8, emergency=True)
        self.assertEqual((sig.phase, sig.direction, sig.emergency), (S_GREEN, 3, True))

    def test_emergency_stays_green_while_the_ambulance_is_crossing(self):
        sig = TrafficSignal()
        sig.request(1, 8, emergency=True)
        run_signal(sig, 12, hold=True)
        self.assertEqual((sig.phase, sig.direction), (S_GREEN, 1))
        run_signal(sig, C.EMERGENCY_CLEAR + 0.1, hold=False)    # ambulance has passed
        self.assertEqual(sig.phase, S_YELLOW)

    def test_emergency_green_has_a_hard_limit(self):
        sig = TrafficSignal()
        sig.request(1, 8, emergency=True)
        run_signal(sig, C.EMERGENCY_MAX - 0.5, hold=True)
        self.assertEqual(sig.phase, S_GREEN)               # still within the limit
        run_signal(sig, 0.5 + C.EMERGENCY_CLEAR + 0.2, hold=True)
        self.assertEqual(sig.phase, S_YELLOW)              # limit reached, then cleared

    def test_two_ambulances_on_different_roads_are_both_served_in_order(self):
        """Regression test: a second emergency must not overwrite the first."""
        sig = TrafficSignal()
        sig.request(0, 20)
        sig.request(2, 8, emergency=True)
        sig.request(3, 8, emergency=True)
        served = []
        for _ in range(int(40 / DT)):
            sig.update(DT, hold=False)
            if sig.phase == S_GREEN and sig.emergency and sig.direction not in served:
                served.append(sig.direction)
        self.assertEqual(served, [2, 3])

    def test_gap_out_ends_an_empty_green_early(self):
        sig = TrafficSignal()
        sig.request(0, 20)
        run_signal(sig, C.MIN_GREEN - 0.5, gap_out=True)
        self.assertEqual(sig.phase, S_GREEN)               # never shorter than MIN_GREEN
        run_signal(sig, 0.7, gap_out=True)
        self.assertEqual(sig.phase, S_YELLOW)              # then ends long before 20 s

    def test_gap_out_needs_a_continuous_empty_queue(self):
        sig = TrafficSignal()
        sig.request(0, 20)
        for _ in range(int(10 / DT)):
            sig.update(DT, gap_out=(int(sig.elapsed / 1.0) % 2 == 0))   # keeps flickering
        self.assertEqual((sig.phase, sig.direction), (S_GREEN, 0))


class TestVehicles(unittest.TestCase):
    def make_world(self):
        return World("Normal", seed=1)          # signal idle = all red, no random traffic needed

    def advance(self, world, seconds):
        for _ in range(int(seconds / DT)):
            world.update(DT)

    def test_vehicle_stops_at_the_red_line(self):
        w = self.make_world()
        for d in range(4):
            v = w.spawn_vehicle(d, "car")
            self.assertIsNotNone(v)
            v.pos = -150
        w.mode = "Normal"
        w.rng.random = lambda: 1.0              # switch random arrivals off
        self.advance(w, 15)
        for d in range(4):
            v = w.vehicles[d][0]
            self.assertLessEqual(v.pos, 0.0)
            self.assertGreater(v.pos, -1.0)
            self.assertLess(v.speed, 1.0)

    def test_followers_keep_a_safe_gap(self):
        w = self.make_world()
        w.rng.random = lambda: 1.0
        a = w.spawn_vehicle(0, "bus")
        a.pos = -100
        b = w.spawn_vehicle(0, "car")
        b.pos = -220
        self.advance(w, 20)
        gap = a.pos - a.length - b.pos
        self.assertGreaterEqual(gap, C.MIN_GAP - 1e-6)
        self.assertLess(gap, C.MIN_GAP + 1.0)

    def test_vehicle_crosses_on_green_and_leaves(self):
        w = self.make_world()
        w.rng.random = lambda: 1.0
        v = w.spawn_vehicle(2, "car")
        v.pos = -200
        w.signal.request(2, 20)
        self.advance(w, 12)
        self.assertEqual(w.passed, 1)
        self.assertEqual(w.vehicle_count(), 0)

    def test_sensor_counts_waiting_vehicles(self):
        w = self.make_world()
        w.rng.random = lambda: 1.0
        for pos in (-20, -80, -140):
            v = w.spawn_vehicle(1, "car")
            v.pos = pos
        w.vehicles[1].sort(key=lambda x: -x.pos)
        self.assertEqual(w.sensor_count(1), 3)
        self.assertEqual(w.counts(), [0, 3, 0, 0])

    def test_no_spawn_when_the_road_is_full(self):
        w = self.make_world()
        w.rng.random = lambda: 1.0
        results = [w.spawn_vehicle(0, "car") for _ in range(30)]
        self.assertIsNone(results[-1])
        self.assertIsNotNone(results[0])

    def test_ambulance_raises_an_irq_with_its_direction(self):
        seen = []
        w = World("Normal", seed=1, on_ambulance=seen.append)
        w.spawn_ambulance(3)
        self.assertEqual(seen, [3])
        self.assertEqual(w.vehicles[3][0].kind, "ambulance")


class TestWholeSystem(unittest.TestCase):
    def simulate(self, mode, seconds, seed, check_overlaps=True):
        s = SmartTrafficSystem(mode, seed)
        w = s.world
        overlaps = 0
        for frame in range(int(seconds / DT)):
            s.update(DT, 10)
            if check_overlaps and frame % 3 == 0:
                ns = [v.rect() for d in (0, 1) for v in w.vehicles[d]]
                ew = [v.rect() for d in (2, 3) for v in w.vehicles[d]]
                overlaps += sum(1 for a in ns for b in ew if overlap(a, b))
                for lane in w.vehicles:
                    for i in range(1, len(lane)):
                        if lane[i].pos > lane[i - 1].pos - lane[i - 1].length + 1e-6:
                            overlaps += 1
        return s, overlaps

    def test_safety_in_every_mode(self):
        for mode in C.MODE_ORDER:
            with self.subTest(mode=mode):
                s, overlaps = self.simulate(mode, 240, seed=11)
                self.assertEqual(s.world.red_violations, 0)
                self.assertEqual(overlaps, 0)
                self.assertGreater(s.world.passed, 100)

    def test_no_road_is_starved_in_rush_hour(self):
        s, _ = self.simulate("Rush Hour", 400, seed=5, check_overlaps=False)
        w = s.world
        self.assertTrue(all(n > 20 for n in w.passed_by_dir), w.passed_by_dir)
        self.assertLess(w.max_wait, 120)

    def test_cpu_drives_the_lights(self):
        s, _ = self.simulate("Normal", 60, seed=2, check_overlaps=False)
        self.assertGreater(s.world.signal.green_starts, 3)
        self.assertGreater(s.cpu.instructions, 1000)
        self.assertGreater(s.memory.hits, 0)
        self.assertGreater(s.memory.misses, 0)
        self.assertGreater(s.cpu.cpi, 3.0)

    def test_ages_reach_ram(self):
        s, _ = self.simulate("Rush Hour", 90, seed=5, check_overlaps=False)
        for d in range(4):
            self.assertEqual(s.memory.peek(ADDR_AGE_N + d), s.world.ages[d])

    def test_same_seed_gives_the_same_run(self):
        a, _ = self.simulate("Normal", 60, seed=9, check_overlaps=False)
        b, _ = self.simulate("Normal", 60, seed=9, check_overlaps=False)
        self.assertEqual((a.world.passed, a.cpu.cycles, a.memory.hits),
                         (b.world.passed, b.cpu.cycles, b.memory.hits))

    def test_ambulance_interrupts_the_cpu_and_gets_priority(self):
        s = SmartTrafficSystem("Normal", seed=3)
        w = s.world
        for _ in range(int(20 / DT)):
            s.update(DT, 10)
        current = w.signal.direction if w.signal.direction is not None else 0
        target = (current + 1) % 4
        s.spawn_ambulance(target)
        self.assertEqual(len(s.interrupts.pending), 1)
        waited, entered_isr = 0.0, False
        while not (w.signal.emergency and w.signal.direction == target):
            s.update(DT, 10)
            entered_isr = entered_isr or s.cpu.in_isr or s.interrupts.serviced > 0
            waited += DT
            self.assertLess(waited, 5.0, "ambulance did not get a green in time")
        self.assertTrue(entered_isr)
        self.assertEqual(s.cpu.interrupt_count, 1)
        for _ in range(int(15 / DT)):
            s.update(DT, 10)
        self.assertEqual(w.ambulances_served, 1)
        self.assertFalse(s.cpu.in_isr)

    def test_every_ambulance_in_emergency_mode_is_served(self):
        s, _ = self.simulate("Emergency", 300, seed=4, check_overlaps=False)
        self.assertGreaterEqual(s.interrupts.raised, 3)
        self.assertLessEqual(s.interrupts.raised - s.interrupts.serviced, 1)
        self.assertGreaterEqual(s.world.ambulances_served, s.interrupts.raised - 3)

    def test_reset_and_mode_switch(self):
        s = SmartTrafficSystem("Normal", seed=1)
        for _ in range(300):
            s.update(DT, 10)
        s.set_mode("Rush Hour")
        self.assertEqual(s.world.mode, "Rush Hour")
        s.reset()
        self.assertEqual((s.cpu.cycles, s.world.passed, s.world.time), (0, 0, 0.0))
        self.assertEqual(s.mode, "Rush Hour")


class TestUISmoke(unittest.TestCase):
    def test_app_runs_and_handles_every_key(self):
        try:
            import pygame
            from main import App
        except ImportError:
            self.skipTest("pygame not installed")
        app = App("Emergency", seed=1)
        try:
            for _ in range(20):
                app.frame()
            for key in (pygame.K_SPACE, pygame.K_s, pygame.K_s, pygame.K_SPACE,
                        pygame.K_UP, pygame.K_UP, pygame.K_UP, pygame.K_UP,
                        pygame.K_DOWN, pygame.K_1, pygame.K_2, pygame.K_3,
                        pygame.K_a, pygame.K_r):
                app.handle_key(key)
                app.dashboard.draw(app.system, app.ui)
            self.assertEqual(app.ui.speed_index, len(C.SPEED_STEPS) - 1 - 1)
            app.handle_key(pygame.K_ESCAPE)
            self.assertFalse(app.running)
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
