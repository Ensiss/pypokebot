import memory; mem = memory.Memory
import database; db = database.Database
import core.io; io = core.io.IO
import misc
import item

def partyMenuSelect(index):
    """
    Switch to the specified pokemon from the player's party
    Assumes the party menu is already open
    """
    pm = db.party_menu

    if index >= db.getPartySize():
        return -1
    # Select party member
    while index > 0 and pm.cursor == 0:
        yield from misc.fullPress(io.Key.RIGHT)
    yield from misc.moveCursor(1, index, lambda: pm.cursor)
    yield from misc.fullPress(io.Key.A)
    return 0

def waitForPartyMenu():
    """
    Wait for the pokemon selection menu to be open
    Done by waiting until pressing the keys changes the party menu cursor
    """
    cursor = db.party_menu.cursor
    while db.party_menu.cursor == cursor:
        if db.getLastByte() in [0xFA, 0xFB]:
            yield from misc.fullPress(io.Key.A)
        else:
            yield from misc.fullPress(io.Key.RIGHT)

