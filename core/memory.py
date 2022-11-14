import struct
import re
import mgba

import utils

class Buffer():
    def __init__(self, idx, get_addr, size):
        self.getAddr = get_addr

        self.idx = idx
        self.addr = 0
        self.size = size
        self.buf = None
        self.update()

    def update(self):
        new_addr = self.getAddr()
        if self.addr != new_addr:
            self.addr = new_addr
            self.buf = mgba.ffi.buffer(self.addr, self.size)

class Memory(object):
    def init(core):
        if hasattr(Memory, "core"):
            return
        Memory.core = core

        Memory.wram = Buffer(2, (lambda: core._native.memory.wram), core.memory.wram.size)
        Memory.iram = Buffer(3, (lambda: core._native.memory.iwram), core.memory.iwram.size)
        Memory.io = Buffer(4, (lambda: core._native.memory.io), core.memory.io.size)
        Memory.vram = Buffer(6, (lambda: core._native.video.vram), core.memory.vram.size)
        Memory.oam = Buffer(7, (lambda: core._native.video.oam.raw), core.memory.oam.size)
        Memory.rom = Buffer(8, (lambda: core._native.memory.rom), core.memory.rom.size)

        Memory.memmap = [Memory.wram, # 0x2000000
                         Memory.iram, # 0x3000000
                         Memory.io,   # 0x4000000
                         None,
                         Memory.vram, # 0x6000000
                         Memory.oam,  # 0x7000000
                         Memory.rom]  # 0x8000000

    def unpack(addr, fmt, buf=None):
        """
        Unpack variables at 'addr' using formating from the struct module
        Endian is automatically added to the formatting string
        If 'buf' is not specified, the buffer is inferred from the address
        An additional format "S" automatically decodes Pokemon charset strings
        """
        def _expandFmt(fmt):
            """
            Expands repeat counters in format strings
            Ex: 4B8s2i -> BBBBsii
            """
            out = []
            for group in re.findall("\d*\w", fmt):
                char = group[-1]
                if char == "x":
                    continue
                repeat = 1
                if len(group) > 1 and char.lower() != "s":
                    repeat = int(group[:-1])
                out += char * repeat
            return out

        if buf is None:
            buf = Memory.memmap[mapIdx(addr)]
        if type(buf) is Buffer:
            buf = buf.buf
        expanded = None
        if "S" in fmt:
            expanded = _expandFmt(fmt)
            old_fmt = fmt
            fmt = fmt.replace("S", "s")
        unpacked = struct.unpack_from("<"+fmt, buf, addr & 0xFFFFFF)
        if expanded is not None:
            if len(unpacked) != len(expanded):
                print("Unpack: incorrect expansion '%s' @ 0x%08X" % (old_fmt, addr))
                return unpacked
            unpacked = tuple((utils.pokeToAscii(x) if expanded[i] == "S" else x) for i,x in enumerate(unpacked))
        return unpacked

    def readU8(addr, buf=None):
        return Memory.unpack(addr, "B", buf)[0]
    def readU16(addr, buf=None):
        return Memory.unpack(addr, "H", buf)[0]
    def readU32(addr, buf=None):
        return Memory.unpack(addr, "I", buf)[0]
    def readS8(addr, buf=None):
        return Memory.unpack(addr, "b", buf)[0]
    def readS16(addr, buf=None):
        return Memory.unpack(addr, "h", buf)[0]
    def readS32(addr, buf=None):
        return Memory.unpack(addr, "i", buf)[0]
    def readPokeStr(addr, delim=b'\xff', max_sz=-1, buf=None):
        """
        Read and decode a Poke string at 'addr',
        until 'max_sz' or the specified delimiter is reached
        """
        if buf is None:
            buf = Memory.memmap[mapIdx(addr)]
        if type(buf) is Buffer:
            buf = buf.buf
        out = ""
        addr = addr & 0xFFFFFF
        i = 0
        while buf[addr+i:addr+i+len(delim)] != delim and (max_sz < 0 or i < max_sz):
            out += utils.charset[buf[addr + i][0]]
            i += 1
        return out
    def readPokeList(addr, str_sz, delim=b'\x00', buf=None):
        """
        Read and decode a list of Poke strings of 'str_sz' bytes
        until the delimiter is reached
        """
        if buf is None:
            buf = Memory.memmap[mapIdx(addr)]
        if type(buf) is Buffer:
            buf = buf.buf
        addr = addr & 0xFFFFFF
        out = []
        while buf[addr:addr+len(delim)] != delim:
            out.append(utils.pokeToAscii(buf[addr:addr+str_sz]))
            addr += str_sz
        return out

    def updateBuffers():
        for buf in Memory.memmap:
            if buf is not None:
                buf.update()

def mapIdx(addr):
    """
    Returns the memory map index of a given address
    """
    return (addr >> 24) - 2
