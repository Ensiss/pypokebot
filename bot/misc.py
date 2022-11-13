def wait(nframes):
    """ Suspends execution during <nframes> frames """
    for i in range(nframes):
        yield

def waitUntil(condition):
    """
    Suspends execution until a condition is met
    The condition parameter is a function returning the value
    """
    yield
    while condition():
        yield

def waitWhile(condition):
    """
    Suspends execution while a condition is met
    The condition parameter is a function returning the value
    """
    while condition():
        yield
