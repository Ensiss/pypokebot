import memory; mem = memory.Memory
import database; db = database.Database
import core.io; io = core.io.IO
import misc
import world

def turn(btn):
    if btn not in io.directions:
        print("turn error: button %d is not a direction" % btn)
        return -1

    ow = db.ows[0] # Player's sprite
    yield from misc.waitWhile(lambda: db.getPlayerState() != db.PlayerState.STATIC)
    if io.directions[ow.dir] != btn:
        while db.getPlayerState() != db.PlayerState.TURN:
            yield io.toggle(btn)

    io.releaseAll()
    yield from misc.waitWhile(lambda: db.getPlayerState() == db.PlayerState.TURN)
    return 0

def step(btn):
    def _isValid(m, btn, xend, yend):
        if (xend < 0 or xend >= m.width or
            yend < 0 or yend >= m.height):
            return True
        # Check hills
        if btn == io.Key.RIGHT and m.map_behavior[yend, xend] == 0x38:
            return True
        if btn == io.Key.LEFT and m.map_behavior[yend, xend] == 0x39:
            return True
        if btn == io.Key.DOWN and m.map_behavior[yend, xend] == 0x3B:
            return True
        if m.map_status[yend, xend] == world.Status.WALKABLE:
            return True
        return False

    if btn not in io.directions:
        print("step error: button %d is not a direction" % btn)
        return -1

    m = db.getCurrentMap()
    ow = db.ows[0]
    xstart = db.player.x
    ystart = db.player.y
    xend = xstart + (btn == io.Key.RIGHT) - (btn == io.Key.LEFT)
    yend = ystart + (btn == io.Key.DOWN) - (btn == io.Key.UP)
    if not _isValid(m, btn, xend, yend):
        print("step error: destination %d unreachable from (%d,%d)" %
              (btn, xstart, ystart))
        return -1

    io.releaseAll()
    while ow.dest_x == xstart and ow.dest_y == ystart:
        yield io.toggle(btn)
    io.releaseAll()

    moving = lambda: db.getPlayerState() == db.PlayerState.WALK
    yield from misc.waitWhile(moving)
    return 0

def to(x, y = None, max_dist = 0):
    """
    to(x, y[, maxDist])      Moves to a node in the current map
    to(id)                   Moves to a person defined by its id
    """
    def _getOWParams():
        return [[ow.dest_x, ow.dest_y] for ow in db.ows]

    def _getTargetPos(x, y=None):
        if y is not None:
            return x, y
        m = db.getCurrentMap()
        pers = m.persons[x]
        for i in range(1, len(db.ows)):
            ow = db.ows[i]
            if ow.map_id == 0 and ow.bank_id == 0:
                break
            if (ow.map_id == db.player.map_id and ow.bank_id == db.player.bank_id and
                ow.evt_nb == pers.evt_nb):
                return ow.dest_x, ow.dest_y
        return pers.x, pers.y

    def _checkNPCs(ows, path):
        """ Check if any moving NPC joined/left the current player path """
        ret = False
        for i in range(1, len(db.ows)):
            old = ows[i]
            new = db.ows[i]
            if new.bank_id != db.player.bank_id or new.map_id != db.player.map_id:
                continue
            if old[0] == new.dest_x and old[1] == new.dest_y:
                continue
            old[0] = new.dest_x
            old[1] = new.dest_y
            for nx, ny in path:
                if ((new.dest_x == nx and new.dest_y == ny) or
                    (new.x == nx and new.y == ny)):
                    ret = True
                    break
        return ret

    if y is None:
        max_dist = 1
    p = db.player
    m = db.getCurrentMap()
    finder = m.makePathfinder()
    ows = _getOWParams()

    while True:
        tgt = _getTargetPos(x, y)
        path = finder.search(p.x, p.y, *tgt, max_dist)
        if path is None:
            print("to error: no path found: (%d,%d) to (%d,%d)" % (p.x, p.y, *tgt))
            return -1

        while len(path):
            nx, ny = path[0]
            # nx, ny = path.pop(0)
            dx = nx - p.x
            dy = ny - p.y
            if dx == 0 and dy == 0:
                path.pop(0)
                continue
            if dx == 0:
                btn = io.Key.UP if dy < 0 else io.Key.DOWN
            else:
                btn = io.Key.LEFT if dx < 0 else io.Key.RIGHT
            if (yield from step(btn)) == -1:
                print("step error, recomputing path")
                break

            if _checkNPCs(ows, path):
                print("NPC moved, recomputing path")
                break

            if _getTargetPos(x, y) != tgt:
                print("Target moved, recomputing path")
                break

            path.pop(0)

        if abs(p.x - tgt[0]) + abs(p.y - tgt[1]) <= max_dist:
            return 0
    return 0
