import sys
sys.path += ["core", "bot"]
import memory; mem = memory.Memory
import database; db = database.Database
import misc

def turn(btn):
    dirs = [mem.core.KEY_DOWN,
            mem.core.KEY_UP,
            mem.core.KEY_LEFT,
            mem.core.KEY_RIGHT]
    if btn not in dirs:
        print("turn error: button %d is not a direction" % btn)
        return -1

    counter = 0
    ow = db.getOWObject(0) # Player's sprite
    yield from misc.waitWhile(lambda: db.getPlayerState() != db.PlayerState.STATIC)
    if dirs[ow.dir] != btn:
        while db.getPlayerState() != db.PlayerState.TURN:
            if mem.core.frame_counter % 2 == 0:
                mem.core.clear_keys(btn)
            else:
                mem.core.set_keys(btn)
            yield

    mem.core.set_keys()
    yield from misc.waitWhile(lambda: db.getPlayerState() == db.PlayerState.TURN)
    return 0
