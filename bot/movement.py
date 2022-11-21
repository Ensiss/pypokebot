import memory; mem = memory.Memory
import database; db = database.Database
import core.io; io = core.io.IO
import misc

def turn(btn):
    if btn not in io.directions:
        print("turn error: button %d is not a direction" % btn)
        return -1

    ow = db.ows[0] # Player's sprite
    yield from misc.waitWhile(lambda: db.getPlayerState() != db.PlayerState.STATIC)
    if io.directions[ow.dir] != btn:
        while db.getPlayerState() != db.PlayerState.TURN:
            yield io.toggle(btn)

    io.releaseAll()
    yield from misc.waitWhile(lambda: db.getPlayerState() == db.PlayerState.TURN)
    return 0
