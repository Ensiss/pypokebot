import sys
sys.path += ["core", "bot"]
import memory; mem = memory.Memory
import database; db = database.Database
import misc

class Bot():
    def __init__(self, script, battle_script):
        self.script = script
        self.battle_script = battle_script
        self.was_in_battle = False
        self.wait_after_battle = 30
        self.saved_keys = 0

    def onPreFrame(self):
        while True:
            curr_script = self.battle_script if db.isInBattle() else self.script

            if db.isInBattle() != self.was_in_battle:
                if self.was_in_battle:
                    mem.core.set_keys()
                    yield from misc.wait(self.wait_after_battle)
                    mem.core.set_keys(raw=self.saved_keys)
                else:
                    self.saved_keys = mem.core._core.getKeys(mem.core._core)
                self.was_in_battle = not self.was_in_battle

            if curr_script is not None:
                yield next(curr_script)
            else:
                yield
