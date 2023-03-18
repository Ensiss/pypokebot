import numpy as np
import memory; mem = memory.Memory
import database; db = database.Database
import core.io; io = core.io.IO
from bot import Bot
import script
import misc
import movement

def doInteraction(choices=[]):
    """
    Handle a currently running npc interaction/script
    Optionally answers dialog boxes with a list of choices
    """
    pc = db.global_context.pc
    if pc == 0:
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

def readSign(sign_id, choices=[]):
    """
    Move to and interact with a sign event, optionally with predefined choices
    """
    Bot.instance.watchInteraction(script.Script.getSign(sign_id), choices)
    while Bot.instance.tgt_script:
        if (yield from movement.toSign(sign_id)) == -1:
            return -1
        yield from misc.fullPress(io.Key.A)

def talkTo(local_id, choices=[]):
    """
    Move to and talk to an NPC, optionally with predefined choices
    """
    Bot.instance.watchInteraction(script.Script.getPerson(local_id-1), choices)
    while Bot.instance.tgt_script:
        if (yield from movement.toPers(local_id)) == -1:
            return -1
        yield from misc.fullPress(io.Key.A)
