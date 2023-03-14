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
        self.script = main_fun(self)
        self.battle_fun = battle_fun
        self.battle_script = battle_fun(self)
        self.interact_fun = interact_fun
        self.interact_script = None
        self.was_in_battle = False
        self.wait_after_battle = 30
        self.was_interacting = False
        self.saved_keys = 0
        self.tgt_script = None # Next script manually handled by the user
        Bot.instance = self

        # NPC interactions
        self.npc_hooks = {}
        self.npc_waitlist = set()
        self.npc_visited = set()

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

    def track(self, pscript):
        """
        Track a script's variables to monitor new dialogue options
        Add to the waitlist if necessary
        WARNING: might race condition if a var/flag is set before script execution is detected.
        """
        if pscript is None or pscript.key in self.npc_visited:
            return
        self.npc_visited.add(pscript.key)
        for ctx in pscript.ctxs:
            for var in ctx.getFilteredInputs():
                if var not in self.npc_hooks:
                    self.npc_hooks[var] = []
                self.npc_hooks[var].append(pscript.key)
        self.checkTracked([pscript.key])

    def checkTracked(self, keys):
        """
        Check a list of script keys for possible flags/variables to set
        """
        for key in keys:
            if not (pscript := Script.cache[key]):
                continue
            if key in self.npc_waitlist:
                self.npc_waitlist.remove(key)
            for ctx in (ctxs := pscript.execute()):
                if len(ctx.getFilteredOutputs()):
                    self.npc_waitlist.add(key)
                    break
    def checkHooks(self, changed):
        """
        Poll hooks for a list of changed flags/variables
        """
        if len(changed):
            print(", ".join([str(x) for x in changed]))
        for var in changed:
            if var in self.npc_hooks:
                self.checkTracked(self.npc_hooks[var])

    def onPreFrame(self):
        flags_old = None
        vars_old = None
        pscript = None

        while True:
            if db.isInBattle() != self.was_in_battle:
                if not self.was_in_battle:
                    # When entering battle, reload the battle script and save pressed keys
                    self.saved_keys = io.getRaw()
                    self.battle_script = self.battle_fun(self)
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
                    self.track(pscript)
                    # If the interaction was not manually triggered, auto handle
                    if self.interact_fun:
                        last_talked = db.getScriptVar(Script.LASTTALKED)
                        # LASTTALKED is probably not robust
                        eq_lasttalked = (self.tgt_script and
                                         self.tgt_script.idx == last_talked-1 and
                                         self.tgt_script.type == Script.Type.PERSON)
                        eq_script = (self.tgt_script and
                                     self.tgt_script == pscript)
                        if not eq_script and not eq_lasttalked:
                            self.interact_script = self.interact_fun()
                # Finishing an interaction
                else:
                    flags_new = db.getScriptFlags()
                    vars_new = db.getScriptVars()
                    flags_changed = np.where(flags_new != flags_old)[0]
                    vars_changed = np.where(vars_new != vars_old)[0]
                    changed = [Script.Flag(x) for x in flags_changed]
                    changed += [Script.Var(0x4000+x) for x in vars_changed]
                    if pscript and pscript.key in self.npc_waitlist:
                        self.npc_waitlist.remove(pscript.key)
                    self.checkHooks(changed)
                self.was_interacting = not self.was_interacting
                continue

            # In other cases, run the normal script
            if self.script:
                if (ret := next(self.script, -1)) == -1:
                    return -1
                yield ret
                continue
            yield
