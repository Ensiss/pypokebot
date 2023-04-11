import numpy as np
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

def turnTowards(tx, ty):
    px, py = db.player.x, db.player.y
    if px < tx:
        key = io.Key.RIGHT
    elif px > tx:
        key = io.Key.LEFT
    elif py < ty:
        key = io.Key.DOWN
    elif py > ty:
        key = io.Key.UP
    else:
        return 0
    return (yield from turn(key))

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

def to(target_func, dist_func, max_dist = 0):
    """
    Moves to reach a defined target.
    target_func returns the current target, and is monitored for changes
    dist_func computes the distance to the current target
    max_dist is the distance required to successfully reach the target
    """
    def _getOWParams():
        return [[ow.dest_x, ow.dest_y] for ow in db.ows]

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

    p = db.player
    m = db.getCurrentMap()
    finder = m.getPathfinder()
    ows = _getOWParams()

    while True:
        tgt = target_func()
        path = finder.search(p.x, p.y, lambda n: dist_func(n, tgt), max_dist)
        if path is None:
            print("to error: no path found: (%d,%d) to (%d,%d)" % (p.x, p.y, *tgt))
            return -1

        while len(path):
            nx, ny = path[0]
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

            if (target_func() != tgt).any():
                print("Target moved, recomputing path")
                break

            path.pop(0)

        if len(path) == 0:
            return 0
    return 0

def toAny(locs, max_dist=0):
    """
    Run pathfinding to a collection of nodes stored as a 2D numpy array
    """
    tgt_func = lambda: locs
    dist_func = lambda n, tgt: np.linalg.norm(tgt - [n.x, n.y], ord=1, axis=1).min()
    return (yield from to(tgt_func, dist_func, max_dist))

def toPos(x, y, max_dist=0):
    return (yield from toAny(np.array([[x, y]]), max_dist))

def toSign(info, max_dist=1):
    """
    toSign(info)    Move to a sign
    info: either SignEvent or sign index
    """
    if (sign := world.SignEvent.get(info)) is None:
        return -1
    yield from toPos(sign.x, sign.y, max_dist)
    return (yield from turnTowards(sign.x, sign.y))

def toPers(info, max_dist=1):
    """
    toPers(info)    Move to a NPC
    info: either PersonEvent or person local index
    """
    def _getTargetPos(pers):
        for i in range(1, len(db.ows)):
            ow = db.ows[i]
            if ow.map_id == 0 and ow.bank_id == 0:
                break
            if (ow.map_id == db.player.map_id and ow.bank_id == db.player.bank_id and
                ow.evt_nb == pers.evt_nb):
                return np.array([ow.dest_x, ow.dest_y])
        return np.array([pers.x, pers.y])

    if (pers := world.PersonEvent.get(info)) is None:
        return -1
    if not pers.isVisible():
        return -1
    tgt_func = lambda: _getTargetPos(pers)
    dist_func = lambda n, tgt: np.linalg.norm(tgt - [n.x, n.y], ord=1)
    if (yield from to(tgt_func, dist_func, max_dist)) == -1:
        return -1
    tx, ty = _getTargetPos(pers)
    return (yield from turnTowards(tx, ty))

def toConnection(info):
    """
    toConnection(info)    Leave the current map in the specified direction
    info: either Connection, connection index, or ConnectionType
    """
    if (connection := world.Connection.get(info)) is None:
        return -1
    ctype = connection.type
    if ctype == world.ConnectType.NONE or ctype > world.ConnectType.RIGHT:
        print("connection error: only up, down, left, right are supported")
        return -1
    if connection is None or len(connection.exits) == 0:
        print("connection error: no connection of type %d in map (%d,%d)" %
              (ctype, db.player.bank_id, db.player.map_id))
        return -1
    yield from toAny(connection.exits)
    yield from step(io.directions[ctype - 1])
    return 0

def toWarp(info):
    """
    toWarp(info)    Leave the map by using the specified warp
    info: either WarpEvent, or phys_warp index
    """
    p = db.player
    m = db.getCurrentMap()
    if (warp := world.WarpEvent.get(info)) is None:
        return -1
    max_dist = (m.map_status[warp.y, warp.x] == world.Status.OBSTACLE)
    if (yield from toPos(warp.x, warp.y, max_dist)) == -1:
        return -1

    if p.bank_id == warp.dest_bank and p.map_id == warp.dest_map:
        return 0
    key = None
    if p.x == warp.x and p.y == warp.y:
        key = db.warp_behaviors[m.map_behavior[warp.y, warp.x]]
    else:
        if p.y < warp.y:
            key = io.Key.DOWN
        elif p.y > warp.y:
            key = io.Key.UP
        elif p.x > warp.x:
            key = io.Key.LEFT
        elif p.x < warp.x:
            key = io.Key.RIGHT

    if key is None:
        return -1

    # TODO: use step instead, and improve step to allow stepping through doors
    ow = db.ows[0]
    owx, owy = ow.dest_x, ow.dest_y
    while ow.dest_x == owx and ow.dest_y == owy:
        yield io.press(key)
    io.releaseAll()

    # TODO: Detect screen fade out more accurately
    yield from misc.wait(150)
