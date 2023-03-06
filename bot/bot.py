import sys
import memory; mem = memory.Memory
import database; db = database.Database
import core.io; io = core.io.IO
from script import Script
import misc
import numpy as np

class Bot():
    def __init__(self, main_fun, battle_fun, interact_fun=None):
        self.main_fun = main_fun
        self.script = main_fun()
        self.battle_fun = battle_fun
        self.battle_script = battle_fun()
        self.interact_fun = interact_fun
        self.interact_script = None
        self.was_in_battle = False
        self.wait_after_battle = 30
        self.was_interacting = False
        self.saved_keys = 0
        self.tgt_script = None # Next script manually handled by the user
        Bot.instance = self

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
            if dmg[1] == 0:
                continue
            # TODO: consider moves with low chance to kill
            if np.ceil(dmg[1]) < e.curr_hp and (best is None or dmg[1] > maxdmg):
                best = i
                maxdmg = dmg[1]
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

    def getBestMon():
        """
        TODO: consider type advantage
        """
        best_id = 0
        for i, pkmn in enumerate(db.pteam):
            if pkmn.growth.species_idx == 0:
                break
            if pkmn.curr_hp == 0:
                continue
            if pkmn.curr_hp > db.pteam[best_id].curr_hp:
                best_id = i
        return best_id

    def onPreFrame(self):
        flags_old = None
        vars_old = None
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

            # If in a battle
            if db.isInBattle():
                if (ret := next(self.battle_script, -1)) == -1:
                    return -1
                yield ret
                continue

            # If in an auto-interaction, finish it
            if self.interact_script:
                try:
                    next(self.interact_script)
                except StopIteration:
                    self.interact_script = None
                yield
                continue

            if db.isInteracting() != self.was_interacting:
                # Entering new interaction
                if not self.was_interacting:
                    flags_old = db.getScriptFlags()
                    vars_old = db.getScriptVars()
                    pscript, instr = Script.getFromNextAddr(db.global_context.pc,
                                                            db.global_context.stack)
                    # If the interaction was not manually triggered, auto handle
                    if (self.interact_fun and (not self.tgt_script or
                                               pscript != self.tgt_script)):
                        self.interact_script = self.interact_fun()
                # Finishing an interaction
                else:
                    flags_new = db.getScriptFlags()
                    vars_new = db.getScriptVars()
                    flags_changed = np.where(flags_new != flags_old)[0]
                    vars_changed = np.where(vars_new != vars_old)[0]
                    changed = [Script.Flag(x) for x in flags_changed]
                    changed += [Script.Var(0x4000+x) for x in vars_changed]
                    if len(changed):
                        print(", ".join([str(x) for x in changed]))
                self.was_interacting = not self.was_interacting
                continue

            # In other cases, run the normal script
            if self.script:
                if (ret := next(self.script, -1)) == -1:
                    return -1
                yield ret
                continue
            yield
