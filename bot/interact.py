import numpy as np
import memory; mem = memory.Memory
import database; db = database.Database
import core.io; io = core.io.IO
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
    pscript, instr = script.Script.getFromNextAddr(pc, db.global_context.stack)
    while db.global_context.pc != 0:
        if db.global_context.pc != pc:
            pc = db.global_context.pc
            instr = pscript.searchPrevious(pc, db.global_context.stack)
            yield io.releaseAll()

        if type(instr.cmd) is script.CommandYesNoBox:
            choice = choices.pop(0) if len(choices) > 0 else 0
            while db.global_context.pc == pc:
                yield from misc.fullPress(io.Key.A if choice else io.Key.B)
            continue
        elif type(instr.cmd) is script.CommandMultichoice and len(choices) > 0:
            choice = choices.pop(0) if len(choices) > 0 else 0x7f
            mcm = db.multi_choice_menu
            if choice != 0x7f:
                yield from misc.moveCursor(mcm.columns, choice, lambda: mcm.cursor)
            while db.global_context.pc == pc:
                yield from misc.fullPress(io.Key.A if choice != 0x7f else io.Key.B)
            continue
        yield io.toggle(io.Key.A)
    return 0

def talkTo(local_id, choices=[]):
    """
    Move to and talk to an NPC, optionally with predefined choices
    """
    while db.global_context.pc == 0:
        yield from movement.toPers(local_id)
        yield from misc.fullPress(io.Key.A)
    return (yield from doInteraction(choices))
