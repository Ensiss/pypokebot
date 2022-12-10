import core.io; io = core.io.IO

def wait(nframes):
    """ Suspends execution during <nframes> frames """
    for i in range(nframes):
        yield

def waitUntil(condition):
    """
    Suspends execution until a condition is met
    The condition parameter is a function returning the value
    """
    while True:
        yield
        if condition():
            break

def waitWhile(condition):
    """
    Suspends execution while a condition is met
    The condition parameter is a function returning the value
    """
    while condition():
        yield

def moveCursor(w, dest, func):
    """
    Moves the cursor to a specific position in a box
    w     Width of the box
    dest  Index of destination position
    func  Function returning the current cursor position
    """
    dx = dest % w
    dy = dest // w

    while True:
        cursor = func()
        cx = cursor % w
        cy = cursor // w
        btn = None

        if cx > dx:
            btn = io.Key.LEFT
        elif cy > dy:
            btn = io.Key.UP
        elif cx < dx:
            btn = io.Key.RIGHT
        elif cy < dy:
            btn = io.Key.DOWN
        else:
            return 0

        yield io.pressOnly(btn)
        yield io.release(btn)
    return 0

def fullPress(btn):
    """
    Fully presses a button then releases it
    """
    yield io.press(btn)
    yield io.release(btn)
