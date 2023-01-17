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
        self.coins = mem.readU16(saveblock1_offset + 0x294) ^ encryption_key
        self.saveblock1_offset = saveblock1_offset
        self.saveblock2_offset = saveblock2_offset
