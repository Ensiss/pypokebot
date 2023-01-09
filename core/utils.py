import numpy as np
import struct
import memory; mem = memory.Memory

class RawStruct:
    fmt = ""
    def __init__(self, addr, buf=None):
        super().__init__()
        self.addr = addr
        self.buf = buf
        return self.unpack()

    def unpack(self):
        return mem.unpack(self.addr, self.fmt, self.buf)

class AutoUpdater:
    """
    AutoUpdater class which automatically updates its variables before access
    when dirty. The update method must be overridden for this to work.
    """
    def __init__(self):
        super().__init__()
        self._last_update = 0

    @classmethod
    def lock(cls):
        """ Lock updates. Improves performance when many attributes call are
        needed in a single frame """
        cls.__getattribute__ = object.__getattribute__
        cls.__getitem__ = list.__getitem__

    @classmethod
    def unlock(cls):
        """ Unlock and resume auto updates """
        cls.__getitem__ = cls.__unlocked_getitem__
        cls.__getattribute__ = cls.__unlocked_getattribute__

    def _checkUpdate(self):
        if mem.frame_counter > object.__getattribute__(self, "_last_update"):
            self._last_update = mem.frame_counter
            object.__getattribute__(self, "update")()

    def __unlocked_getitem__(self, idx):
        if mem.frame_counter > object.__getattribute__(self, "_last_update"):
            self._last_update = mem.frame_counter
            object.__getattribute__(self, "update")()
        return list.__getitem__(self, idx)

    def __unlocked_getattribute__(self, name):
        if mem.frame_counter > object.__getattribute__(self, "_last_update"):
            self._last_update = mem.frame_counter
            object.__getattribute__(self, "update")()
        return object.__getattribute__(self, name)

    __getattribute__ = __unlocked_getattribute__
    __getitem__ = __unlocked_getitem__

    def update(self):
        raise Exception("Please override 'update' when inheriting AutoUpdater")

def rawArray(struct_cls, addr, count, size=-1):
    if size == -1:
        size = struct.calcsize(struct_cls.fmt.replace("S", "s"))
    return [struct_cls(addr+i*size) for i in range(count)]

charset = np.zeros(256, dtype=str)
charset[:] = "?"
charset[0x00] = " "
charset[0x01:0x15] = list("AAACEEEEI?IIOOOOUUUN")
charset[0x16:0x2A] = list("aa?ceeeei?iioooouuun")
charset[0x2C:0x2F] = list(" &+")
charset[0x35] = "="
charset[0x5A:0x5E] = list("I%()")
charset[0x79:0x7D] = list("^v<>")
charset[0xA1:0xAB] = list(map(chr, range(ord('0'), ord('9')+1)))
charset[0xAB:0xBB] = list("!?.-*.\"\"''MF ,x/")
charset[0xBB:0xD5] = list(map(chr, range(ord('A'), ord('Z')+1)))
charset[0xD5:0xEF] = list(map(chr, range(ord('a'), ord('z')+1)))
charset[0xEF:0xFA] = ">:AOUaou^v<"
charset[0xFE] = "\n"
charset[0xFF] = "\x00"

def pokeToAscii(poke):
    if b'\xff' in poke:
        poke = poke[:poke.index(b'\xff')]
    return "".join([charset[x] for x in poke])

def getFlag(flag):
    offset = mem.readU32(0x3005008)
    byte = mem.readU8(offset + 0xEE0 + (flag >> 3))
    return (byte & (1 << (flag & 7))) != 0

def getVar(var):
    offset = mem.readU32(0x3005008)
    return mem.readU16(offset + 0x1000 + (var - 0x4000) * 2)
