from itertools import permutations
import numpy as np
import enum
import utils
import memory; mem = memory.Memory
import database; db = database.Database

class Status(enum.IntEnum):
    SLEEP = 0
    POISON = enum.auto()
    BURN = enum.auto()
    FREEZE = enum.auto()
    PARALYSIS = enum.auto()
    BAD_POISON = enum.auto()

class IPokeData(utils.RawStruct, utils.AutoUpdater):
    fmt = ""
    def __init__(self, addr):
        super().__init__(addr)

    def _getMultiplier(self, n, d):
        r = (abs(n) + d) / d
        return 1/r if n < 0 else r

    def checkStatus(self, status):
        if (status == Status.SLEEP):
            return self.status & 7
        return bool(self.status & (1 << (status + 2)))

    def getRealAtk(self):
        return self.atk * self._getMultiplier(self.atk_buff, 2)
    def getRealDef(self):
        return self.defense * self._getMultiplier(self.def_buff, 2)
    def getRealSpeed(self):
        return self.speed * self._getMultiplier(self.speed_buff, 2)
    def getRealSpAtk(self):
        return self.spatk * self._getMultiplier(self.spatk_buff, 2)
    def getRealSpDef(self):
        return self.spdef * self._getMultiplier(self.spdef_buff, 2)
    def getRealAccuracy(self):
        return 100 * self._getMultiplier(self.accuracy_buff, 3)
    def getRealEvasion(self):
        return 100 * self._getMultiplier(self.evasion_buff, 3)

    def isSleeping(self):
        return self.checkStatus(Status.SLEEP)
    def isPoisoned(self):
        return self.checkStatus(Status.POISON)
    def isBurned(self):
        return self.checkStatus(Status.BURN)
    def isFrozen(self):
        return self.checkStatus(Status.FREEZE)
    def isParalysed(self):
        return self.checkStatus(Status.PARALYSIS)
    def isBadlyPoisoned(self):
        return self.checkStatus(Status.BAD_POISON)

    def typeEffectiveness(self, move):
        return self.species.typeEffectiveness(move)

    def sameTypeAttackBonus(self, move):
        return self.species.sameTypeAttackBonus(move)

    def chanceToHit(self, target, move):
        if type(move) is int:
            move = db.moves[move]
        return move.accuracy * (self.getRealAccuracy() / target.getRealEvasion())

    def potentialDamage(self, target, move):
        if type(move) is int:
            move = db.moves[move]
        if move.power == 0:
            return 0, 0
        atk = self.getRealSpAtk() if move.isSpecial() else self.getRealAtk()
        defense = target.getRealSpDef() if move.isSpecial() else target.getRealDef()
        stab = self.sameTypeAttackBonus(move)
        effectiveness = target.typeEffectiveness(move)
        dmg = 2.0 * self.level / 5.0 + 2
        dmg = (dmg * atk * move.power) / defense
        dmg = (dmg / 50.0) + 2
        dmg = dmg * stab * effectiveness
        return dmg * 217 / 255, dmg

class BattleData(IPokeData):
    fmt = mem.Unpacker("6H(4H)I(8B)4B(4B)H2B2H11SB8S5I")
    def update(self):
        (self.species_idx,
         self.atk,
         self.defense,
         self.speed,
         self.spatk,
         self.spdef,
         move_ids,
         self.ivs,
         buffs,
         self.ability,
         self.type1,
         self.type2,
         self.padding,
         self.pps,
         self.curr_hp,
         self.level,
         self.happiness,
         self.max_hp,
         self.item,
         self.nick,
         self.unknown,
         self.ot_name,
         self.padding2,
         self.pid,
         self.status,
         self.status2,
         self.ot_id) = self.unpack()
        (self.hp_buff,
         self.atk_buff,
         self.def_buff,
         self.speed_buff,
         self.spatk_buff,
         self.spdef_buff,
         self.accuracy_buff,
         self.evasion_buff) = (x - 6 for x in buffs)
        self.move_ids = move_ids
        self.moves = [db.moves[idx] for idx in move_ids if idx != 0]
        self.species = db.species[self.species_idx]

class PokemonData(IPokeData):
    fmt = mem.Unpacker("2I10SH7SBH2x48sI2B7H")
    def update(self):
        (self.personality,
         self.ot_id,
         self.nick,
         self.lang,
         self.ot_name,
         self.markings,
         self.checksum,
         self.data,
         self.status,
         self.level,
         self.pokerus,
         self.curr_hp,
         self.max_hp,
         self.atk,
         self.defense,
         self.speed,
         self.spatk,
         self.spdef) = self.unpack()
        self.hp_buff = 0
        self.atk_buff = 0
        self.def_buff = 0
        self.speed_buff = 0
        self.spatk_buff = 0
        self.spdef_buff = 0
        self.accuracy_buff = 0
        self.evasion_buff = 0

        # Decrypt substructures
        key = self.personality ^ self.ot_id
        order = list(permutations(range(4)))[self.personality % 24]
        sub_types = [Growth, Attacks, EVs, Misc]
        xored = (np.frombuffer(self.data, dtype=np.uint32) ^ key).tobytes()
        subs = [None] * 4
        for i in range(4):
            subs[order[i]] = sub_types[order[i]](12 * i, xored)
        (self.growth,
         self.attacks,
         self.evs,
         self.misc) = subs

        self.species = db.species[self.growth.species_idx]

class Growth(utils.RawStruct):
    fmt = "2HI2BH"
    def __init__(self, addr, buf):
        (self.species_idx,
         self.item,
         self.xp,
         self.pp_up,
         self.friendship,
         self.unknown) = super().__init__(addr, buf)

class Attacks(utils.RawStruct):
    fmt = mem.Unpacker("(4H)(4B)")
    def __init__(self, addr, buf):
        (self.move_ids,
         self.pps) = super().__init__(addr, buf)
        self.moves = [db.moves[idx] for idx in self.move_ids if idx != 0]

class EVs(utils.RawStruct):
    fmt = "12B"
    def __init__(self, addr, buf):
        (self.hp,
         self.atk,
         self.defense,
         self.speed,
         self.spatk,
         self.spdef,
         self.coolness,
         self.beauty,
         self.cuteness,
         self.smartness,
         self.toughness,
         self.feel) = super().__init__(addr, buf)

class Misc(utils.RawStruct):
    fmt = "2BH2I"
    def __init__(self, addr, buf):
        (self.pokerus,
         self.met_location,
         self.origins_info,
         self.iv_egg_ability,
         self.ribbons) = super().__init__(addr, buf)

