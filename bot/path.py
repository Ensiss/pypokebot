import memory; mem = memory.Memory
import database; db = database.Database
import core.io; io = core.io.IO
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
