import numpy as np
import database; db = database.Database
import core.io; io = core.io.IO

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
            self.clear()

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

        def getMovementCost(self):
            """ Returns movement cost """
            if self.behavior in [0x0202]: # Grass
                return 10.0
            return 1.0

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
            self.prev = None

        def setHeuristicTo(self, xe, ye):
            dist = np.sqrt((xe - self.x) ** 2 + (ye - self.y) ** 2)
            self.heuristic = self.weight + dist

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

    def search(self, xs, ys, xe, ye, dist=0):
        if self.dirty:
            self.clear()
        self.dirty = True
        start = self.getNode(xs, ys)
        start.setHeuristicTo(xe, ye)
        openset = [start]
        closedset = []

        while len(openset) > 0:
            curr = openset.pop(self._getNextIndex(openset))
            if abs(curr.x - xe) + abs(curr.y - ye) == dist:
                return self._rebuildPath(curr)
            closedset.append(curr)
            for next_node in curr.getNeighbors():
                if next_node.hasOverWorld():
                    continue
                cost = curr.weight + next_node.getMovementCost()
                visited = (next_node in closedset)
                if visited and cost >= next_node.weight:
                    continue
                if not visited or cost < next_node.weight:
                    next_node.prev = curr
                    next_node.weight = cost
                    next_node.setHeuristicTo(xe, ye)
                    if next_node not in openset:
                        openset.append(next_node)
        return None

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
