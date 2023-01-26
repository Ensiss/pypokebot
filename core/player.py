import memory; mem = memory.Memory
import utils

class Player(utils.AutoUpdater):
    def update(self):
        saveblock1_offset = mem.readU32(0x3005008)
        saveblock2_offset = mem.readU32(0x300500C)
        self.valid = (saveblock1_offset != 0 and saveblock2_offset != 0)
        (self.x,
         self.y,
         self.bank_id,
         self.map_id) = mem.unpack(saveblock1_offset, "2H2B")
        (self.name,
         self.gender,
         self.unknown,
         self.trainer_id) = mem.unpack(saveblock2_offset, "8S2BH")
        encryption_key = mem.readU32(saveblock2_offset + 0xF20)
        self.money = mem.readU32(saveblock1_offset + 0x290) ^ encryption_key
        self.coins = mem.readU16(saveblock1_offset + 0x294) ^ (encryption_key & 0xFFFF)
        self.saveblock1_offset = saveblock1_offset
        self.saveblock2_offset = saveblock2_offset

class Pokedex(utils.AutoUpdater):
    def update(self):
        saveblock2_offset = mem.readU32(0x300500C)
        dex_offset = saveblock2_offset + 0x18
        unpacked = mem.unpack(dex_offset, "4B3I52B52B")
        (self.order,
         self.mode,
         self.national_magic,
         self.unknown,
         self.unown_personality,
         self.spinda_personality,
         self.unknown2) = unpacked[:7]
        self.owned = unpacked[7:59]
        self.seen = unpacked[59:]

    # idx-1 is used because species start with '??????' at idx 0
    # but the pokedex skips it and starts with bulbasaur at idx 0
    def hasSeen(self, idx):
        if idx <= 0:
            return False
        return utils.getFlagFrom(self.seen, idx-1)
    def hasOwned(self, idx):
        if idx <= 0:
            return False
        return utils.getFlagFrom(self.owned, idx-1)
