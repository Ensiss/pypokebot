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
import battle
from script import Script
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
Script.loadCache()

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
    io.releaseAll()
    io.turbo = True
    while core.frame_counter < 800:
        yield io.toggle(core.KEY_A)
    io.turbo = False
    yield from movement.toConnection(world.ConnectType.DOWN)
    grass = np.vstack(np.where(db.getCurrentMap().map_behavior == 0x202)[::-1]).T
    yield from movement.toAny(grass)
    while True:
        yield from movement.turn(core.KEY_DOWN)
        yield from movement.turn(core.KEY_LEFT)
        yield from movement.turn(core.KEY_UP)
        yield from movement.turn(core.KEY_RIGHT)

def battleAI():
    print(db.pteam[0].species.name, "vs", db.eteam[0].species.name)

    while True:
        if db.battle_menu.is_open and db.battle_menu.menu == 0:
            best_move = Bot.getBestMove()
            print("Best move: %s" % db.battlers[0].moves[best_move].name)
            yield from battle.attack(best_move)
        else:
            yield io.toggle(core.KEY_A)

runGame(Bot(mainAI, battleAI))
pygame.display.quit()
m = db.getCurrentMap()
