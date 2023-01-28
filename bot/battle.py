import memory; mem = memory.Memory
import database; db = database.Database
import core.io; io = core.io.IO
import misc
import item

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

def use(item_id):
    bm = db.battle_menu

    if bm.menu != 0:
        return -1
    # Select the item menu
    yield from misc.moveCursor(2, 1, lambda: bm.cursor)
    while bm.menu == 0:
        yield from misc.fullPress(io.Key.A)
    yield from misc.wait(75)
    yield from item.select(item_id)
    while bm.menu != 0:
        yield from misc.fullPress(io.Key.A)
    return 0

def switch(poke):
    """
    Switch to the 0-indexed pokemon from the ones not already in battle
    TODO: use moveCursor instead of navigating blind
    TODO: use index from db.pteam
    """
    bm = db.battle_menu

    if bm.menu != 0:
        return -1
    # Select the switch menu
    yield from misc.moveCursor(2, 2, lambda: bm.cursor)
    while bm.menu == 0:
        yield from misc.fullPress(io.Key.A)
    # Wait animation
    yield from misc.wait(75)
    # Select party member
    yield from misc.fullPress(io.Key.RIGHT)
    for i in range(poke):
        yield from misc.fullPress(io.Key.DOWN)
    for i in range(2):
        yield from misc.fullPress(io.Key.A)
    return 0

def flee():
    bm = db.battle_menu

    if bm.menu != 0:
        return -1
    yield from misc.moveCursor(2, 3, lambda: bm.cursor)
    while bm.menu == 0:
        yield from misc.fullPress(io.Key.A)
    return 0
