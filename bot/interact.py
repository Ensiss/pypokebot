import numpy as np
import memory; mem = memory.Memory
import database; db = database.Database
import core.io; io = core.io.IO
from bot import Bot
import script
import misc
import movement

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
