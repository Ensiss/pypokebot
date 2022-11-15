import memory; mem = memory.Memory
import utils

class Player(utils.AutoUpdater):
    def update(self):
        map_offset = mem.readU32(0x3005008)
        data_offset = mem.readU32(0x300500C)
        self.valid = (map_offset != 0 and data_offset != 0)
        (self.x,
         self.y,
         self.bank_id,
         self.map_id) = mem.unpack(map_offset, "2H2B")
        (self.name,
         self.gender,
         self.unknown,
         self.trainer_id) = mem.unpack(data_offset, "8S2BH")
        self.map_offset = map_offset
        self.data_offset = data_offset
