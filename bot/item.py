import memory; mem = memory.Memory
import database; db = database.Database
import core.io; io = core.io.IO
import misc

def select(item):
    if type(item) is int:
        item = db.items[item]
    item_id = item.index
    pocket, cursor = db.bag.getItemLoc(item)
    if cursor is None or db.bag[pocket][cursor].quantity == 0:
        print("Item %s not found" % item.name)
        return -1
    bm = db.bag_menu
    yield from misc.moveCursor(3, pocket, lambda: bm.pocket)
    yield from misc.moveCursor(1, cursor, lambda: bm.scroll + bm.cursor)
    yield from misc.wait(30)
    yield from misc.fullPress(io.Key.A)

