import utils
import enum
import numpy as np
import memory; mem = memory.Memory
import database; db = database.Database
from pathfinder import Pathfinder

class WildType(enum.IntEnum):
    GRASS = 0
    WATER = enum.auto()
    ROCK = enum.auto()
    FISHING = enum.auto()

class MapType(enum.IntEnum):
    NONE = 0
    TOWN = enum.auto()
    CITY = enum.auto()
    ROUTE = enum.auto()
    UNDERGROUND = enum.auto()
    UNDERWATER = enum.auto()
    OCEAN_ROUTE = enum.auto()
    UNKNOWN = enum.auto()
    INDOOR = enum.auto()
    SECRET_BASE = enum.auto()

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

class Status(enum.IntEnum):
    OBSTACLE = 0x01
    WATER = 0x04
    WALKABLE = 0x0C

class Map():
    def __init__(self, addr, bank_id, map_id):
        self.map_hdr = MapHeader(addr)
        self.bank_id = bank_id
        self.map_id = map_id
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

        # Map scripts
        self.map_scripts = []
        i = 0
        while mem.readU8(self.map_hdr.script_ptr + 5 * i) > 0:
            self.map_scripts.append(MapScript(self.map_hdr.script_ptr + 5 * i, i))
            i += 1

        # Map data handling
        rom = mem.rom.buf
        data_ptr = data_hdr.data_ptr & 0xFFFFFF
        sz = self.width * self.height
        data = np.frombuffer(rom[data_ptr:data_ptr+(2 * sz)], dtype=np.uint16)
        data = data.reshape(self.height, self.width)
        self.map_status = (data >> 10).astype(np.uint8)
        self.map_collision = self.map_status & 3
        self.map_level = self.map_status >> 2
        self.map_tile = (data & 1023)
        self.map_attrs = np.zeros(data.shape, dtype=np.uint32)
        self.map_blocks = np.zeros(data.shape, dtype=np.uint16)
        tile_dict = {} # Cache tile attribute when possible
        # Fill background and behavior from tilesets
        for y, line in enumerate(self.map_tile):
            for x, t in enumerate(line):
                if t not in tile_dict:
                    if t < 640:
                        tileset = data_hdr.global_tileset
                        tileset_idx = t
                    else:
                        tileset = data_hdr.local_tileset
                        tileset_idx = t - 640

                    block = mem.readU16(tileset.blocks_ptr + tileset_idx * 2)
                    attr = mem.readU32(tileset.behavior_ptr + tileset_idx * 4)
                    tile_dict[t] = (block, attr)
                block, attr = tile_dict[t]
                self.map_attrs[y, x] = attr
                self.map_blocks[y, x] = block
        self.map_behavior  = (self.map_attrs & 0x000001ff) >> 0
        self.map_terrain   = (self.map_attrs & 0x00003e00) >> 9
        self.map_attr2     = (self.map_attrs & 0x0003c000) >> 14
        self.map_attr3     = (self.map_attrs & 0x00fc0000) >> 18
        self.map_encounter = (self.map_attrs & 0x07000000) >> 24
        self.map_attr5     = (self.map_attrs & 0x18000000) >> 27
        self.map_layer     = (self.map_attrs & 0x60000000) >> 29
        self.map_attr7     = (self.map_attrs & 0x80000000) >> 31
        self.pathfinder = None

        # Physically reachable warps
        self.phys_warps = []
        for warp in self.warps:
            if self.map_behavior[warp.y, warp.x] != 0:
                self.phys_warps.append(warp)

        # Wild battles
        self.wild_battles = []
        for i in range(4):
            self.wild_battles.append(WildBattle())

    def isOutside(self):
        return self.map_hdr.type in [MapType.TOWN, MapType.CITY, MapType.ROUTE,
                                     MapType.UNDERWATER, MapType.OCEAN_ROUTE]
    def isLink(self):
        """
        Does the map link to a different region (with a name change)?
        """
        for evt in self.connects + self.warps:
            if evt.dest_bank >= len(db.banks) or evt.dest_map >= len(db.banks[evt.dest_bank]):
                continue
            if self.name != db.banks[evt.dest_bank][evt.dest_map].name:
                return True
        return False
    def getRegionMaps(self, region=set()):
        region.add(self)
        for evt in self.connects + self.warps:
            if evt.dest_bank >= len(db.banks) or evt.dest_map >= len(db.banks[evt.dest_bank]):
                continue
            dmap = db.banks[evt.dest_bank][evt.dest_map]
            if dmap.name != self.name or dmap in region:
                continue
            dmap.getRegionMaps(region)
        return region

    def getPathfinder(self):
        if self.pathfinder is None:
            self.pathfinder = Pathfinder(self)
        return self.pathfinder

    def plotAttributes(self):
        import matplotlib.pyplot as plt
        names = ["behavior", "terrain", "attr2", "attr3",
                 "encounter", "attr5", "layer", "attr7"]
        for i, name in enumerate(names):
            plt.subplot(2, 4, i+1)
            plt.imshow(self.__getattribute__("map_"+name))
            plt.title(name.capitalize())
        plt.show()

    def plot(self):
        import matplotlib.pyplot as plt
        plt.subplot(2, 2, 1)
        plt.imshow(self.map_attrs)
        plt.title("Attributes")
        plt.subplot(2, 2, 2)
        plt.imshow(self.map_status)
        plt.title("Status")
        plt.subplot(2, 2, 3)
        plt.imshow(self.map_blocks)
        plt.title("Block")
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
    fmt = "2B2x5I"
    def __init__(self, addr):
        (self.compressed,
         self.secondary,
         self.img_ptr,
         self.palette_ptr,
         self.blocks_ptr,
         self.anim_ptr,
         self.behavior_ptr) = super().__init__(addr)

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

