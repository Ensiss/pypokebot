import memory; mem = memory.Memory
import database; db = database.Database
import core.io; io = core.io.IO
import misc

def attack(atk_id):
    bm = db.battle_menu

    if bm.menu != 0:
        return -1
    # Select the attack menu
    yield from misc.moveCursor(2, 0, lambda: bm.cursor)
    while bm.menu == 0:
        yield from misc.fullPress(io.Key.A)
    # Select the corresponding attack
    yield from misc.moveCursor(2, atk_id, lambda: bm.attack)
    while bm.is_open == 1:
        yield from misc.fullPress(io.Key.A)
    return 0
