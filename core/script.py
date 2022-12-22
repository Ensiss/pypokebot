import memory; mem = memory.Memory
import database; db = database.Database
import struct

class Command:
    arg_fmts = {
        "byte": "B",
        "word": "H",
        "dword": "I",
        "ptr": "I",
        "var": "H",
        "flag": "H",
        "bank": "B",
        "buffer": "B",
        "hidden": "B",
        "ptr/bank": "I",
        "ptr/bank0": "I",
        "flag/var": "H",
        "word/var": "H",
        "byte/var": "H"
    }

    cmd_op = [
        lambda a, b: a < b,
        lambda a, b: a == b,
        lambda a, b: a > b,
        lambda a, b: a <= b,
        lambda a, b: a >= b,
        lambda a, b: a != b
    ]

    def __init__(self, opcode, str_fmt, args):
        self.opcode = opcode
        self.str_fmt = str_fmt
        self.name = self.str_fmt.split(" ")[0]
        self.args = args
        self.fmt = ""
        for arg in self.args.split(" "):
            if arg == "":
                continue
            self.fmt += Command.arg_fmts[arg]
        self.size = struct.calcsize("<" + self.fmt) + 1 # Add 1 for bytecode

    def __len__(self):
        return self.size

    def format(self, instr):
        return self.str_fmt % instr.args

    def unrolledString(self, addr):
        return mem.readPokeStr(addr).replace("\n", " ")

    def execute(self, vm, ctx, instr):
        return

class CommandCall(Command):
    def execute(self, vm, ctx, instr):
        ctx.stack.append(instr.next_addr)
        ctx.pc = instr.args[0]

class CommandGoto(Command):
    def execute(self, vm, ctx, instr):
        ctx.pc = instr.args[0]

class CommandIf(Command):
    def format(self, instr):
        op = ["<", "==", ">", "<=", ">=", "!=", "?"][min(6, instr.args[0])]
        cmd = "goto" if instr.opcode == 0x06 else "call"
        return  "if %s %s 0x%08x" % (op, cmd, instr.args[1])

class CommandIf1(CommandIf):
    def execute(self, vm, ctx, instr):
        if instr.args[0] > 5:
            print("If1 error: no operator %d" % instr.args[0])
            return
        if Command.cmd_op[instr.args[0]](ctx.cmp1, ctx.cmp2):
            CommandGoto.execute(self, vm, ctx, instr)

class CommandIf2(CommandIf):
    def execute(self, vm, ctx, instr):
        if instr.args[0] > 5:
            print("If2 error: no operator %d" % instr.args[0])
            return
        if Command.cmd_op[instr.args[0]](ctx.cmp1, ctx.cmp2):
            CommandCall.execute(self, vm, ctx, instr)

class CommandLoadPointer(Command):
    def format(self, instr):
        return "loadpointer %d \"%s\"" % (instr.args[0], self.unrolledString(instr.args[1]))
    def execute(self, vm, ctx, instr):
        ctx.setBank(instr.args[0], instr.args[1])

class CommandSetByte2(Command):
    def execute(self, vm, ctx, instr):
        ctx.setBank(instr.args[0], instr.args[1])

class CommandLoadByteFromPtr(Command):
    def execute(self, vm, ctx, instr):
        ctx.setBank(instr.args[0], mem.readU8(instr.args[1]))

class CommandCopyScriptBanks(Command):
    def execute(self, vm, ctx, instr):
        ctx.setBank(instr.args[0], ctx.getBank(instr.args[1]))

class CommandBufferString(Command):
    def format(self, instr):
        return "bufferstring %d \"%s\"" % (instr.args[0], self.unrolledString(instr.args[1]))

class CommandPrepareMsg(Command):
    def format(self, instr):
        if instr.args[0] == 0:
            return self.str_fmt % instr.args
        return "preparemsg \"%s\"" % self.unrolledString(instr.args[0])

class CommandCheckAttack(Command):
    def format(self, instr):
        return "checkattack \"%s\"" % db.moves[instr.args[0]].name

class Instruction:
    def __init__(self, addr):
        self.addr = addr
        self.opcode = mem.readU8(addr)
        self.cmd = cmds[self.opcode]
        self.args = mem.unpack(addr+1, self.cmd.fmt)
        self.next_addr = self.addr + len(self.cmd)

    def __len__(self):
        return len(self.cmd)

    def __str__(self):
        return self.cmd.format(self)

