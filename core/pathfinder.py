import numpy as np
import database; db = database.Database
import core.io; io = core.io.IO
from script import Script, MvtScript

class Pathfinder:
    mvt_static = [0, 1, 7, 8, 9, 10] + list(range(13, 25)) + list(range(64, 80))

    class Node:
        def __init__(self, m, coords):
            self.map = m
            self.x, self.y = coords
            self.status = m.map_status[self.y, self.x]
            self.tile = m.map_tile[self.y, self.x]
            self.behavior = m.map_behavior[self.y, self.x]
            self.left = self.right = None
            self.up = self.down = None
            self.scripts = []
            self.setMovementCost()
            self.clear()

        def isWalkable(self):
            return (self.status in [0x0C, 0x00, 0x10] and   # Walkable tile
                    self.behavior not in [0x61, 0x6B])      # Not escalator

        def hasOverWorld(self):
            if self.ow is not None:
                return self.ow
            checked = [False] * len(self.map.persons)
            bid = self.map.bank_id
            mid = self.map.map_id
            # If working on the active map, check dynamic overworlds
            if bid == db.player.bank_id and mid == db.player.map_id:
                for ow in db.ows[1:]: # Skip player overworld
                    if ow.bank_id == 0 and ow.map_id == 0:
                        break
                    if ow.bank_id == bid and ow.map_id == mid:
                        if ow.dest_x == self.x and ow.dest_y == self.y:
                            self.ow = True
                            return self.ow
                        checked[ow.evt_nb-1] = True
            for pers in self.map.persons:
                if checked[pers.evt_nb-1]: # Already checked as overworld
                    continue
                if pers.x == self.x and pers.y == self.y and pers.isVisible():
                    self.ow = True
                    return self.ow
            self.ow = False
            return self.ow

        def hasScriptMovement(self, ctx):
            if self.script_mvmt is not None:
                return self.script_mvmt
            for s in self.scripts:
                if ctx.getVar(s.var_nb, False) != s.var_val:
                    continue
                sscript = Script.getScript(s.data_idx, self.map.bank_id, self.map.map_id)
                # is duplicating the context necessary here?
                out_ctxs = sscript.execute(Script.Context(ctx))
                for out_ctx in out_ctxs:
                    for mvt_addr in out_ctx.outputs.filter(Script.Movement):
                        mvt_script = MvtScript(int(mvt_addr))
                        if mvt_script.dx != 0 or mvt_script.dy != 0:
                            self.script_mvmt = True
                            return self.script_mvmt
            self.script_mvmt = False
            return self.script_mvmt

        def setMovementCost(self):
            """ Sets movement cost """
            terrain = self.map.map_terrain[self.y, self.x]
            encounter = self.map.map_encounter[self.y, self.x]
            self.movement_cost = 1.0
            if terrain == 1 and encounter == 1: # Grass
                self.movement_cost = 10.0

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
            """ Disconnect a node from its neighbors, in both directions """
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

        def getNeighbors(self):
            neighbs = [self.up, self.down, self.left, self.right]
            return [x for x in neighbs if x]

        def clear(self):
            """
            Clear weights and recorded path
            Keeps links and other static data
            """
            self.weight = self.heuristic = 0
            self.dist = 9999
            self.prev = None
            self.ow = None
            self.script_mvmt = None

        def setHeuristic(self, dist):
            self.dist = dist
            self.heuristic = self.weight + self.dist

    def __init__(self, map_data):
        self.map = map_data
        self.dirty = False
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
        # Register scripts
        for s in self.map.scripts:
            if (node := self.getNode(s.x, s.y)) is None:
                continue
            node.scripts.append(s)

    def search(self, xs, ys, dist_func, dist=0, ctx=None):
        """
        Returns the path from [xs,ys] to a given target
        dist_func returns the distance to the target from a node
        """
        def unlock():
            db.player.unlock()
            database.OWObject.unlock()

        if ctx is None:
            ctx = Script.Context()
        if self.dirty:
            self.clear()
        # Lock dynamic objects from updates
        db.player.lock()
        database.OWObject.lock()
        for ow in db.ows:
            ow._checkUpdate()
        self.dirty = True
        # If start is inside a building, try to exit
        if (self.map.map_collision[ys,xs] == 1 and
            self.map.map_behavior[ys,xs] in db.warp_behaviors):
            key = db.warp_behaviors[self.map.map_behavior[ys,xs]].invert()
            dx, dy = [(1, 0), (-1, 0), (0, -1), (0, 1)][key - io.Key.RIGHT]
            xs += dx
            ys += dy
        start = self.getNode(xs, ys)
        if start is None:
            print("pathfinding error: invalid start (%d,%d)" % (xs, ys))
            unlock()
            return None
        start.setHeuristic(dist_func(start))
        openset = [start]
        closedset = []

        while len(openset) > 0:
            curr = openset.pop(self._getNextIndex(openset))
            # If the target is reached
            if curr.dist == dist:
                unlock()
                return self._rebuildPath(curr)
            # If the target is an NPC directly behind a counter
            elif dist == 1 and curr.dist == 2:
                for dir_i in range(4):
                    dx = curr.x + np.sign(dir_i - 1) * (1 - dir_i % 2)
                    dy = curr.y + np.sign(dir_i - 2) * (dir_i % 2)
                    if (dx < 0 or dx >= self.map.width or
                        dy < 0 or dy >= self.map.height):
                        continue
                    if self.map.map_behavior[dy,dx] == 0x80:
                        unlock()
                        return self._rebuildPath(curr)
            closedset.append(curr)
            for next_node in curr.getNeighbors():
                if next_node.hasOverWorld() or next_node.hasScriptMovement(ctx):
                    continue
                cost = curr.weight + next_node.movement_cost
                visited = (next_node in closedset)
                if visited and cost >= next_node.weight:
                    continue
                if not visited or cost < next_node.weight:
                    next_node.prev = curr
                    next_node.weight = cost
                    next_node.setHeuristic(dist_func(next_node))
                    if next_node not in openset:
                        openset.append(next_node)
        unlock()
        return None

    def searchAny(self, xs, ys, locs, dist=0):
        dist_func = lambda n: np.linalg.norm(locs - [n.x, n.y], ord=1, axis=1).min()
        return self.search(xs, ys, dist_func, dist)
    def searchPos(self, xs, ys, xe, ye, dist=0):
        return self.searchAny(xs, ys, np.array([[xe, ye]]), dist)
    def searchPers(self, xs, ys, pers, dist=1):
        return self.searchPos(xs, ys, pers.x, pers.y, dist)
    def searchWarp(self, xs, ys, warp, dist=0):
        return self.searchPos(xs, ys, warp.x, warp.y, dist)
    def searchConnection(self, xs, ys, conn, dist=0):
        if conn is None or len(conn.exits) == 0:
            return None
        return self.searchAny(xs, ys, conn.exits, dist)

    def _getNextIndex(self, l):
        minh = np.inf
        mini = 0
        for i, elm in enumerate(l):
            if elm.heuristic < minh:
                mini = i
                minh = elm.heuristic
        return mini

    def _rebuildPath(self, node, l=None):
        if l is None:
            l = []
        if node.prev:
            self._rebuildPath(node.prev, l)
        l.append([node.x, node.y])
        return l

    def clear(self):
        """ Clear all node weights and paths """
        for row in self.nodes:
            for node in row:
                if node:
                    node.clear()

    def getNode(self, x, y):
        if not (0 <= x < self.map.width and 0 <= y < self.map.height):
            return None
        return self.nodes[y][x]

    def plotPath(self, path):
        import matplotlib.pyplot as plt
        out = np.zeros(self.map.map_tile.shape)
        for y in range(self.map.height):
            for x in range(self.map.width):
                if self.nodes[y][x]:
                    out[y][x] = self.nodes[y][x].heuristic
        plt.imshow(out)
        if path is not None:
            plt.plot(*np.array(path).T, color="red")
        plt.show()

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
