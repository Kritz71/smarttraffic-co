"""Central settings for SmartTraffic-CO.

Every tunable number lives here, so you never have to hunt through the code.
"""

TITLE = "SmartTraffic-CO"
WIDTH, HEIGHT = 1280, 720
FPS = 60

# ---------------------------------------------------------------- layout ----
SIM_W = 800            # traffic area = left 800 px, dashboard = the rest
CX, CY = 400, 360      # centre of the intersection
ROAD_HALF = 50         # half the road width (roads are 100 px wide)
LANE_OFFSET = 25       # lane centre is this far from the road centre line
STOP_GAP = 6           # gap between a stop line and the junction box
LAMP_MARGIN = 16       # how far the signal lamp sits outside the kerb

# ------------------------------------------------------------ directions ----
# A direction is the road a vehicle COMES FROM. Everyone drives straight on.
DIRECTIONS = ("N", "S", "E", "W")
DIR_NAMES = ("North", "South", "East", "West")
NORTH, SOUTH, EAST, WEST = 0, 1, 2, 3

# ---------------------------------------------------------------- colours ---
BG_COLOR = (18, 22, 30)
GRASS_COLOR = (27, 40, 36)
ROAD_COLOR = (54, 58, 66)
ROAD_LINE_COLOR = (150, 154, 165)
STOP_LINE_COLOR = (240, 240, 245)
PANEL_BG = (24, 29, 40)
PANEL_BOX = (34, 41, 56)
PANEL_BORDER = (52, 60, 78)
TEXT_COLOR = (230, 235, 245)
MUTED_COLOR = (130, 142, 165)
ACCENT_COLOR = (80, 200, 120)
WARN_COLOR = (240, 190, 60)
DANGER_COLOR = (230, 70, 70)
INFO_COLOR = (90, 160, 240)
LIGHT_COLORS = {
    "green": (60, 220, 100),
    "yellow": (245, 205, 50),
    "red": (235, 60, 60),
}
CAR_COLORS = [(90, 150, 230), (200, 90, 90), (120, 200, 160),
              (180, 130, 220), (220, 200, 110), (150, 160, 175)]
BUS_COLOR = (235, 150, 40)
AMBULANCE_COLOR = (245, 245, 250)

# --------------------------------------------------------------- vehicles ---
# Speeds are in pixels per second, lengths in pixels.
VEHICLES = {
    "car": {"length": 34, "width": 20, "speed": 140, "accel": 180},
    "bus": {"length": 62, "width": 24, "speed": 90, "accel": 100},
    "ambulance": {"length": 40, "width": 22, "speed": 210, "accel": 260},
}
BRAKE = 260            # comfortable braking (px/s^2) used by every vehicle
MIN_GAP = 8            # bumper-to-bumper gap when stopped
AMBULANCE_EXTRA = 250  # ambulances start this far off-screen (siren is heard early)
CLEAR_POS = 130        # an ambulance has "cleared" the junction after this position

# ---------------------------------------------------------------- signals ---
YELLOW_TIME = 1.5
ALL_RED_TIME = 1.0
MIN_GREEN = 4          # seconds
MAX_GREEN = 20         # seconds
BASE_GREEN = 3         # seconds added to the demand score (stored in RAM)
EMERGENCY_GREEN = 8    # seconds of priority green for an ambulance
EMERGENCY_MAX = 15     # hard limit for an emergency green
EMERGENCY_CLEAR = 1.5  # green left once the ambulance has passed
GAP_OUT_TIME = 1.5     # green ends early after this long with an empty queue
SENSOR_RANGE = 300     # sensor loop covers this many pixels before the stop line

# Aging (anti-starvation): a timer peripheral adds 1 to a road's "age" every
# AGE_INTERVAL seconds while vehicles wait there. The CPU adds age to the count.
AGE_INTERVAL = 2.0
MAX_AGE = 15

# ---------------------------------------------------- CPU / memory hardware --
NUM_REGISTERS = 6
RAM_SIZE = 16          # words
CACHE_LINES = 4        # direct-mapped, one word per line
CACHE_HIT_CYCLES = 1
CACHE_MISS_CYCLES = 5  # also the cost of every write (write-through)
IO_CYCLES = 2          # READ_SENSOR / WRITE_SIGNAL
IRQ_CYCLES = 3         # hardware cost of saving state and jumping to the ISR
SPEED_STEPS = (1, 2, 5, 10, 30, 100)   # CPU clock ticks per frame
DEFAULT_SPEED_INDEX = 3

# ------------------------------------------------------------------ modes ---
# rates = vehicles per second arriving from N, S, E, W
MODES = {
    "Normal": {"rates": (0.25, 0.25, 0.25, 0.25), "bus_share": 0.15,
               "ambulance_rate": 0.0},
    "Rush Hour": {"rates": (0.55, 0.55, 0.25, 0.25), "bus_share": 0.10,
                  "ambulance_rate": 0.0},
    "Emergency": {"rates": (0.25, 0.25, 0.25, 0.25), "bus_share": 0.15,
                  "ambulance_rate": 0.04},
}
MODE_ORDER = ("Normal", "Rush Hour", "Emergency")
