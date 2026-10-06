"""Roads, vehicles, traffic signals and sensors.

This file contains no pygame code, so the whole traffic model can be tested
without opening a window.
"""
import math
import random
from collections import deque
from dataclasses import dataclass

from . import config as C

GREEN, YELLOW, RED = "green", "yellow", "red"
S_IDLE, S_GREEN, S_YELLOW, S_ALL_RED = "IDLE", "GREEN", "YELLOW", "ALL_RED"


# ------------------------------------------------------------- geometry ----
@dataclass(frozen=True)
class Approach:
    """Geometry of one road that leads into the junction."""
    sx: float            # stop-line point (centre of the lane): x
    sy: float            # stop-line point (centre of the lane): y
    dx: int              # unit vector of travel
    dy: int
    approach_len: float  # stop line -> edge of the traffic area, behind it
    exit_len: float      # stop line -> edge of the traffic area, ahead of it
    lamp: tuple          # where the signal lamp is drawn


def _approach(sx, sy, dx, dy):
    if dy == 1:
        back, ahead = sy, C.HEIGHT - sy
    elif dy == -1:
        back, ahead = C.HEIGHT - sy, sy
    elif dx == -1:
        back, ahead = C.SIM_W - sx, sx
    else:
        back, ahead = sx, C.SIM_W - sx
    side = (C.ROAD_HALF - C.LANE_OFFSET) + C.LAMP_MARGIN
    lamp = (sx + (-dy) * side, sy + dx * side)   # driver's right-hand side
    return Approach(sx, sy, dx, dy, back, ahead, lamp)


# Index order matches config: North, South, East, West.
APPROACH = (
    _approach(C.CX - C.LANE_OFFSET, C.CY - C.ROAD_HALF - C.STOP_GAP, 0, 1),
    _approach(C.CX + C.LANE_OFFSET, C.CY + C.ROAD_HALF + C.STOP_GAP, 0, -1),
    _approach(C.CX + C.ROAD_HALF + C.STOP_GAP, C.CY - C.LANE_OFFSET, -1, 0),
    _approach(C.CX - C.ROAD_HALF - C.STOP_GAP, C.CY + C.LANE_OFFSET, 1, 0),
)


# -------------------------------------------------------------- vehicles ---
@dataclass
class Vehicle:
    vid: int
    kind: str
    direction: int
    pos: float            # front bumper, distance past the stop line (negative = before it)
    length: float
    width: float
    speed: float
    max_speed: float
    accel: float
    color: tuple
    wait: float = 0.0
    crossed: bool = False

    def rect(self):
        """Bounding box (x0, y0, x1, y1) in traffic-area pixels."""
        ap = APPROACH[self.direction]
        fx = ap.sx + self.pos * ap.dx
        fy = ap.sy + self.pos * ap.dy
        bx = fx - self.length * ap.dx
        by = fy - self.length * ap.dy
        hw = self.width / 2
        if ap.dx == 0:
            return (fx - hw, min(fy, by), fx + hw, max(fy, by))
        return (min(fx, bx), fy - hw, max(fx, bx), fy + hw)


