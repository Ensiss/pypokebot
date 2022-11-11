import utils
import numpy as np
import world
import memory; mem = memory.Memory

class Database():
    def init():
        if hasattr(Database, "type_chart"):
            return
        Database.species_names = mem.readPokeList(0x8245EE0, 11, b'\xae\xff')
        Database.move_names = mem.readPokeList(0x8247094, 13, b'\x00')
        Database.ability_names = mem.readPokeList(0x824FC4D, 13, b'\x00')
        Database.type_names = mem.readPokeList(0x824F1A0, 7, b'\x00')

        Database.moves = [Move(0x08250C04+i*12, n) for i, n in enumerate(Database.move_names)]
        Database.species = [Species(0x08254784+i*28, n) for i, n in enumerate(Database.species_names)]
        Database.items = utils.rawArray(Item, 0x083DB028, 375)

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
    fmt = "14S2H2BIH2B4I"
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
