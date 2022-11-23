import utils
import enum
import numpy as np
import memory; mem = memory.Memory
import database; db = database.Database

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

class Status(enum.IntEnum):
    OBSTACLE = 0x01
    WATER = 0x04
    WALKABLE = 0x0C

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

        # Map scripts
        self.map_scripts = []
        i = 0
        while mem.readU8(self.map_hdr.script_ptr + 5 * i) > 0:
            self.map_scripts.append(MapScript(self.map_hdr.script_ptr + 5 * i))
            i += 1

        # Map data handling
        rom = mem.rom.buf
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

    def makePathfinder(self):
        return Pathfinder(self)

    def plot(self):
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

class Pathfinder:
    mvt_static = [0, 1, 7, 8, 9, 10] + list(range(13, 25)) + list(range(64, 80))

    class Node:
        def __init__(self, m, coords):
            self.map = m
            self.x, self.y = coords
            self.status = m.map_status[self.y, self.x]
            self.tile = m.map_tile[self.y, self.x]
            self.behavior = m.map_behavior[self.y, self.x]
            self.bg = m.map_bg[self.y, self.x]
            self.left = self.right = None
            self.up = self.down = None
            self.g = self.f = 0

        def isWalkable(self):
            return (self.status in [0x0C, 0x00, 0x10] and   # Walkable tile
                    self.behavior not in [0x61, 0x6B])      # Not escalator

        def hasOverWorld(self):
            for pers in self.map.persons:
                if (pers.x == self.x and pers.y == self.y and pers.isVisible() and
                    pers.mvt_type in Pathfinder.mvt_static):
                    return True
            for ow in db.ows[1:]: # Skip player overworld
                if ow.map_id == 0 and ow.bank_id == 0:
                    break
                if (ow.bank_id == db.player.bank_id and
                    ow.map_id == db.player.map_id and
                    ow.dest_x == self.x and ow.dest_y == self.y):
                    return True
            return False

        def connect(self, pth):
            right = pth.getNode(self.x+1, self.y)
            if right:
                bhv = right.behavior
                if bhv in [0x38, 0x39]: # Hills
                    right = pth.getNode(self.x+2, self.y)
                    if bhv == 0x38: # Right jump
                        self.right = right
                    elif right: # Left jump
                        right.left = self
                elif right.isWalkable():
                    self.right = right
                    right.left = self

            down = pth.getNode(self.x, self.y+1)
            if down:
                if down.behavior == 0x3B: # Down jump
                    self.down = pth.getNode(self.x, self.y+2)
                elif down.isWalkable():
                    self.down = down
                    down.up = self

        def disconnect(self):
            if self.left:
                self.left.right = None
            if self.right:
                self.right.left = None
            if self.up:
                self.up.down = None
            if self.down:
                self.down.up = None
            self.left = self.right = None
            self.up = self.down = None

    def __init__(self, map_data):
        self.map = map_data
        self.nodes = []
        # Create nodes
        for y in range(self.map.height):
            rows = []
            for x in range(self.map.width):
                n = Pathfinder.Node(self.map, (x, y))
                rows.append(n)
            self.nodes.append(rows)
        # Connect nodes
        for y in range(self.map.height):
            for x in range(self.map.width):
                if not self.nodes[y][x].isWalkable():
                    continue
                self.nodes[y][x].connect(self)
        # Remove unwalkable nodes
        for y in range(self.map.height):
            for x in range(self.map.width):
                if not self.nodes[y][x].isWalkable():
                    self.nodes[y][x] = None

    def getNode(self, x, y):
        if not (0 <= x < self.map.width and 0 <= y < self.map.height):
            return None
        return self.nodes[y][x]

    def plot(self):
        import matplotlib.pyplot as plt
        xy = []
        ows = []
        for row in self.nodes:
            for node in row:
                if node is None:
                    continue
                xy.append([node.x, node.y])
                if node.hasOverWorld():
                    ows.append([node.x, node.y])
                if node.right:
                    plt.plot([node.x+.1, node.right.x-.1], [node.y+.1, node.right.y+.1])
                if node.left:
                    plt.plot([node.x-.1, node.left.x+.1], [node.y-.1, node.left.y-.1])
                if node.up:
                    plt.plot([node.x-.1, node.up.x-.1], [node.y-.1, node.up.y+.1])
                if node.down:
                    plt.plot([node.x+.1, node.down.x+.1], [node.y+.1, node.down.y-.1])
        plt.scatter(*np.array(xy).T, zorder=2.5)
        plt.scatter(*np.array(ows).T, color="red", zorder=2.5)
        plt.gca().invert_yaxis()
        plt.gca().set_aspect(1)
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

class MapScript(utils.RawStruct):
    fmt = "BI"
    def __init__(self, addr):
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

    def isVisible(self):
        if self.idx == 0:
            return True
        return not utils.getFlag(self.idx)

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
