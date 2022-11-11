import memory; mem = memory.Memory

class Player():
    def __init__(self):
        self.map_offset = mem.readU32(0x3005008)
        self.data_offset = mem.readU32(0x300500C)
        self.valid = (self.map_offset != 0 and self.data_offset != 0)
        (self.x,
         self.y,
         self.bank_id,
         self.map_id) = mem.unpack(self.map_offset, "2H2B")
        (self.name,
         self.gender,
         self.unknown,
         self.trainer_id) = mem.unpack(self.data_offset, "8S2BH")
