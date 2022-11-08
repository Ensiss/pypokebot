import utils
import numpy as np
import enum
import memory; mem = memory.Memory
import database; db = database.Database

class Status(enum.IntEnum):
    SLEEP = 0
    POISON = enum.auto()
    BURN = enum.auto()
    FREEZE = enum.auto()
    PARALYSIS = enum.auto()
    BAD_POISON = enum.auto()

class IPokeData(utils.RawStruct):
    fmt = ""
    def __init__(self, addr):
        return super().__init__(addr)

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
        atk = self.getRealSpAtk() if move.isSpecial() else self.getRealAtk()
        defense = self.getRealSpDef() if move.isSpecial() else self.getRealDef()
        stab = self.sameTypeAttackBonus(move)
        effectiveness = target.typeEffectiveness(move)
        dmg = 2.0 * self.level / 5.0 + 2
        dmg = (dmg * atk * move.power) / defense
        dmg = (dmg / 50.0) + 2
        dmg = dmg * stab * effectiveness
        return dmg * 217 / 255, dmg

class BattleData(IPokeData):
    fmt = "10HI16BH2B2H11SB8S5I"
    def __init__(self, addr):
        unpacked = super().__init__(addr)
        (self.species_idx,
         self.atk,
         self.defense,
         self.speed,
         self.spatk,
         self.spdef) = unpacked[:6]
        self.moves[4] = list(unpacked[6:10])
        self.ivs = unpacked[10]
        (self.hp_buff,
         self.atk_buff,
         self.def_buff,
         self.speed_buff,
         self.spatk_buff,
         self.spdef_buff,
         self.accuracy_buff,
         self.evasion_buff) = (x - 6 for x in unpacked[11:19])
        (self.ability,
         self.type1,
         self.type2,
         self.padding) = unpacked[19:23]
        self.pps[4] = list(unpacked[23:27])
        (self.curr_hp,
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
         self.ot_id) = unpacked[27:]
        self.species = db.species[self.species_idx]

class PokemonData(IPokeData):
    fmt = "2I10SH7SBH2x48sI2B7H"
    def __init__(self, addr):
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
         self.spdef) = super().__init__(addr)
        self.hp_buff = 0
        self.atk_buff = 0
        self.def_buff = 0
        self.speed_buff = 0
        self.spatk_buff = 0
        self.spdef_buff = 0
        self.accuracy_buff = 0
        self.evasion_buff = 0

        # Decrypt substructures
        sub_types = [Growth, Attacks, EVs, Misc]
        subs = [None] * 4
        nmax = 24
        pick = np.uint8((1 << 4) - 1)
        key = self.personality ^ self.ot_id
        order = self.personality % 24
        self.xored = (np.frombuffer(self.data, dtype=np.uint32) ^ key).tobytes()
        for n in range(4, 0, -1):
            nmax /= n
            i = order / nmax
            order %= nmax
            count = -1
            for j in range(4):
                if pick & (1 << j):
                    count += 1
                    if count == i:
                        break
            pick &= np.uint8(~(1 << j))
            subs[j] = sub_types[j](4 * 3 * (4 - n), self.xored)
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
    fmt = "4H4B"
    def __init__(self, addr, buf):
        unpacked = super().__init__(addr, buf)
        self.moves = list(unpacked[:4])
        self.pps = list(unpacked[4:])

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