# --------------------------------------------------------------- signal ----
class TrafficSignal:
    """Four-way signal: only one road has green at a time.

    The CPU does not flip lamps directly. It *requests* a green phase
    (WRITE_SIGNAL). The signal finishes its current cycle first
    (GREEN -> YELLOW -> ALL_RED) and then serves the latest request.
    An emergency request (made from the ISR) cuts the current green short.
    """

    def __init__(self, on_green=None):
        self.on_green = on_green
        self.reset()

    def reset(self):
        self.phase = S_IDLE
        self.direction = None
        self.timer = 0.0
        self.pending = None      # (direction, green seconds) - normal request
        self.priority = deque()  # (direction, green seconds) - emergency requests, FIFO
        self.emergency = False   # current green is an emergency green
        self.emergency_time = 0.0
        self.green_starts = 0
        self.elapsed = 0.0       # seconds the current green has been on
        self.gap_time = 0.0      # seconds the green road's queue has been empty

    # ---- requests from the CPU ----
    def request(self, direction, green_s, emergency=False):
        if not 0 <= direction < 4:
            raise ValueError(f"bad direction {direction}")
        if emergency:
            if self.phase == S_GREEN and self.direction == direction:
                # already green for the ambulance: just keep it green
                self.emergency = True
                self.emergency_time = 0.0
                self.timer = max(self.timer, C.EMERGENCY_GREEN)
                return
            if all(d != direction for d, _ in self.priority):
                self.priority.append((direction, C.EMERGENCY_GREEN))
            if self.phase == S_GREEN and not self.emergency:
                self.timer = 0.0            # cut the current green short
            elif self.phase == S_IDLE:
                self._start_next()
            return
        green = max(C.MIN_GREEN, min(C.MAX_GREEN, int(green_s)))
        self.pending = (direction, green)
        if self.phase == S_IDLE and not self.priority:
            self._start_next()

    # ---- state machine ----
    def _start_next(self):
        if self.priority:
            direction, green = self.priority.popleft()
            self.emergency = True
            self.emergency_time = 0.0
        elif self.pending is not None:
            (direction, green), self.pending = self.pending, None
            self.emergency = False
        else:
            return
        self.phase = S_GREEN
        self.direction = direction
        self.timer = float(green)
        self.elapsed = 0.0
        self.gap_time = 0.0
        self.green_starts += 1
        if self.on_green:
            self.on_green(direction, self.emergency)

    def update(self, dt, hold=False, gap_out=False):
        """Advance the signal.

        hold    - an ambulance is still crossing (keeps an emergency green on)
        gap_out - the green road's queue is empty while other roads wait
                  (like an inductive-loop detector: end the green early)
        """
        if self.phase == S_IDLE:
            self._start_next()
            return
        if self.phase == S_GREEN:
            self.elapsed += dt
            ended_early = False
            if self.emergency:
                self.emergency_time += dt
                hold = hold and self.emergency_time < C.EMERGENCY_MAX
                if not hold:
                    self.timer = min(self.timer, C.EMERGENCY_CLEAR)
            else:
                self.gap_time = self.gap_time + dt if gap_out else 0.0
                if self.gap_time >= C.GAP_OUT_TIME and self.elapsed >= C.MIN_GREEN:
                    ended_early = True
                    self.timer = 0.0
            if not (self.emergency and hold):
                self.timer -= dt
            if self.timer <= 0:
                same_again = (self.pending is not None and not self.priority
                              and not self.emergency and not ended_early
                              and self.pending[0] == self.direction)
                if same_again:               # still the busiest road: keep green
                    self.timer = float(self.pending[1])
                    self.pending = None
                    self.gap_time = 0.0
                else:
                    self.phase = S_YELLOW
                    self.timer = C.YELLOW_TIME
                    self.emergency = False
        elif self.phase == S_YELLOW:
            self.timer -= dt
            if self.timer <= 0:
                self.phase = S_ALL_RED
                self.timer = C.ALL_RED_TIME
        elif self.phase == S_ALL_RED:
            self.timer -= dt
            if self.timer <= 0:
                self.phase = S_IDLE
                self.direction = None
                self._start_next()

    def color_for(self, direction):
        if self.direction == direction:
            if self.phase == S_GREEN:
                return GREEN
            if self.phase == S_YELLOW:
                return YELLOW
        return RED


