import mgba.core
import struct
import re

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
    def __init__(self, core):
        self.core = core

        self.wram = Buffer(2, (lambda: core._native.memory.wram), core.memory.wram.size)
        self.iram = Buffer(3, (lambda: core._native.memory.iwram), core.memory.iwram.size)
        self.io = Buffer(4, (lambda: core._native.memory.io), core.memory.io.size)
        self.vram = Buffer(6, (lambda: core._native.video.vram), core.memory.vram.size)
        self.oam = Buffer(7, (lambda: core._native.video.oam.raw), core.memory.oam.size)
        self.rom = Buffer(8, (lambda: core._native.memory.rom), core.memory.rom.size)

        self.memmap = [self.wram, # 0x2000000
                       self.iram, # 0x3000000
                       self.io,   # 0x4000000
                       None,
                       self.vram, # 0x6000000
                       self.oam,  # 0x7000000
                       self.rom]  # 0x8000000

    def unpack(self, addr, fmt, buf=None):
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
            buf = self.memmap[mapIdx(addr)]
        expanded = None
        if "S" in fmt:
            expanded = _expandFmt(fmt)
            old_fmt = fmt
            fmt = fmt.replace("S", "s")
        unpacked = struct.unpack_from("<"+fmt, buf.buf, addr & 0xFFFFFF)
        if expanded is not None:
            if len(unpacked) != len(expanded):
                print("Unpack: incorrect expansion '%s' @ 0x%08X" % (old_fmt, addr))
                return unpacked
            unpacked = tuple((utils.pokeToAscii(x) if expanded[i] == "S" else x) for i,x in enumerate(unpacked))
        return unpacked

def unpack(addr, fmt, buf=None):
    return Memory.instance.unpack(addr, fmt, buf)
def readU8(addr, buf=None):
    return Memory.instance.unpack(addr, "B", buf)[0]
def readU16(addr, buf=None):
    return Memory.instance.unpack(addr, "H", buf)[0]
def readU32(addr, buf=None):
    return Memory.instance.unpack(addr, "I", buf)[0]
def readS8(addr, buf=None):
    return Memory.instance.unpack(addr, "b", buf)[0]
def readS16(addr, buf=None):
    return Memory.instance.unpack(addr, "h", buf)[0]
def readS32(addr, buf=None):
    return Memory.instance.unpack(addr, "i", buf)[0]
def readPokeStr(addr, delim=b'\xff', max_sz=-1, buf=None):
    """
    Read and decode a Poke string at 'addr',
    until 'max_sz' or the specified delimiter is reached
    """
    if buf is None:
        buf = Memory.instance.memmap[mapIdx(addr)]
    out = ""
    addr = addr & 0xFFFFFF
    i = 0
    while buf.buf[addr+i:addr+i+len(delim)] != delim and (max_sz < 0 or i < max_sz):
        out += utils.charset[buf.buf[addr + i][0]]
        i += 1
    return out

def init(core):
    if not hasattr(Memory, "instance"):
        Memory.instance = Memory(core)
    return Memory.instance

def updateBuffers():
    for buf in Memory.instance.memmap:
        if buf is not None:
            buf.update()

def mapIdx(addr):
    """
    Returns the memory map index of a given address
    """
    return (addr >> 24) - 2
