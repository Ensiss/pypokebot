import sys
import memory; mem = memory.Memory
import database; db = database.Database
import core.io; io = core.io.IO
import misc

class Bot():
    def __init__(self, main_fun, battle_fun):
        self.main_fun = main_fun
        self.script = main_fun()
        self.battle_fun = battle_fun
        self.battle_script = battle_fun()
        self.was_in_battle = False
        self.wait_after_battle = 30
        self.saved_keys = 0

    def onPreFrame(self):
        while True:
            if db.isInBattle() != self.was_in_battle:
                if not self.was_in_battle:
                    # When entering battle, reload the battle script and save pressed keys
                    self.saved_keys = io.getRaw()
                    self.battle_script = self.battle_fun()
                else:
                    # After battle, wait for screen fade and restore keys
                    io.releaseAll()
                    yield from misc.wait(self.wait_after_battle)
                    io.setRaw(self.saved_keys)
                self.was_in_battle = not self.was_in_battle

            curr_script = self.battle_script if db.isInBattle() else self.script
            if curr_script is not None:
                ret = next(curr_script, -1)
                if ret == -1:
                    return -1
                yield ret
            else:
                yield
