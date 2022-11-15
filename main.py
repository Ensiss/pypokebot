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

sys.path += ["core", "bot"]
import world
import pokedata
import player
import utils
import memory; mem = memory.Memory
import database; db = database.Database
import core.io; io = core.io.IO
import misc
import movement
from bot import Bot

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
io.init(core)
db.init()

screen = pygame.display.set_mode(size)
clock = pygame.time.Clock()

def runGame(bot=None):
    onPreFrame = None if bot is None else bot.onPreFrame()

    while True:
        clock.tick(0 if io.turbo else 60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                return
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    io.turbo = True
                    continue
                for key in io.keymap:
                    if event.key == key[0]:
                        io.press(key[1])
                        break
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    io.turbo = False
                    continue
                for key in io.keymap:
                    if event.key == key[0]:
                        io.release(key[1])
                        break

        if onPreFrame is not None and next(onPreFrame, -1) == -1:
            return
        core.run_frame()
        mem.updateBuffers()

        surface = pygame.image.frombuffer(screen_buf.to_pil().tobytes(), size, "RGBX")
        screen.blit(surface, (0, 0))
        pygame.display.flip()

def mainAI():
    io.turbo = True
    while core.frame_counter < 800:
        yield io.toggle(core.KEY_A)
    io.turbo = False
    yield from misc.wait(60*1)
    while True:
        print(player.x, player.y, db.isInBattle())
        yield from movement.turn(core.KEY_DOWN)
        yield from movement.turn(core.KEY_LEFT)
        yield from movement.turn(core.KEY_UP)
        yield from movement.turn(core.KEY_RIGHT)

def battleAI():
    while True:
        yield io.toggle(core.KEY_A)

pteam = utils.rawArray(pokedata.PokemonData, 0x02024284, 6)
eteam = utils.rawArray(pokedata.PokemonData, 0x0202402C, 6)
player = player.Player()

runGame(Bot(mainAI(), battleAI()))
