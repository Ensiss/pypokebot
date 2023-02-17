import memory; mem = memory.Memory
import database; db = database.Database
import utils

class PartyMenu(utils.RawStruct, utils.AutoUpdater):
    fmt = mem.Unpacker("2I.4.2.2B2bBH[2h]")
    internal_fmt = mem.Unpacker("2I.1.3.7.7.14I[3B][8B]B[256H][16h]")
    order_fmt = mem.Unpacker("6.4B")
    def __init__(self):
        super().__init__(0x0203B0A0)

    def update(self):
        (self.exit_callback,
         self.task_ptr,
         self.menu_type,
         self.layout,
         self.choose_mon_battle_type,
         self.cursor,
         self.cursor2,
         self.action,
         self.bag_item,
         self.data) = self.unpack()
        internal_addr = mem.readU32(0x0203B09C)
        (self.internal_task_ptr,
         self.internal_exit_callback,
         self.choose_multiple,
         self.last_selected_slot,
         self.sprite_id_confirm_pokeball,
         self.sprite_id_cancel_pokeball,
         self.message_id,
         self.window_id,
         self.actions,
         self.nb_actions,
         self.pal_buffer,
         self.internal_data) = mem.unpack(internal_addr, PartyMenu.internal_fmt)
        order = mem.unpack(0x0203B0DC, PartyMenu.order_fmt)
        if all([x==0 for x in order]):
            self.order = list(range(6)) # Default order if unavailable
        else:
            self.order = [order[i] for i in [1, 0, 3, 2, 5, 4]]

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
