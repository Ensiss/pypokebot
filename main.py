import numpy as np
import cv2
import mgba.core
import mgba.image
import mgba.log

import argparse
import struct
import sys
import os
import re

parser = argparse.ArgumentParser(description="Pokebot")
parser.add_argument("-r", "--rom", type=str, default=os.path.expanduser("~/Games/Pokemon - FireRed Version (USA).gba"),
                    help="Path to the Pokemon Firered v1.0 ROM")

args = parser.parse_args()

mgba.log.silence()
core = mgba.core.load_path(args.rom)
core.autoload_save()

screen = mgba.image.Image(*core.desired_video_dimensions())
core.set_video_buffer(screen)
core.reset()

rom = mgba.ffi.buffer(core._native.memory.rom, core.memory.rom.size)
wram = mgba.ffi.buffer(core._native.memory.wram, core.memory.wram.size)

for i in range(20000):
    core.clear_keys(core.KEY_A)
    if i % 2 == 0:
        core.add_keys(core.KEY_A)
    core.run_frame()
    RGB = np.array(screen.to_pil())[:,:,[2,1,0]]
    cv2.imshow("out", RGB)
    k = cv2.waitKey(1) & 0xFF
    if k == 27:
        break

cv2.destroyAllWindows()

