import mgba.core
import struct

class Memory():
    def __init__(self, core):
        self.wram = mgba.ffi.buffer(core._native.memory.wram, core.memory.wram.size)
        self.iram = mgba.ffi.buffer(core._native.memory.iwram, core.memory.iwram.size)
        self.io = mgba.ffi.buffer(core._native.memory.io, core.memory.io.size)
        self.vram = mgba.ffi.buffer(core._native.video.vram, core.memory.vram.size)
        self.oam = mgba.ffi.buffer(core._native.video.oam.raw, core.memory.oam.size)
        self.rom = mgba.ffi.buffer(core._native.memory.rom, core.memory.rom.size)

        self.memmap = [None,
                       None,
                       self.wram, # 0x2000000
                       self.iram, # 0x3000000
                       self.io,   # 0x4000000
                       None,
                       self.vram, # 0x6000000
                       self.oam,  # 0x7000000
                       self.rom]  # 0x8000000

    def mapIdx(self, addr):
        """
        Returns the memory map index of a given address
        """
        return (addr & 0xFF000000) >> 24

    def unpack(self, addr, fmt, buf=None):
        """
        Unpack variables at 'addr' using formating from the struct module
        Endian is automatically added to the formatting string
        If 'buf' is not specified, infer the buffer from the address
        """
        if buf is None:
            buf = self.memmap[self.mapIdx(addr)]
        return struct.unpack_from("<"+fmt, buf, addr & 0xFFFFFF)

    def readU8(self, addr, buf=None):
        return self.unpack(addr, "B", buf)[0]
    def readU16(self, addr, buf=None):
        return self.unpack(addr, "H", buf)[0]
    def readU32(self, addr, buf=None):
        return self.unpack(addr, "I", buf)[0]
    def readS8(self, addr, buf=None):
        return self.unpack(addr, "b", buf)[0]
    def readS16(self, addr, buf=None):
        return self.unpack(addr, "h", buf)[0]
    def readS32(self, addr, buf=None):
        return self.unpack(addr, "i", buf)[0]
