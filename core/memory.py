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
        Memory.core = core
        Memory.frame_counter = Memory.core.frame_counter

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

    class Unpacker:
        """
        Custom binary reading helper designed to extend the struct module.
        Pre-compiles the format for faster execution.
        Modifications over struct module:
        - 'S' acts like 's' but also automatically decodes from Pokemon charset
        - '.7B' uses only the first 7 bits of the field for a given variable
        - '.7.1B' returns two variables of 7 and 1 bits each from a single byte
        - '4.2B' defines 4 variables of 3 bits each, covering a full byte
        - '(4B)' returns a tuple of 4 bytes instead of 4 individual variables
        - '[4B]' returns an array of 4 bytes instead of 4 individual variables
        """
        def __init__(self, fmt):
            self.no_sub = (lambda l, elm: l.extend(elm))
            self.subs = {"(": ("(", ")", lambda l, elm: l.append(elm)),
                         "[": ("[", "]", lambda l, elm: l.append(tuple(elm)))}
            self.fmt = fmt
            self.varcount = 0
            self.native_fmt = ""
            self.groups = []
            self.decode_list = []
            self.parse(fmt)
            self.size = struct.calcsize(self.native_fmt)

        def unpack(self, buf, addr):
            unpacked = list(struct.unpack_from("<"+self.native_fmt, buf, addr))
            out = []
            # Decode poke strings
            for idx in self.decode_list:
                unpacked[idx] = utils.pokeToAscii(unpacked[idx])
            # Pack data
            idx = 0
            for sz, func in self.groups:
                func(out, unpacked[idx:idx+sz])
                idx += sz
            return out

        def parse(self, fmt, idx=0, sub=None):
            group_sz = 0
            curr_bits = 0
            paren = None
            while idx < len(fmt):
                if sub is None and fmt[idx] in self.subs:
                    if group_sz > 0:
                        self.groups.append((group_sz, self.no_sub))
                        group_sz = 0
                    idx = self.parse(fmt, idx+1, self.subs[fmt[idx]])
                    continue
                elif sub is not None and fmt[idx] == sub[1]:
                    self.groups.append((group_sz, sub[2]))
                    return idx + 1
                res = re.match("\d*(?:\.\d+)?[a-zA-Z]", fmt[idx:])
                if res is None:
                    raise SyntaxError("Invalid format: %s" % fmt[idx:])
                group = res.group()
                char = group[-1]
                repeat = 1
                repeat_match = re.match("\d+", group)
                if repeat_match:
                    repeat = int(repeat_match.group(0))
                if repeat <= 0:
                    raise SyntaxError("Format repeater has to be positive: %s" % fmt[idx:])
                native_char = "s" if char == "S" else char
                if native_char == "s":
                    self.varcount += 1
                elif native_char != "x":
                    self.varcount += repeat
                if char == "S":
                    self.decode_list.append(self.varcount-1)
                repeat_str = str(repeat) if repeat > 1 else ""
                self.native_fmt += '%s%c' % (repeat_str, native_char)
                group_sz += repeat
                idx += res.end()
            if group_sz > 0:
                self.groups.append((group_sz, self.no_sub))
            return idx

    def unpackRaw(addr, fmt, buf=None):
        """
        Unpack variables at 'addr' using formating from the struct module
        Endian is automatically added to the formatting string
        If 'buf' is not specified, the buffer is inferred from the address
        """
        buf = Memory.bufferFromAddr(addr, buf)
        return struct.unpack_from("<"+fmt, buf, addr & 0xFFFFFF)
    def unpack(addr, unpacker, buf=None):
        """
        Unpack variables at 'addr' using custom Unpacker formating
        Endian is automatically added to the formatting string
        If 'buf' is not specified, the buffer is inferred from the address
        """
        if type(unpacker) is str:
            return Memory.unpackRaw(addr, unpacker, buf)
        buf = Memory.bufferFromAddr(addr, buf)
        return unpacker.unpack(buf, addr & 0xFFFFFF)

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
        buf = Memory.bufferFromAddr(addr, buf)
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
        buf = Memory.bufferFromAddr(addr, buf)
        addr = addr & 0xFFFFFF
        out = []
        while buf[addr:addr+len(delim)] != delim:
            out.append(utils.pokeToAscii(buf[addr:addr+str_sz]))
            addr += str_sz
        return out

    def hexdump(addr, sz, buf=None):
        buf = Memory.bufferFromAddr(addr, buf)
        addr = addr & 0xFFFFFF
        out = ""
        translation = ""
        for i in range(sz):
            if i % 16 == 0:
                out += "%08x  " % (addr + i)
            out += "%02x " % buf[addr + i][0]
            c = utils.charset[buf[addr + i][0]].replace("\n", " ")
            if not c.isprintable() or len(c) == 0:
                c = "."
            translation += c
            if i % 8 == 7:
                out += " "
            if i % 16 == 15:
                out += "|%s|\n" % translation
                translation = ""
        if out[-1] != "\n":
            out += "\n"
        print(out, end="")

    def updateBuffers():
        Memory.frame_counter = Memory.core.frame_counter
        for buf in Memory.memmap:
            if buf is not None:
                buf.update()

    def bufferFromAddr(addr, buf=None):
        if buf is None:
            buf = Memory.memmap[mapIdx(addr)]
        if type(buf) is Buffer:
            buf = buf.buf
        return buf

def mapIdx(addr):
    """
    Returns the memory map index of a given address
    """
    return (addr >> 24) - 2
