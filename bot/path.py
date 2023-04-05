import memory; mem = memory.Memory
import database; db = database.Database
import core.io; io = core.io.IO
from metafinder import Metafinder
from script import Script
import misc
import world
import movement
import interact
import battle

def follow(bot, path, explore=False):
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
            yield from bot.exploreMap()
        yield from func

def heal(bot):
    if (path := Metafinder.searchHealer()) is None:
        return -1
    yield from follow(bot, path)
    (x, y, bid, mid), pers = path[-1]
    pscript = Script.getPerson(pers.evt_nb-1, bid, mid)
    choices = []
    for ctx in pscript.execute():
        if Script.CallSpecial(0x0) in ctx.outputs:
            choices = ctx.choices
            break
    return (yield from interact.talkTo(pers, choices))
