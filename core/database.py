import numpy as np
import struct
import enum
import utils
import world
import memory; mem = memory.Memory
import re

class Database():
    class PlayerState(enum.IntEnum):
        STATIC = 0
        TURN = enum.auto()
        WALK = enum.auto()

    def init():
        Database.species_names = mem.readPokeList(0x8245EE0, 11, b'\xae\xff')
        Database.move_names = mem.readPokeList(0x8247094, 13, b'\x00')
        Database.ability_names = mem.readPokeList(0x824FC4D, 13, b'\x00')
        Database.type_names = mem.readPokeList(0x824F1A0, 7, b'\x00')

        Database.moves = NamedDataList([Move(0x08250C04+i*12, n) for i, n in enumerate(Database.move_names)])
        Database.species = NamedDataList([Species(0x08254784+i*28, n) for i, n in enumerate(Database.species_names)])
        Database.items = NamedDataList(utils.rawArray(Item, 0x083DB028, 375))

        # Type effectiveness chart
        Database.type_chart = np.ones((18, 18))
        addr = 0x0824F050
        t1, t2, code = mem.unpack(addr, "3B")
        while t1 != 0xFF:
            if t1 < 18 and t2 < 18:
                val = 1
                if code == 0x14:
                    val = 2
                elif code == 0x05:
                    val = 0.5
                elif code == 0x00:
                    val = 0
                Database.type_chart[t1, t2] = val
            addr += 3
            t1, t2, code = mem.unpack(addr, "3B")

        # World and map data
        bankptr = 0x83526A8
        rel, nxt = mem.unpack(bankptr, "2I")
        Database.banks = []
        while nxt > 0x8000000:
            maps = []
            for addr in range(rel, nxt, 4):
                maps.append(world.Map(mem.readU32(addr)))
            Database.banks.append(maps)
            rel, nxt = mem.unpack(bankptr + len(Database.banks) * 4, "2I")
        # Load map exits in memory
        for bank in Database.banks:
            for m in bank:
                for connect in m.connects:
                    connect.findExits(m)
        # Load wild battle data
        wildptr = 0x083c9cb8
        while True:
            unpacked = mem.unpack(wildptr, "2B2x4I")
            bank_id, map_id = unpacked[:2]
            entry_ptrs = unpacked[2:]
            if bank_id == 0xFF or map_id == 0xFF:
                break
            m = Database.banks[bank_id][map_id]
            for i in range(4):
                if entry_ptrs[i] != 0:
                    wb = m.wild_battles[i]
                    wb.ratio, mon_ptr = mem.unpack(entry_ptrs[i], "B3xI")
                    nentries = (entry_ptrs[i] - mon_ptr) // 4
                    wb.entries = utils.rawArray(world.WildEntry, mon_ptr, nentries)
            wildptr += 20

        import pokedata
        import player
        import bag
        # Dynamic data
        Database.pteam = utils.rawArray(pokedata.PokemonData, 0x02024284, 6)
        Database.eteam = utils.rawArray(pokedata.PokemonData, 0x0202402C, 6)
        Database.battlers = utils.rawArray(pokedata.BattleData, 0x02023BE4, 4)
        Database.player = player.Player()
        Database.pokedex = player.Pokedex()
        Database.bag = bag.Bag()
        Database.ows = utils.rawArray(OWObject, 0x02036E38, 16)

        import menu
        # Menus
        Database.battle_menu = menu.BattleMenu()
        Database.bag_menu = menu.BagMenu()
        Database.start_menu = menu.StartMenu()
        Database.multi_choices = utils.rawArray(menu.MultiChoice, 0x083E04B0, 0x41)
        Database.party_menu = menu.PartyMenu()
        Database.multi_choice_menu = menu.MultiChoiceMenu()

        # Scripting
        Database.global_context = ScriptContext(0x03000EB0)
        Database.immediate_context = ScriptContext(0x03000F28)

        # Battle
        Database.battle_context = BattleContext()

    def plotTypeEffectiveness():
        import matplotlib.pyplot as plt
        from matplotlib.colors import LinearSegmentedColormap
        colors = ["black", "red", "grey", "green"]
        nodes = [0, 0.25, 0.5, 1]
        mycmap = LinearSegmentedColormap.from_list("mycmap", list(zip(nodes, colors)))
        plt.imshow(Database.type_chart, cmap=mycmap)
        plt.xticks(range(len(Database.type_names)), Database.type_names, rotation=45, ha='right')
        plt.yticks(range(len(Database.type_names)), Database.type_names)
        plt.show()

    def isInBattle():
        return mem.readU32(0x30030F0) == 0x80123E5

    def getPlayerState():
        """
        Returns the animation state of the player, see PlayerState
        0: static
        1: turning
        2: walking
        """
        return mem.readU8(0x203707A)

    def getCurrentMap():
        return Database.banks[Database.player.bank_id][Database.player.map_id]

    def getPartySize():
        sz = 0
        for ppoke in Database.pteam:
            if ppoke.growth.species_idx == 0:
                break
            sz += 1
        return sz

    def getScriptFlag(flag):
        offset = mem.readU32(0x3005008)
        byte = mem.readU8(offset + 0xEE0 + (flag >> 3))
        return (byte & (1 << (flag & 7))) != 0

    def getScriptVar(var):
        if var >= 0x8000:
            # 0x80xx variables are scrambled around and not in contiguous memory
            # The index list from the original source must be accessed
            offset = mem.readU32(0x0815FD0C + 4*(var - 0x8000))
            return mem.readU16(offset)
        offset = mem.readU32(0x3005008)
        return mem.readU16(offset + 0x1000 + (var - 0x4000) * 2)

