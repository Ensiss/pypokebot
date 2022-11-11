import argparse
import struct
import sys
import os
import re

import numpy as np
import mgba.core
import mgba.image
import mgba.log
import pygame

import world
import pokedata
import utils
import memory; mem = memory.Memory
import database; db = database.Database

parser = argparse.ArgumentParser(description="Pokebot")
parser.add_argument("-r", "--rom", type=str, default=os.path.expanduser("~/Games/Pokemon - FireRed Version (USA).gba"),
                    help="Path to the Pokemon Firered v1.0 ROM")

args = parser.parse_args()
mgba.log.silence()
core = mgba.core.load_path(args.rom)
core.autoload_save()
size = core.desired_video_dimensions()
screen_buf = mgba.image.Image(*size)
core.set_video_buffer(screen_buf)
core.reset()
mem.init(core)
db.init()

screen = pygame.display.set_mode(size)
clock = pygame.time.Clock()
turbo = False
keymap = [(pygame.K_UP, core.KEY_UP),
          (pygame.K_DOWN, core.KEY_DOWN),
          (pygame.K_LEFT, core.KEY_LEFT),
          (pygame.K_RIGHT, core.KEY_RIGHT),
          (pygame.K_w, core.KEY_A),
          (pygame.K_x, core.KEY_B),
          (pygame.K_q, core.KEY_L),
          (pygame.K_s, core.KEY_R),
          (pygame.K_RETURN, core.KEY_START),
          (pygame.K_BACKSPACE, core.KEY_SELECT)]

def runGame(onPreFrame=None, nframes=-1):
    global turbo
    i = 0
    while True:
        clock.tick(0 if turbo else 60)
        if nframes > 0 and i >= nframes:
            return
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                return
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    turbo = True
                    continue
                for key in keymap:
                    if event.key == key[0]:
                        core.add_keys(key[1])
                        break
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    turbo = False
                    continue
                for key in keymap:
                    if event.key == key[0]:
                        core.clear_keys(key[1])
                        break

        if onPreFrame is not None:
            onPreFrame()
        core.run_frame()
        mem.updateBuffers()

        surface = pygame.image.frombuffer(screen_buf.to_pil().tobytes(), size, "RGBX")
        screen.blit(surface, (0, 0))
        pygame.display.flip()
        i += 1

def introSkipper():
    core.clear_keys(core.KEY_B, core.KEY_A)
    if core.frame_counter % 2 == 0:
        core.set_keys(core.KEY_A)

runGame(introSkipper, 800)
runGame()