# ----------------------------------------------------------------- world ---
class World:
    """All four roads, their vehicles, the signal and the sensors."""

    def __init__(self, mode="Normal", seed=None, on_ambulance=None):
        self.rng = random.Random(seed)
        self.on_ambulance = on_ambulance        # called with the direction
        self.signal = TrafficSignal(on_green=self._on_green)
        self.vehicles = [[], [], [], []]        # front-most vehicle first
        self.ages = [0, 0, 0, 0]
        self._age_timer = [0.0] * 4
        self.mode = mode
        self.time = 0.0
        self._next_id = 1
        # statistics
        self.passed = 0
        self.passed_by_dir = [0, 0, 0, 0]
        self.total_wait = 0.0
        self.max_wait = 0.0
        self.ambulances_served = 0
        self.red_violations = 0

    def set_mode(self, name):
        if name not in C.MODES:
            raise ValueError(f"unknown mode {name}")
        self.mode = name

    # ---- sensors ----
    def sensor_count(self, direction):
        """Vehicles between the stop line and SENSOR_RANGE pixels behind it."""
        return sum(1 for v in self.vehicles[direction]
                   if -C.SENSOR_RANGE <= v.pos < 0)

    def counts(self):
        return [self.sensor_count(d) for d in range(4)]

    # ---- spawning ----
    def spawn_vehicle(self, direction, kind="car"):
        spec = C.VEHICLES[kind]
        extra = C.AMBULANCE_EXTRA if kind == "ambulance" else 0
        start = -(APPROACH[direction].approach_len + spec["length"] + extra)
        lane = self.vehicles[direction]
        if lane:
            last = lane[-1]
            if start > last.pos - last.length - C.MIN_GAP:
                return None                      # no room on the road
        if kind == "car":
            color = self.rng.choice(C.CAR_COLORS)
        elif kind == "bus":
            color = C.BUS_COLOR
        else:
            color = C.AMBULANCE_COLOR
        v = Vehicle(self._next_id, kind, direction, start, spec["length"],
                    spec["width"], spec["speed"], spec["speed"], spec["accel"],
                    color)
        self._next_id += 1
        lane.append(v)
        if kind == "ambulance" and self.on_ambulance:
            self.on_ambulance(direction)         # the siren raises an interrupt
        return v

    def spawn_ambulance(self, direction=None):
        if direction is None:
            direction = self.rng.randrange(4)
        return self.spawn_vehicle(direction, "ambulance")

    def _spawn_random(self, dt):
        mode = C.MODES[self.mode]
        for d in range(4):
            if self.rng.random() < mode["rates"][d] * dt:
                kind = "bus" if self.rng.random() < mode["bus_share"] else "car"
                self.spawn_vehicle(d, kind)
        if self.rng.random() < mode["ambulance_rate"] * dt:
            self.spawn_ambulance()

    # ---- helpers ----
    def ambulance_holding(self, direction):
        """True while an ambulance on this road has not cleared the junction."""
        return any(v.kind == "ambulance" and v.pos < C.CLEAR_POS
                   for v in self.vehicles[direction])

    def _on_green(self, direction, emergency):
        self.ages[direction] = 0
        self._age_timer[direction] = 0.0

    # ---- one simulation step ----
    def update(self, dt):
        self.time += dt
        self._spawn_random(dt)
        sd = self.signal.direction
        hold = sd is not None and self.ambulance_holding(sd)
        gap_out = False
        if sd is not None and self.signal.phase == S_GREEN:
            gap_out = (self.sensor_count(sd) == 0 and
                       any(self.sensor_count(o) > 0 for o in range(4) if o != sd))
        self.signal.update(dt, hold, gap_out)
        for d in range(4):
            self._update_lane(d, dt)
        self._update_ages(dt)

    def _update_lane(self, d, dt):
        lane = self.vehicles[d]
        light = self.signal.color_for(d)
        for i, v in enumerate(lane):
            gap = 1e9                                  # free road ahead
            if i > 0:
                lead = lane[i - 1]
                gap = lead.pos - lead.length - C.MIN_GAP - v.pos
            if v.pos <= 0 and light != GREEN:
                # Red or yellow: stop at the line, unless it is yellow and
                # the vehicle is too close to stop comfortably.
                too_late = light == YELLOW and v.speed ** 2 / (2 * C.BRAKE) > -v.pos
                if not too_late:
                    gap = min(gap, -v.pos)
            gap = max(gap, 0.0)
            safe_speed = math.sqrt(2 * C.BRAKE * gap)   # can always stop in 'gap'
            v.speed = min(v.speed + v.accel * dt, v.max_speed, safe_speed)
            v.pos += min(v.speed * dt, gap)
            if v.pos < 0 and v.speed < 5:
                v.wait += dt
            if not v.crossed and v.pos > 0:
                v.crossed = True
                self.passed += 1
                self.passed_by_dir[d] += 1
                self.total_wait += v.wait
                self.max_wait = max(self.max_wait, v.wait)
                if v.kind == "ambulance":
                    self.ambulances_served += 1
                if light == RED:
                    self.red_violations += 1
        exit_len = APPROACH[d].exit_len
        while lane and lane[0].pos - lane[0].length > exit_len:
            lane.pop(0)

    def _update_ages(self, dt):
        for d in range(4):
            waiting = self.sensor_count(d) > 0
            served = self.signal.phase == S_GREEN and self.signal.direction == d
            if served or not waiting:
                self.ages[d] = 0               # nothing to wait for any more
                self._age_timer[d] = 0.0
                continue
            self._age_timer[d] += dt           # still waiting: age grows
            if self._age_timer[d] >= C.AGE_INTERVAL:
                self._age_timer[d] -= C.AGE_INTERVAL
                self.ages[d] = min(C.MAX_AGE, self.ages[d] + 1)


    # ---- statistics ----
    @property
    def avg_wait(self):
        return self.total_wait / self.passed if self.passed else 0.0

    def vehicle_count(self):
        return sum(len(lane) for lane in self.vehicles)
