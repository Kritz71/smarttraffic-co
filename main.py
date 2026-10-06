"""SmartTraffic-CO - entry point.

    python main.py                       open the simulator
    python main.py --mode "Rush Hour"    start in another mode
    python main.py --frames 600 --screenshot screenshots/demo.png
                                         run 600 frames, save a picture, quit
"""
import argparse
import sys

import pygame

from src import config as C
from src.controller import SmartTrafficSystem
from src.dashboard import Dashboard


class UIState:
    """Things the user controls with the keyboard."""

    def __init__(self):
        self.paused = False
        self.speed_index = C.DEFAULT_SPEED_INDEX

    @property
    def ticks_per_frame(self):
        return C.SPEED_STEPS[self.speed_index]


class App:
    def __init__(self, mode="Normal", seed=None):
        pygame.init()
        self.screen = pygame.display.set_mode((C.WIDTH, C.HEIGHT))
        pygame.display.set_caption(C.TITLE)
        self.clock = pygame.time.Clock()
        self.system = SmartTrafficSystem(mode, seed)
        self.dashboard = Dashboard(self.screen)
        self.ui = UIState()
        self.running = True

    # ---- input ----
    def handle_key(self, key):
        ui, system = self.ui, self.system
        if key == pygame.K_ESCAPE:
            self.running = False
        elif key == pygame.K_SPACE:
            ui.paused = not ui.paused
        elif key == pygame.K_s and ui.paused:
            system.step_instruction()
        elif key == pygame.K_UP:
            ui.speed_index = min(ui.speed_index + 1, len(C.SPEED_STEPS) - 1)
        elif key == pygame.K_DOWN:
            ui.speed_index = max(ui.speed_index - 1, 0)
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
            system.set_mode(C.MODE_ORDER[key - pygame.K_1])
        elif key == pygame.K_a:
            system.spawn_ambulance()
        elif key == pygame.K_r:
            system.reset()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.handle_key(event.key)

    # ---- one frame ----
    def frame(self):
        self.handle_events()
        if not self.ui.paused:
            # Fixed time step: the simulation never depends on how fast the PC is.
            self.system.update(1 / C.FPS, self.ui.ticks_per_frame)
        self.dashboard.draw(self.system, self.ui)
        pygame.display.flip()
        self.clock.tick(C.FPS)

    def run(self, max_frames=None):
        frames = 0
        while self.running and (max_frames is None or frames < max_frames):
            self.frame()
            frames += 1


def main():
    parser = argparse.ArgumentParser(description="SmartTraffic-CO simulator")
    parser.add_argument("--mode", choices=C.MODE_ORDER, default="Normal")
    parser.add_argument("--seed", type=int, default=None, help="random seed (repeatable runs)")
    parser.add_argument("--frames", type=int, default=None, help="quit after this many frames")
    parser.add_argument("--screenshot", default=None, help="save a PNG when the run ends")
    args = parser.parse_args()

    app = App(args.mode, args.seed)
    app.run(args.frames)
    if args.screenshot:
        pygame.image.save(app.screen, args.screenshot)
        print("saved", args.screenshot)
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
