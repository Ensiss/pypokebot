import numpy as np

charset = np.zeros(256, dtype=str)
charset[:] = "?"
charset[0xA1:0xAB] = list(map(chr, range(ord('0'), ord('9')+1)))
charset[0xAB:0xBB] = list("!?.-*.\"\"''MF ,x/")
charset[0xBB:0xD5] = list(map(chr, range(ord('A'), ord('Z')+1)))
charset[0xD5:0xEF] = list(map(chr, range(ord('a'), ord('z')+1)))
charset[0x00] = " "
charset[0xF0] = ":"
charset[0xFE] = "\n"
charset[0xFF] = "\x00"

def pokeToAscii(poke):
    return "".join([charset[x] for x in poke])
