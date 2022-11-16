import enum
import pygame

class IO(object):
    class Key(enum.IntEnum):
        A = 0
        B = enum.auto()
        SELECT = enum.auto()
        START = enum.auto()
        RIGHT = enum.auto()
        LEFT = enum.auto()
        UP = enum.auto()
        DOWN = enum.auto()
        R = enum.auto()
        L = enum.auto()

    def init(core):
        IO.core = core

        IO.turbo = False
        IO.keymap = [(pygame.K_UP, core.KEY_UP),
                     (pygame.K_DOWN, core.KEY_DOWN),
                     (pygame.K_LEFT, core.KEY_LEFT),
                     (pygame.K_RIGHT, core.KEY_RIGHT),
                     (pygame.K_w, core.KEY_A),
                     (pygame.K_x, core.KEY_B),
                     (pygame.K_q, core.KEY_L),
                     (pygame.K_s, core.KEY_R),
                     (pygame.K_RETURN, core.KEY_START),
                     (pygame.K_BACKSPACE, core.KEY_SELECT)]

    def getRaw():
        return IO.core._core.getKeys(IO.core._core)
    def setRaw(keys):
        return IO.core.set_keys(raw=keys)

    def press(key):
        IO.core.add_keys(key)
    def pressOnly(key):
        IO.core.set_keys(key)
    def release(key):
        IO.core.clear_keys(key)
    def releaseAll():
        IO.core.set_keys()

    def toggle(key):
        IO.setRaw(IO.getRaw() ^ (1 << key))
    def setState(key, pressed):
        if pressed:
            IO.press(key)
        else:
            IO.release(key)
