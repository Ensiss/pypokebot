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

    def getWeakenMove():
        """
        Returns the index of the best move for non-lethal damage.
        TODO: also consider status moves
        """
        p = db.battlers[0]
        e = db.battlers[1]
        best = None
        maxdmg = 0

        for i, move in enumerate(p.moves):
            if p.pps[i] == 0:
                continue
            dmg = p.potentialDamage(e, move)
            if dmg[1] < e.curr_hp and (best is None or dmg[1] > maxdmg):
                best = i
                maxdmg = dmg[0]
        return best

    def getBestMove():
        """
        Returns the index of the best move the current pokemon can use
        Currently computed as the highest damaging move if not lethal,
        or the weakest move that will still kill.
        TODO: also consider long term strategies with status affecting moves
        """
        p = db.battlers[0]
        e = db.battlers[1]
        best = 0
        mindmg = 0

        for i, move in enumerate(p.moves):
            if p.pps[i] == 0:
                continue
            dmg = p.potentialDamage(e, move)
            if ((mindmg < e.curr_hp and dmg[0] > mindmg) or
                (dmg[0] > e.curr_hp and dmg[0] < mindmg)):
                best = i
                mindmg = dmg[0]
        return best

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
