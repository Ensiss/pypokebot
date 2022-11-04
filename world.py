import memory as mem
import utils
import enum
import numpy as np

class WildType(enum.IntEnum):
    GRASS = 0
    WATER = enum.auto()
    ROCK = enum.auto()
    FISHING = enum.auto()

class ConnectType(enum.IntEnum):
    NONE = 0
    DOWN = enum.auto()
    UP = enum.auto()
    LEFT = enum.auto()
    RIGHT = enum.auto()
    DIVE = enum.auto()
    EMERGE = enum.auto()

class MapScriptType(enum.IntEnum):
    NONE = 0
    SETMAPTILE = enum.auto()
    VALIDATE_LOAD_1 = enum.auto()
    ENTER_NO_MENU = enum.auto()
    VALIDATE_LOAD_2 = enum.auto()
    ENTER_MENU_1 = enum.auto()
    UNKNOWN = enum.auto()
    ENTER_MENU_2 = enum.auto()

class Map():
    def __init__(self, addr):
        self.map_hdr = MapHeader(addr)
        data_hdr = self.map_hdr.data_hdr
        evt = self.map_hdr.event

        self.width = data_hdr.width
        self.height = data_hdr.height

        # Events
        self.persons = utils.rawArray(PersonEvent, evt.persons_ptr, evt.nb_persons)
        self.warps = utils.rawArray(WarpEvent, evt.warps_ptr, evt.nb_warps)
        self.scripts = utils.rawArray(ScriptEvent, evt.scripts_ptr, evt.nb_scripts)
        self.signs = utils.rawArray(SignEvent, evt.signs_ptr, evt.nb_signs)
        connect_ptr = self.map_hdr.connect_ptr
        self.connects = []
        if connect_ptr != 0:
            nb_connects, connect_ptr = mem.unpack(connect_ptr, "2I")
            self.connects = utils.rawArray(Connection, connect_ptr, nb_connects)

        # Name
        name_addr = mem.readU32(0x083F1CAC + (self.map_hdr.label_id - 88) * 4)
        self.name = mem.readPokeStr(name_addr)

        # Map data handling
        rom = mem.Memory.instance.rom.buf
        data_ptr = data_hdr.data_ptr & 0xFFFFFF
        sz = self.width * self.height
        data = np.frombuffer(rom[data_ptr:data_ptr+(2 * sz)], dtype=np.uint16)
        data = data.reshape(self.height, self.width)
        global_ptr = data_hdr.global_tileset.behavior_ptr
        local_ptr = data_hdr.local_tileset.behavior_ptr
        self.map_status = (data >> 10).astype(np.uint8)
        self.map_tile = (data & 1023)
        self.map_bg = np.zeros(data.shape, dtype=np.uint16)
        self.map_behavior = np.zeros(data.shape, dtype=np.uint16)
        tile_dict = {} # Cache tile attribute when possible
        # Fill background and behavior from tilesets
        for y, line in enumerate(self.map_tile):
            for x, t in enumerate(line):
                if t not in tile_dict:
                    if t < 640:
                        tile_dict[t] = TileAttr(global_ptr + t * 4)
                    else:
                        tile_dict[t] = TileAttr(local_ptr + (t - 640) * 4)
                tile = tile_dict[t]
                self.map_bg[y, x] = tile.bg
                self.map_behavior[y, x] = tile.behavior

    def show(self):
        import matplotlib.pyplot as plt
        plt.subplot(2, 2, 1)
        plt.imshow(self.map_behavior)
        plt.title("Behavior")
        plt.subplot(2, 2, 2)
        plt.imshow(self.map_bg)
        plt.title("Background")
        plt.subplot(2, 2, 3)
        plt.imshow(self.map_status)
        plt.title("Status")
        plt.subplot(2, 2, 4)
        plt.imshow(self.map_tile)
        plt.title("Tile")
        plt.show()


