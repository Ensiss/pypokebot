pypokebot
==========

**pypokebot** is the Python version of [pokebot](https://github.com/Ensiss/pokebot), a bot designed to eventually fully beat pokemon FireRed without explicitely being told how. This version uses the Python bindings provided by [mGBA](https://github.com/mgba-emu/mgba) to emulate a Game Boy Advance and control the game state.

# Dependencies

## mgba

Please first install [mGBA](https://github.com/mgba-emu/mgba) with the Python bindings:

```
$ git clone https://github.com/mgba-emu/mgba.git
$ mkdir mgba/build
$ cd mgba/build
$ cmake .. -DBUILD_PYTHON=ON
$ make
$ sudo make install
```

Install steps will be different if you are not using Linux, but this project should be compatible with any OS.

## pypokebot

pypokebot uses `pygame` for display and user input.

## Pokemon Fire Red GBA ROM (U) (V1.0)

You can find it easily on the internet. Remember to get the V1.0 and **not** V1.1 as the memory addresses used by pypokebot are specific to V1.0.

The md5sum of the right file is `e26ee0d44e809351c8ce2d73c7400cdd`.

# Info

To learn how the project works, some ressources are available in the [pokebot wiki](https://github.com/Ensiss/pokebot/wiki).
