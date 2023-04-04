import numpy as np
import memory; mem = memory.Memory
import database; db = database.Database
import core.io; io = core.io.IO
from bot import Bot
import script
import misc
import movement
import world

def readSign(info, choices=[]):
    """
    Move to and interact with a sign event, optionally with predefined choices
    """
    if (sign := world.SignEvent.get(info)) is None:
        return -1
    Bot.instance.watchInteraction(script.Script.getSign(sign.data_idx), choices)
    while Bot.instance.tgt_script:
        if (yield from movement.toSign(sign)) == -1:
            return -1
        yield from misc.fullPress(io.Key.A)

def talkTo(info, choices=[]):
    """
    Move to and talk to an NPC, optionally with predefined choices
    """
    if (pers := world.PersonEvent.get(info)) is None:
        return -1
    Bot.instance.watchInteraction(script.Script.getPerson(pers.data_idx), choices)
    while Bot.instance.tgt_script:
        if (yield from movement.toPers(pers)) == -1:
            return -1
        yield from misc.fullPress(io.Key.A)