class Move(utils.RawStruct):
    fmt = "9B3x"
    def __init__(self, addr, name):
        self.name = name
        (self.effect,
         self.power,
         self.type,
         self.accuracy,
         self.pp,
         self.effectAccuracy,
         self.target,
         self.priority,
         self.flags) = super().__init__(addr)

    def isSpecial(self):
        """ Whether the move uses spatk/spdef or normal stats """
        return self.type > 9

class Species(utils.RawStruct):
    fmt = "10B3H10B2x"
    def __init__(self, addr, name):
        self.name = name
        (self.hp,
         self.atk,
         self.defense,
         self.speed,
         self.spatk,
         self.spdef,
         self.type1,
         self.type2,
         self.catch_rate,
         self.base_exp_yield,
         self.effort_yield,
         self.item1,
         self.item2,
         self.gender,
         self.egg_cycles,
         self.friendship,
         self.level_up_type,
         self.egg_group1,
         self.egg_group2,
         self.ability1,
         self.ability2,
         self.safari_zone_rate,
         self.color_flip) = super().__init__(addr)

    def typeEffectiveness(self, move):
        if type(move) is int:
            move = Database.moves[move]
        eff = Database.type_chart[move.type, self.type1]
        if self.type1 != self.type2:
            eff *= Database.type_chart[move.type, self.type2]
        return eff

    def sameTypeAttackBonus(self, move):
        if type(move) is int:
            move = Database.moves[move]
        mt = move.type
        return 1 + 0.5 * (self.type1 == mt or self.type2 == mt)

class Item(utils.RawStruct):
    fmt = mem.Unpacker("14S2H2BIH2B4I")
    def __init__(self, addr):
        (self.name,
         self.index,
         self.price,
         self.hold_effect,
         self.parameter,
         self.description_ptr,
         self.mystery_value,
         self.pocket,
         self.type,
         self.field_usage_code_ptr,
         self.battle_usage,
         self.battle_usage_code_ptr,
         self.extra_parameter) = super().__init__(addr)
    def __eq__(self, other):
        if type(other) is Item:
            return other.index == self.index
        elif type(other) is int:
            return other == self.index
        return other == self

class NamedDataList(list):
    """
    Wrapper class which acts as a list, but also allows direct named access to its elements.
    Elements of the list must have a ".name" member for this to work.
    """
    def __init__(self, array):
        super().__init__(array)
        self.data = {}
        for x in self:
            if not x.name[0].isalpha():
                continue
            key = re.sub("\W", "", x.name.lower().replace(" ", "_"))
            self.data[key] = x
    def __getattr__(self, key):
        return self.data[key]

class OWObject(utils.RawStruct, utils.AutoUpdater):
    """
    Overworld Objects such as people, pickable objects, etc.
    """
    fmt = "2BH2BH4B8HI2H"
    def __init__(self, addr):
        super().__init__(addr)

    def update(self):
        (self.temp,    # Temporary variable ?
         self.flags,   # 0x01 = locked (in menu or talking)
                       # 0x10 = immovable (pokeball in Oak's lab, cuttable tree, etc.)
                       # 0x40 = off-screen
         self.unknown,
         self.unknown2,
         self.picture_nb,
         self.mvt_type,
         self.evt_nb,
         self.map_id,  # Updated by warps for the player
         self.bank_id, # Updated by warps for the player
         self.jump,    # Unknown. Set to 0x30 when jumping, 0x33 otherwise
         self.spawn_x,
         self.spawn_y,
         self.dest_x,
         self.dest_y,
         self.curr_x,
         self.curr_y,
         self.dir2,    # _dir * 11
         self.unknown5,
         self.anim,    # current OW animation ?
         self.dir,
         self.unknown6) = self.unpack()
        self.dir -= 1  # 0 = down, 1 = up, 2 = left, 3 = right
        self.dest_x -= 7
        self.dest_y -= 7
        self.curr_x -= 7
        self.curr_y -= 7
        self.x = self.curr_x
        self.y = self.curr_y

class ScriptContext(utils.RawStruct, utils.AutoUpdater):
    """
    Script context in memory
    """
    fmt = mem.Unpacker("2BHII(20I)2I(4I)")
    def __init__(self, addr):
        super().__init__(addr)

    def update(self):
        (depth,
         self.mode,
         self.cmp_result,
         self.ptr_asm,
         self.pc,
         raw_stack,
         self.cmd_table_ptr,
         self.cmd_table_max,
         self.data) = self.unpack()
        self.stack = raw_stack[:depth]

class BattleContext(utils.RawStruct, utils.AutoUpdater):
    """
    Various battle-related info
    """
    fmt = mem.Unpacker("8B")
    def __init__(self):
        super().__init__(0x02023E82)

    def update(self):
        curr_instr_ptr = mem.readU32(0x02023D74)
        self.curr_instr = mem.readU8(curr_instr_ptr)
        (self.multiuse_state,
         self.cursor, # Shared by task_id and sprite_state1
         self.sprite_state2,
         self.move_effect_byte,
         self.actions_confirmed_count,
         self.multistr_chooser,
         self.miss_type,
         self.msg_display) = self.unpack()