class Script:
    def __init__(self, addr):
        self.addr = addr

    def print(self):
        def alreadyVisited(addr):
            for addr_min, addr_max in ranges:
                if addr_min <= addr < addr_max:
                    return True
            if addr in addrs:
                return True
            return False

        def subPrint(addr):
            instr = Instruction(addr)
            jumps = []
            while True:
                # Exit on unknown opcodes
                if instr.cmd.str_fmt == "":
                    print("Error: Unknown opcode 0x%02X" % instr.opcode)
                    break
                # Print current instruction
                header = (" "*8) + "%02x: " % (instr.addr & 0xFF)
                if instr.addr == addr:
                    header = "0x%08x: " % instr.addr
                print(header + str(instr))
                # Store destination of jumps and conditions
                if 0x04 <= instr.opcode <= 0x07:
                    jumps.append(instr.args[-1])
                # Exit at function end
                if instr.opcode in [0x02, 0x03]: # end/return
                    break
                instr = Instruction(instr.next_addr)
            ranges.append((addr, instr.next_addr))
            for jump in jumps:
                if not alreadyVisited(jump):
                    addrs.append(jump)

        ranges = []
        addrs = [self.addr]
        while len(addrs) > 0:
            addr = addrs.pop(0)
            if addr != self.addr:
                print("")
            subPrint(addr)

class VM:
    FLAG_COUNT = 0x900
    VAR_COUNT = 0x100
    TEMP_COUNT = 0x1F
    BANK_COUNT = 0x04
    BUFF_COUNT = 0x03
    VAR_OFFSET = 0x4000
    TEMP_OFFSET = 0x8000

    def isFlag(x):
        return x < VM.FLAG_COUNT
    def isBank(x):
        return x < VM.BANK_COUNT
    def isVar(x):
        return VM.VAR_OFFSET <= x < VM.VAR_OFFSET + VM.VAR_COUNT
    def isTemp(x):
        return VM.TEMP_OFFSET <= x < VM.TEMP_OFFSET + VM.TEMP_COUNT

    class Context:
        def __init__(self, other=None):
            if other is None:
                ptr = mem.readU32(0x03005008)
                self.flags = np.frombuffer(mem.bufferFromAddr(ptr + 0xEE0)[:VM.FLAG_COUNT >> 3], dtype=np.uint8).copy()
                self.variables = np.frombuffer(mem.bufferFromAddr(ptr + 0x1000)[:VM.VAR_COUNT], dtype=np.uint16).copy()
                self.temps = np.zeros(VM.TEMP_COUNT, dtype=np.uint16)
                self.banks = np.zeros(VM.BANK_COUNT, dtype=np.uint32)
                self.cmp1 = self.cmp2 = 0
                self.pc = 0
                self.stack = []
            else:
                self.flags = other.flags.copy()
                self.variables = other.variables.copy()
                self.temps = other.temps.copy()
                self.banks = other.banks.copy()
                self.cmp1 = other.cmp1
                self.cmp2 = other.cmp2
                self.pc = other.pc
                self.stack = other.stack.copy()

        def copy(self):
            return VM.Context(self)

        def getFlag(self, idx):
            if VM.isFlag(idx):
                return bool(self.flags[idx >> 3] & (1 << (idx % 8)))
            print("Context error: flag %d does not exist" % idx)
            return 0

        def getVar(self, idx):
            if VM.isVar(idx):
                return self.variables[idx - VM.VAR_OFFSET]
            elif VM.isTemp(idx):
                return self.temps[idx - VM.TEMP_OFFSET]
            print("Context error: variable %d does not exist" % idx)
            return 0

        def getBank(self, idx):
            if VM.isBank(idx):
                return self.banks[idx]
            print("Context error: bank %d does not exist" % idx)
            return 0

        def setFlag(self, idx, val):
            if not VM.isFlag(idx):
                print("Context error: flag %d does not exist" % idx)
                return
            if val:
                self.flags[idx >> 3] |= (1 << (idx % 8))
            else:
                self.flags[idx >> 3] &= ~(1 << (idx % 8))

        def setVar(self, idx, val):
            if VM.isVar(idx):
                self.variables[idx - VM.VAR_OFFSET] = val
            elif VM.isTemp(idx):
                self.temps[idx - VM.TEMP_OFFSET] = val
            else:
                print("Context error: variable %d does not exist" % idx)

        def setBank(self, idx, val):
            if VM.isBank(idx):
                self.banks[idx] = val
            else:
                print("Context error: bank %d does not exist" % idx)