class MapHeader(utils.RawStruct):
    fmt = "4I2H4BH2B"
    def __init__(self, addr):
        (self.map_ptr,
         self.evt_ptr,
         self.script_ptr,
         self.connect_ptr,
         self.music_id,
         self.map_id,
         self.label_id,
         self.flash,
         self.weather,
         self.type,
         self.unknown,
         self.show_label,
         self.battle_type) = super().__init__(addr)
        self.data_hdr = DataHeader(self.map_ptr)
        self.event = Event(self.evt_ptr)

class DataHeader(utils.RawStruct):
    fmt = "6I2B"
    def __init__(self, addr):
        (self.width,
         self.height,
         self.border,
         self.data_ptr,
         self.global_tileset_ptr,
         self.local_tileset_ptr,
         self.border_w,
         self.border_h) = super().__init__(addr)
        self.global_tileset = TilesetHeader(self.global_tileset_ptr)
        self.local_tileset = TilesetHeader(self.local_tileset_ptr)

class TilesetHeader(utils.RawStruct):
    fmt = "2BH5I"
    def __init__(self, addr):
        (self.compressed,
         self.primary,
         self.unknown,
         self.img_ptr,
         self.palette_ptr,
         self.blocks_ptr,
         self.anim_ptr,
         self.behavior_ptr) = super().__init__(addr)

class TileAttr(utils.RawStruct):
    fmt = "2H"
    def __init__(self, addr):
        (self.behavior,
         self.bg) = super().__init__(addr)

class Event(utils.RawStruct):
    fmt = "4B4I"
    def __init__(self, addr):
        (self.nb_persons,
         self.nb_warps,
         self.nb_scripts,
         self.nb_signs,
         self.persons_ptr,
         self.warps_ptr,
         self.scripts_ptr,
         self.signs_ptr) = super().__init__(addr)

class WildHeader:
    fmt = "2B2x4I"
    def __init__(self, addr):
        unpacked = super().__init__(addr)
        (self.bank_id,
         self.map_id) = unpacked[:2]
        self.entry_ptr = list(unpacked[2:])

class MapScriptHeader(utils.RawStruct):
    fmt = "BI"
    def __init__(self, addr):
        (self.type,
         self.script_ptr) = super().__init__(addr)

class MapScript(utils.RawStruct):
    fmt = "IBHH"
    def __init__(self, addr):
        (self.script_ptr,
         self.type,
         self.var,
         self.value) = super().__init__(addr)

class SignEvent(utils.RawStruct):
    fmt = "2H2BI"
    def __init__(self, addr):
        (self.x,
         self.y,
         self.level,
         self.type,
         self.script_ptr) = super().__init__(addr)

class WarpEvent(utils.RawStruct):
    fmt = "2H4B"
    def __init__(self, addr):
        (self.x,
         self.y,
         self.level,
         self.dest_warp,
         self.dest_map,
         self.dest_bank) = super().__init__(addr)

class PersonEvent(utils.RawStruct):
    fmt = "2B3H6BHI2H"
    def __init__(self, addr):
        (self.evt_nb,
         self.picture_nb,
         self.unknown,
         self.x,
         self.y,
         self.level,
         self.mvt_type,
         self.mvt,
         self.unknown2,
         self.trainer,
         self.unknown3,
         self.view,
         self.script_ptr,
         self.idx,
         self.unknown4) = super().__init__(addr)

class ScriptEvent(utils.RawStruct):
    fmt = "2H2B3HI"
    def __init__(self, addr):
        (self.x,
         self.y,
         self.level,
         self.unknown,
         self.var_nb,
         self.var_val,
         self.unknown2,
         self.script_ptr) = super().__init__(addr)

class Connection(utils.RawStruct):
    fmt = "Ii2B2x"
    def __init__(self, addr):
        (self.type,
         self.offset,
         self.bank_id,
         self.map_id) = super().__init__(addr)

class WildEntry(utils.RawStruct):
    fmt = "2BH"
    def __init__(self, addr):
        (self.min_lvl,
         self.max_lvl,
         self.species) = super().__init__(addr)
