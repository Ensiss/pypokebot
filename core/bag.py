import enum
import struct

import memory; mem = memory.Memory
import database; db = database.Database
import utils

class Bag(utils.AutoUpdater, list):
    def __init__(self):
        super().__init__()
        self.update()

    def update(self):
        self.clear()
        ptr = mem.readU32(0x0300500C)
        if ptr == 0:
            self += [[]] * 5
        else:
            self.key = mem.readU16(ptr + 0x0F20)
            pocket_sz = struct.calcsize(Pocket.fmt)
            for i in range(5):
                self.append(Pocket(self, 0x0203988C + i * pocket_sz))

    def getItemLoc(self, item):
        if type(item) is int:
            item = db.items[item]
        item_id = item.index
        pocket_id = item.pocket - 1
        pocket = self[pocket_id]
        for cursor, inbag_item in enumerate(pocket):
            if inbag_item.idx == item_id:
                return pocket_id, cursor
        return None, None

    def getBagItem(self, item):
        pocket, cursor = self.getItemLoc(item)
        if cursor is None:
            return None
        return self[pocket][cursor]

    def hasItem(self, item):
        pocket, cursor = self.getItemLoc(item)
        if cursor is None or self[pocket][cursor].quantity == 0:
            return False
        return True

class Pocket(utils.RawStruct, list):
    class Type(enum.IntEnum):
        MAIN = 0
        KEY_ITEMS = enum.auto()
        BALLS = enum.auto()
        TMS = enum.auto()
        BERRIES = enum.auto()

    fmt = "2I"
    def __init__(self, bag, addr):
        self.bag = bag
        (self.items_ptr,
         self.capacity) = super().__init__(addr)
        item_sz = struct.calcsize(BagItem.fmt)
        for i in range(self.capacity):
            item = BagItem(self.items_ptr + i * item_sz, bag.key)
            if item.quantity > 0:
                self.append(item)

class BagItem(utils.RawStruct):
    fmt = "2H"
    def __init__(self, addr, key):
        (self.idx,
         self.quantity) = super().__init__(addr)
        self.quantity ^= key
        self.item = db.items[self.idx]
