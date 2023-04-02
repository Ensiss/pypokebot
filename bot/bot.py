import sys
import memory; mem = memory.Memory
import database; db = database.Database
import core.io; io = core.io.IO
import movement
import interact
import battle
import script
from script import Script
import misc
import world
import numpy as np

class Bot():
    def __init__(self, main_fun, battle_fun):
        self.main_fun = main_fun
        self.script = main_fun(self)
        self.battle_fun = battle_fun
        self.battle_script = battle_fun(self)
        self.interact_script = None
        self.was_in_battle = False
        self.wait_after_battle = 30
        self.was_interacting = False
        self.saved_keys = 0
        self.tgt_script = None # Next script manually handled by the user
        self.tgt_choices = []
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

    def doInteraction(choices=[]):
        """
        Handle a currently running npc interaction/script
        Optionally answers dialog boxes with a list of choices
        """
        if (pc := db.global_context.pc) == 0:
            return -1
        locked_counter = 0
        pscript, instr = script.Script.getFromNextAddr(pc, db.global_context.stack)
        while db.global_context.pc != 0:
            if db.global_context.pc != pc:
                pc = db.global_context.pc
                if pscript is None:
                    pscript, instr = script.Script.getFromNextAddr(pc, db.global_context.stack)
                else:
                    instr = pscript.searchPrevious(pc, db.global_context.stack)
                locked_counter = 0
                yield io.releaseAll()

            if instr is None:
                yield io.toggle(io.Key.A)
                continue

            if type(instr.cmd) is script.CommandYesNoBox:
                choice = choices.pop(0) if len(choices) > 0 else 0
                while db.global_context.pc == pc:
                    yield from misc.fullPress(io.Key.A if choice else io.Key.B)
                continue
            elif type(instr.cmd) is script.CommandMultichoice:
                choice = choices.pop(0) if len(choices) > 0 else 0x7f
                mcm = db.multi_choice_menu
                if choice != 0x7f:
                    yield from misc.moveCursor(mcm.columns, choice, lambda: mcm.cursor)
                while db.global_context.pc == pc:
                    yield from misc.fullPress(io.Key.A if choice != 0x7f else io.Key.B)
                continue

            elif instr.opcode == 0x66: # waitmsg
                # Spamming the A button bleeds inputs into yesnobox and multichoice
                # so we need to only press A when needed
                if db.getLastByte() in [0xFA, 0xFB]:
                    yield from misc.fullPress(io.Key.A)
                    continue
            elif instr.opcode == 0x6D: # waitkeypress
                yield from misc.fullPress(io.Key.A)
                continue

            locked_counter += 1
            if locked_counter >= 1000:
                print("doInteraction stuck in instruction, trying to continue...")
                print("0x%08X: %s" % (instr.addr, str(instr)))
                locked_counter = 0
                yield from misc.fullPress(io.Key.A)
                continue
            yield
        return 0

    def watchInteraction(self, pscript, choices=[]):
        self.tgt_script = pscript
        self.tgt_choices = choices
    def clearInteraction(self):
        self.tgt_script = None
        self.tgt_choices = []

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
        for var in pscript.inputs.getTrackable():
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
            self.npc_waitlist.discard(key)
            # Hidden NPCs cannot be interacted with
            if type(pscript.event) is world.PersonEvent and not pscript.event.isVisible():
                continue
            for ctx in pscript.execute():
                if len(ctx.outputs.getTrackable()):
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

    def exploreMap(self):
        """
        Track all NPCs in current map and interact with useful ones
        """
        for i in range(len(db.getCurrentMap().persons)):
            self.track(Script.getPerson(i))
        blacklist = [] # Contains unreachable obstacles
        m = db.getCurrentMap()
        while True: # Double loop to handle new dialogue added during exploration
            found = False
            npcs = []
            # Sort npcs by proximity
            for key in self.npc_waitlist:
                bid, mid, idx, stype = key
                if bid != db.player.bank_id or mid != db.player.map_id:
                    continue
                person = m.persons[idx]
                npcs.append(person)
            px, py = db.player.x, db.player.y
            npcs.sort(key=lambda p: (p.x - px)**2 + (p.y - py)**2)

            # Try visiting npcs in order of proximity
            for npc in npcs:
                if npc in blacklist:
                    continue
                found = True
                if (yield from interact.talkTo(npc.evt_nb)) == -1:
                    blacklist.append(npc)
                else:
                    break
            if not found:
                break

    def followPath(self, path, explore=False):
        for (xp, yp, bidp, midp), args in path:
            if type(args) is world.Connection:
                func = movement.toConnection(args)
            elif type(args) is world.WarpEvent:
                func = movement.toWarp(args)
            elif type(args) is world.PersonEvent:
                func = movement.toPers(args)
            else:
                func = movement.toPos(*args)
            if explore:
                yield from self.exploreMap()
            yield from func

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
                    last_talked = db.getScriptVar(Script.LASTTALKED)
                    # LASTTALKED is probably not robust
                    eq_lasttalked = (self.tgt_script and
                                        self.tgt_script.idx == last_talked-1 and
                                        self.tgt_script.type == Script.Type.PERSON)
                    eq_script = (self.tgt_script and
                                    self.tgt_script == pscript)
                    if eq_script or eq_lasttalked:
                        choices = self.tgt_choices
                        self.clearInteraction()
                    else:
                        choices = []
                    # Auto-handle interactions
                    self.interact_script = Bot.doInteraction(choices)
                # Finishing an interaction
                else:
                    flags_new = db.getScriptFlags()
                    vars_new = db.getScriptVars()
                    flags_changed = np.where(flags_new != flags_old)[0]
                    vars_changed = np.where(vars_new != vars_old)[0]
                    changed = [Script.Flag(x) for x in flags_changed]
                    changed += [Script.Var(0x4000+x) for x in vars_changed]
                    if pscript:
                        self.npc_waitlist.discard(pscript.key)
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
