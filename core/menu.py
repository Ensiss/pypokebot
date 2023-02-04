import memory; mem = memory.Memory
import database; db = database.Database
import utils

class BattleMenu(utils.RawStruct, utils.AutoUpdater):
    fmt = "2BHB"
    def __init__(self):
        super().__init__(0x02023E82)

    def update(self):
        (self.submenu,
         self.state,
         self.unknown,
         self.battle) = self.unpack()
        (self.cursor,
         self.attack) = mem.unpack(0x02023FF8, "2I")
        open_raw = mem.readU8(0x02020014)
        self.is_open = (open_raw == 1 or open_raw == 8)
        self.menu = 0 if self.submenu == 1 else self.cursor + 1

class BagMenu(utils.RawStruct, utils.AutoUpdater):
    fmt = mem.Unpacker("2BH[3H][3H]")
    def __init__(self):
        super().__init__(0x0203AD00)

    def update(self):
        (self.unknown,
         self.is_open,
         self.pocket,
         self.cursors,
         self.scrolls) = self.unpack()
        (self.scroll,
         self.cursor) = mem.unpack(0x030050D8, "2H")

class StartMenu(utils.RawStruct, utils.AutoUpdater):
    fmt = mem.Unpacker("I2B[9B]B")
    def __init__(self):
        super().__init__(0x020370F0)

    def update(self):
        (self.active_ctx,
         self.cursor,
         self.nb_items,
         self.item_idxs,
         self.state) = self.unpack()
        dialog = mem.unpack(0x020204C0, "12s")[0]
        # TODO: find something more robust/clean
        start_bytes = b"\x00\x16\x01\x07\x0d\x0f\x3d\x01\x60\x2d\x00\x02"
        self.is_open = (dialog == start_bytes)

class MultiChoice(utils.RawStruct):
    fmt = "IB3x"

    def __init__(self, addr):
        (self.str_table,
         self.nb_choices) = super().__init__(addr)
        self.choices = []
        for i in range(self.nb_choices):
            str_ptr = mem.readU32(self.str_table + i * 8)
            self.choices.append(mem.readPokeStr(str_ptr))

    def __str__(self):
        choices = ", ".join(["%d:%s"%x for x in enumerate(self.choices)])
        return "MultiChoice@0x%08X: %s" % (self.addr, choices)
