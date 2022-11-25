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
    if btn not in io.directions:
        print("step error: button %d is not a direction" % btn)
        return -1

    xstart = db.player.x
    ystart = db.player.y
    xend = xstart + (btn == io.Key.RIGHT) - (btn == io.Key.LEFT)
    yend = ystart + (btn == io.Key.DOWN) - (btn == io.Key.UP)
    m = db.getCurrentMap()
    ow = db.ows[0]
    if (0 <= xend < m.width and 0 <= yend < m.height and
        m.map_status[yend, xend] != world.Status.WALKABLE):
        print("step error: destination (%d,%d) is unreachable" % (xend, yend))
        return -1

    io.releaseAll()
    while ow.dest_x == xstart and ow.dest_y == ystart:
        yield io.toggle(btn)
    io.releaseAll()

    moving = lambda: ((db.player.x == xstart and db.player.y == ystart) or
                      (ow.x == xstart and ow.y == ystart) or
                      (ow.dest_x == xstart and ow.dest_y == ystart))
    yield from misc.waitWhile(moving)
    return 0

def to(x, y = None, max_dist = 0):
    """
    to(x, y[, maxDist])      Moves to a node in the current map
    to(id)                   Moves to a person defined by its id
    """
    if y is None:
        max_dist = 1
    p = db.player
    m = db.getCurrentMap()
    finder = m.makePathfinder()

    while True:
        tgt = (x, y)
        path = finder.search(p.x, p.y, x, y, max_dist)
        if path is None:
            print("to error: no path found: (%d,%d) to (%d,%d)" % (p.x, p.y, x, y))
            return -1

        for nx, ny in path:
            dx = nx - p.x
            dy = ny - p.y
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                btn = io.Key.UP if dy < 0 else io.Key.DOWN
            else:
                btn = io.Key.LEFT if dx < 0 else io.Key.RIGHT
            if (yield from step(btn)) == -1:
                print("step error, recomputing path")
                break

        if abs(p.x - tgt[0]) + abs(p.y - tgt[1]) <= max_dist:
            return 0
    return 0