cmds = [
    Command(0x00, "nop", ""),
    Command(0x01, "nop1", ""),
    Command(0x02, "end", ""),
    Command(0x03, "return", ""),
    CommandCall(0x04, "call 0x%08x", "ptr"),
    CommandGoto(0x05, "goto 0x%08x", "ptr"),
    CommandIf1(0x06, "if1 %#x 0x%08x", "byte ptr"),
    CommandIf2(0x07, "if2 %#x 0x%08x", "byte ptr"),
    Command(0x08, "gotostd %#x", "byte"),
    Command(0x09, "callstd %#x", "byte"),
    Command(0x0A, "gotostdif %#x %#x", "byte byte"),
    Command(0x0B, "callstdif %#x %#x", "byte byte"),
    Command(0x0C, "jumpram", ""),
    Command(0x0D, "killscript", ""),
    Command(0x0E, "setbyte %#x", "byte"),
    CommandLoadPointer(0x0F, "loadpointer %d %#x", "bank dword"),
    CommandSetByte2(0x10, "setbyte2 %d %#x", "bank byte"),
    Command(0x11, "writebytetooffset %#x 0x%08x", "byte ptr"),
    CommandLoadByteFromPtr(0x12, "loadbytefrompointer %d 0x%08x", "bank ptr"),
    Command(0x13, "setfarbyte %d 0x%08x", "bank ptr"),
    CommandCopyScriptBanks(0x14, "copyscriptbanks %d %d", "bank bank"),
    Command(0x15, "copybyte 0x%08x 0x%08x", "ptr ptr"),
    Command(0x16, "setvar %#x %#x", "var word"),
    Command(0x17, "addvar %#x %#x", "var word"),
    Command(0x18, "subvar %#x %#x", "var word/var"),
    Command(0x19, "copyvar %#x %#x", "var var"),
    Command(0x1A, "copyvarifnotzero %#x %#x", "var word/var"),
    Command(0x1B, "comparebanks %d %d", "bank bank"),
    Command(0x1C, "comparebanktobyte %d %#x", "bank byte"),
    Command(0x1D, "comparebanktofarbyte %d 0x%08x", "bank ptr"),
    Command(0x1E, "comparefarbytetobank 0x%08x %d", "ptr bank"),
    Command(0x1F, "comparefarbytetobyte 0x%08x %#x", "ptr byte"),
    Command(0x20, "comparefarbytes 0x%08x 0x%08x", "ptr ptr"),
    Command(0x21, "compare %#x %#x", "var word"),
    Command(0x22, "comparevars %#x %#x", "var var"),
    Command(0x23, "callasm 0x%08x", "ptr"),
    Command(0x24, "cmd24 0x%08x", "ptr"),
    Command(0x25, "special %#x", "word"),
    Command(0x26, "special2 %#x %#x", "var word"),
    Command(0x27, "waitstate", ""),
    Command(0x28, "pause %#x", "word"),
    Command(0x29, "setflag %#x", "flag/var"),
    Command(0x2A, "clearflag %#x", "flag/var"),
    Command(0x2B, "checkflag %#x", "flag/var"),
    Command(0x2C, "cmd2c", ""),
    Command(0x2D, "checkdailyflags", ""),
    Command(0x2E, "resetvars", ""),
    Command(0x2F, "sound %#x", "word"),
    Command(0x30, "checksound", ""),
    Command(0x31, "fanfare %#x", "word/var"),
    Command(0x32, "waitfanfare", ""),
    Command(0x33, "playsong %#x %#x", "word byte"),
    Command(0x34, "playsong2 %#x", "word"),
    Command(0x35, "fadedefault", ""),
    Command(0x36, "fadesong %#x", "word"),
    Command(0x37, "fadeout %#x", "byte"),
    Command(0x38, "fadein %#x", "byte"),
    Command(0x39, "warp (bank=%d,map=%d) warp#%d (x=%d,y=%d)", "byte byte byte byte/var byte/var"),
    Command(0x3A, "warpmuted (bank=%d,map=%d) warp#%d (x=%d,y=%d)", "byte byte byte byte/var byte/var"),
    Command(0x3B, "warpwalk (bank=%d,map=%d) warp#%d (x=%d,y=%d)", "byte byte byte byte/var byte/var"),
    Command(0x3C, "warphole %#x %#x", "byte byte"),
    Command(0x3D, "warpteleport (bank=%d,map=%d) warp#%d (x=%d,y=%d)", "byte byte byte byte/var byte/var"),
    Command(0x3E, "warp3 (bank=%d,map=%d) warp#%d (x=%d,y=%d)", "byte byte byte byte/var byte/var"),
    Command(0x3F, "setwarpplace %#x %#x %#x %#x %#x", "byte byte byte word word"),
    Command(0x40, "warp4 (bank=%d,map=%d) warp#%d (x=%d,y=%d)", "byte byte byte byte/var byte/var"),
    Command(0x41, "warp5 (bank=%d,map=%d) warp#%d (x=%d,y=%d)", "byte byte byte byte/var byte/var"),
    Command(0x42, "getplayerpos %#x %#x", "var var"),
    Command(0x43, "countPokémon", ""),
    Command(0x44, "additem %#x %#x", "word/var byte/var"),
    Command(0x45, "removeitem %#x %#x", "word/var byte/var"),
    Command(0x46, "checkitemroom %#x %#x", "word/var byte/var"),
    Command(0x47, "checkitem %#x %#x", "word/var byte/var"),
    Command(0x48, "checkitemtype %#x", "word/var"),
    Command(0x49, "addpcitem %#x %#x", "word/var word/var"),
    Command(0x4A, "checkpcitem %#x %#x", "word/var word/var"),
    Command(0x4B, "adddecoration %#x", "word/var"),
    Command(0x4C, "removedecoration %#x", "word/var"),
    Command(0x4D, "testdecoration %#x", "word/var"),
    Command(0x4E, "checkdecoration %#x", "word/var"),
    Command(0x4F, "applymovement %#x 0x%08x", "byte/var ptr"),
    Command(0x50, "applymovementpos %#x 0x%08x", "word ptr"),
    Command(0x51, "waitmovement %#x", "byte/var"),
    Command(0x52, "waitmovementpos %#x %#x %#x", "byte/var byte byte"),
    Command(0x53, "hidesprite %#x", "byte/var"),
    Command(0x54, "hidespritepos %#x %#x %#x", "byte/var byte byte"),
    Command(0x55, "showsprite %#x", "byte/var"),
    Command(0x56, "showspritepos %#x %#x %#x", "byte/var byte byte"),
    Command(0x57, "", ""),
    Command(0x58, "", ""),
    Command(0x59, "", ""),
    Command(0x5A, "faceplayer", ""),
    Command(0x5B, "", ""),
    Command(0x5C, "trainerbattle %#x %#x %#x 0x%08x 0x%08x 0x%08x 0x%08x", "byte word word ptr ptr ptr ptr"),
    Command(0x5D, "repeattrainerbattle", ""),
    Command(0x5E, "", ""),
    Command(0x5F, "", ""),
    Command(0x60, "checktrainerflag %#x", "word/var"),
    Command(0x61, "cleartrainerflag %#x", "word/var"),
    Command(0x62, "settrainerflag %#x", "word/var"),
    Command(0x63, "movesprite2 %d %d %d", "word word word"),
    Command(0x64, "moveoffscreen %#x", "word"),
    Command(0x65, "spritebehave %d %d", "word byte"),
    Command(0x66, "waitmsg", ""),
    CommandPrepareMsg(0x67, "preparemsg %#x", "ptr/bank0"),
    Command(0x68, "closeonkeypress", ""),
    Command(0x69, "lockall", ""),
    Command(0x6A, "lock", ""),
    Command(0x6B, "releaseall", ""),
    Command(0x6C, "release", ""),
    Command(0x6D, "waitkeypress", ""),
    Command(0x6E, "yesnobox %#x %#x", "byte byte"),
    Command(0x6F, "multichoice %#x %#x %#x %#x", "byte byte byte byte"),
    Command(0x70, "multichoice2 %#x %#x %#x %#x %#x", "byte byte byte byte byte"),
    Command(0x71, "multichoice3 %#x %#x %#x %#x %#x", "byte byte byte byte byte"),
    Command(0x72, "", ""),
    Command(0x73, "", ""),
    Command(0x74, "", ""),
    Command(0x75, "showpokepic %#x %#x %#x", "word/var byte byte"),
    Command(0x76, "hidepokepic", ""),
    Command(0x77, "showcontestwinner %#x", "byte"),
    Command(0x78, "braille %#x", "ptr/bank0"),
    Command(0x79, "givePokémon %#x %#x %#x %#x %#x %#x", "word/var byte word dword dword byte"),
    Command(0x7A, "", ""),
    Command(0x7B, "", ""),
    CommandCheckAttack(0x7C, "checkattack %#x", "word"),
    Command(0x7D, "bufferPokémon %d %#x", "buffer word/var"),
    Command(0x7E, "bufferfirstPokémon %d", "buffer"),
    Command(0x7F, "bufferpartyPokémon %d %#x", "buffer word/var"),
    Command(0x80, "bufferitem %d %#x", "buffer word/var"),
    Command(0x81, "bufferdecoration %#x", "word/var"),
    Command(0x82, "bufferattack %d %#x", "buffer word/var"),
    Command(0x83, "buffernumber %d %#x", "buffer word/var"),
    Command(0x84, "bufferstd %d %#x", "buffer word/var"),
    CommandBufferString(0x85, "bufferstring %d 0x%08x", "buffer ptr"),
    Command(0x86, "pokemart 0x%08x", "ptr"),
    Command(0x87, "pokemart2 0x%08x", "ptr"),
    Command(0x88, "pokemart3 0x%08x", "ptr"),
    Command(0x89, "", ""),
    Command(0x8A, "cmd8a", ""),
    Command(0x8B, "choosecontestpkmn", ""),
    Command(0x8C, "startcontest", ""),
    Command(0x8D, "showcontestresults", ""),
    Command(0x8E, "contestlinktransfer", ""),
    Command(0x8F, "random %#x", "word/var"),
    Command(0x90, "givemoney %#x %#x", "dword byte"),
    Command(0x91, "paymoney %#x %#x", "dword byte"),
    Command(0x92, "checkmoney %#x %#x", "dword byte"),
    Command(0x93, "showmoney %#x %#x", "byte byte"),
    Command(0x94, "hidemoney %#x %#x", "byte byte"),
    Command(0x95, "updatemoney %#x %#x", "byte byte"),
    Command(0x96, "cmd96", ""),
    Command(0x97, "fadescreen %#x", "byte"),
    Command(0x98, "", ""),
    Command(0x99, "", ""),
    Command(0x9A, "", ""),
    Command(0x9B, "", ""),
    Command(0x9C, "doanimation %#x", "word"),
    Command(0x9D, "setanimation %#x %#x", "byte word/var"),
    Command(0x9E, "checkanimation %#x", "word"),
    Command(0x9F, "sethealingplace %#x", "word"),
    Command(0xA0, "checkgender", ""),
    Command(0xA1, "cry %#x %#x", "word/var word"),
    Command(0xA2, "setmaptile %#x %#x %#x %#x", "word word word word"),
    Command(0xA3, "resetweather", ""),
    Command(0xA4, "setweather %#x", "word"),
    Command(0xA5, "doweather", ""),
    Command(0xA6, "cmda6 %#x", "byte"),
    Command(0xA7, "", ""),
    Command(0xA8, "", ""),
    Command(0xA9, "", ""),
    Command(0xAA, "", ""),
    Command(0xAB, "", ""),
    Command(0xAC, "setdooropened %#x %#x", "word word"),
    Command(0xAD, "setdoorclosed %#x %#x", "word word"),
    Command(0xAE, "doorchange", ""),
    Command(0xAF, "setdooropened2 %#x %#x", "word word"),
    Command(0xB0, "setdoorclosed2 %#x %#x", "word word"),
    Command(0xB1, "cmdb1", ""),
    Command(0xB2, "cmdb2", ""),
    Command(0xB3, "", ""),
    Command(0xB4, "", ""),
    Command(0xB5, "", ""),
    Command(0xB6, "setwildbattle %#x %#x %#x", "word byte word"),
    Command(0xB7, "dowildbattle", ""),
    Command(0xB8, "", ""),
    Command(0xB9, "", ""),
    Command(0xBA, "", ""),
    Command(0xBB, "", ""),
    Command(0xBC, "", ""),
    Command(0xBD, "", ""),
    Command(0xBE, "", ""),
    Command(0xBF, "", ""),
    Command(0xC0, "showcoins %#x %#x", "byte byte"),
    Command(0xC1, "hidecoins", ""),
    Command(0xC2, "updatecoins %#x %#x", "byte byte"),
    Command(0xC3, "cmdc3 %d", "hidden"),
    Command(0xC4, "warp6", ""),
    Command(0xC5, "waitcry", ""),
    Command(0xC6, "bufferboxname %d %#x", "buffer word/var"),
    Command(0xC7, "textcolor %#x", "byte"),
    Command(0xC8, "cmdc8 %#x", "ptr/bank0"),
    Command(0xC9, "cmdc9", ""),
    Command(0xCA, "signmsg", ""),
    Command(0xCB, "normalmsg", ""),
    Command(0xCC, "comparehiddenvar %d %#x", "hidden dword"),
    Command(0xCD, "setobedience %#x", "word"),
    Command(0xCE, "checkobedience %#x", "word/var"),
    Command(0xCF, "executeram", ""),
    Command(0xD0, "setworldmapflag %#x", "flag/var"),
    Command(0xD1, "warpteleport2", ""),
    Command(0xD2, "setcatchlocation %#x %#x", "word/var byte"),
    Command(0xD3, "braille2 %#x", "ptr/bank0"),
    Command(0xD4, "bufferitems %d %#x %#x", "buffer word/var word/var"),
    Command(0xD5, "cmdd5", "")
]