class MapScript(utils.RawStruct):
    fmt = "BI"
    def __init__(self, addr, data_idx=0):
        self.data_idx = data_idx
        (self.type,
         self.script_ptr) = super().__init__(addr)
        if (self.type == MapScriptType.VALIDATE_LOAD_1 or
            self.type == MapScriptType.VALIDATE_LOAD_2):
            (self.var,
             self.value,
             self.script_ptr) = mem.unpack(self.script_ptr, "HHI")
        else:
            self.var = 0
            self.value = 0

class SignEvent(utils.RawStruct):
    fmt = "2H2B2xI"
    def __init__(self, addr, data_idx=0):
        self.data_idx = data_idx
        (self.x,
         self.y,
         self.level,
         self.type,
         union) = super().__init__(addr)
        # Hidden objects
        self.script_ptr = union
        (self.item_id,
         self.hidden_item_id,
         self.quantity,
         self.is_underfoot) = mem.unpackBitfield(addr+8, [16, 8, 7, 1])

    def get(info):
        if type(info) is SignEvent:
            return info
        elif type(info) is int:
            return db.getCurrentMap().signs[info]
        print("sign error: invalid argument:", info)
        return None

class WarpEvent(utils.RawStruct):
    fmt = "2H4B"
    def __init__(self, addr, data_idx=0):
        self.data_idx = data_idx
        (self.x,
         self.y,
         self.level,
         self.dest_warp,
         self.dest_map,
         self.dest_bank) = super().__init__(addr)

    def get(info):
        if type(info) is WarpEvent:
            return info
        elif type(info) is int:
            return db.getCurrentMap().phys_warps[info]
        print("warp error: invalid argument:", info)
        return None

class PersonEvent(utils.RawStruct):
    fmt = "2B3H6BHI2H"
    def __init__(self, addr, data_idx=0):
        self.data_idx = data_idx
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

    def get(info):
        if type(info) is PersonEvent:
            return info
        elif type(info) is int:
            return db.getCurrentMap().persons[info-1]
        print("person error: invalid argument:", info)
        return None

    def isVisible(self):
        if self.idx == 0:
            return True
        return not db.getScriptFlag(self.idx)

class ScriptEvent(utils.RawStruct):
    fmt = "2H2B3HI"
    def __init__(self, addr, data_idx=0):
        self.data_idx = data_idx
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
    def __init__(self, addr, data_idx=0):
        self.data_idx = data_idx
        (self.type,
         self.offset,
         self.dest_bank,
         self.dest_map) = super().__init__(addr)

    def get(info):
        def _findConnection(m, ctype):
            for connection in m.connects:
                if connection.type == ctype:
                    return connection
            return None
        if type(info) is ConnectType:
            return _findConnection(db.getCurrentMap(), info)
        elif type(info) is Connection:
            return info
        elif type(info) is int:
            return db.getCurrentMap().connects[info]
        print("connection error: invalid argument:", info)
        return None

    def getMatchingEntry(self, x, y):
        """
        Given an exit's x/y coordinates,
        return the matching entry point in the following map
        """
        dmap = db.banks[self.dest_bank][self.dest_map]
        if self.type == ConnectType.NONE or self.type > ConnectType.RIGHT:
            return x, y
        if self.type == ConnectType.DOWN:
            x -= self.offset
            y = 0
        elif self.type == ConnectType.UP:
            x -= self.offset
            y = dmap.height - 1
        elif self.type == ConnectType.LEFT:
            x = dmap.width - 1
            y -= self.offset
        elif self.type == ConnectType.RIGHT:
            x = 0
            y -= self.offset
        return x, y

    def findExits(self, m):
        exits = []
        if self.type == ConnectType.NONE or self.type > ConnectType.RIGHT:
            return
        dmap = db.banks[self.dest_bank][self.dest_map]
        x = (self.type == ConnectType.RIGHT) * (m.width - 1)
        y = (self.type == ConnectType.DOWN) * (m.height - 1)
        vtcl = (self.type in [ConnectType.UP, ConnectType.DOWN])
        xstep = int(vtcl)
        ystep = 1 - xstep

        while x < m.width and y < m.height:
            # Compute corresponding position in destination map
            if vtcl:
                dx = x - self.offset
                dy = (self.type == ConnectType.UP) * (dmap.height - 1)
            else:
                dx = (self.type == ConnectType.LEFT) * (dmap.width - 1)
                dy = y - self.offset

            if (0 <= dx < dmap.width and 0 <= dy < dmap.height and # In bounds
                m.map_status[y, x] == Status.WALKABLE and # Curr map walkable
                dmap.map_status[dy, dx] == Status.WALKABLE): # Destination walkable
                exits.append([x, y])

            x += xstep
            y += ystep
        self.exits = np.array(exits)

class WildBattle():
    def __init__(self):
        self.ratio = 0
        self.entries = []

class WildEntry(utils.RawStruct):
    fmt = "2BH"
    def __init__(self, addr, data_idx=0):
        self.data_idx = data_idx
        (self.min_lvl,
         self.max_lvl,
         self.species) = super().__init__(addr)
