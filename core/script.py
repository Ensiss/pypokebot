import numpy as np
import memory; mem = memory.Memory
import database; db = database.Database
import struct
import enum
import sys

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

    def unrolledString(self, addr):
        """
        Convenience function to read a pokestring and unroll it in one line.
        """
        return mem.readPokeStr(addr).replace("\n", " ")

    def format(self, instr):
        """
        Called to pretty print a script. Override to define specific behavior.
        """
        return self.str_fmt % instr.args

    def inPrint(self, jumps, instr):
        """
        Called for each instruction when pretty printing.
        Override to store jumps to other scripts.
        """
        return

    def argsFormat(self, instr):
        """
        Return struct formatting string. Override for dynamic commands.
        """
        return self.fmt

    def checkPreviousVisit(self, ctx, conditionals, spec=None):
        """
        Check if the current pc+call stack was already visited.
        'spec' can be used to differentiate different branches of a conditional
        Exit if the point was visited, register a new visit otherwise.
        """
        cs = ctx.getCallStack() + (spec,)
        if cs in conditionals:
            ctx.do_exit = True
            return True
        conditionals[cs] = True
        return False

    def execute(self, open_ctxs, conditionals, ctx, instr):
        """
        Called to simulate script execution and update the context.
        Should ideallly update the current context exactly as the in-game script.
        By default, only moves the context pc to the next instruction.
        """
        ctx.pc = instr.next_addr

    def explore(self, open_ctxs, conditionals, ctx, instr):
        """
        Called to explore all script branches and track inputs and outputs.
        This should be different from execute only for branching instructions.
        """
        return self.execute(open_ctxs, conditionals, ctx, instr)

class CommandEnd(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.do_exit = True

class CommandReturn(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        if len(ctx.stack) == 0:
            ctx.do_exit = True
            return
        ctx.pc = ctx.stack.pop()

class CommandCall(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.stack.append(instr.next_addr)
        ctx.pc = instr.args[0]

    def inPrint(self, jumps, instr):
        jumps.append(instr.args[-1])

class CommandGoto(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.pc = instr.args[0]

    def inPrint(self, jumps, instr):
        jumps.append(instr.args[-1])

class CommandIf(Command):
    def format(self, instr):
        op = ["<", "==", ">", "<=", ">=", "!=", "?"][min(6, instr.args[0])]
        cmd = "goto" if instr.opcode == 0x06 else "call"
        return  "if %s %s 0x%08x" % (op, cmd, instr.args[1])

    def inPrint(self, jumps, instr):
        jumps.append(instr.args[-1])

    def exploreFalse(self, conditionals, ctx, instr):
        ctx.pc = instr.next_addr

    def explore(self, open_ctxs, conditionals, ctx, instr):
        if instr.addr not in conditionals:
            conditionals[instr.addr] = True
            jump_ctx = ctx.copyTo(open_ctxs)
            self.exploreTrue(conditionals, jump_ctx, instr)
            self.exploreFalse(conditionals, ctx, instr)
        else:
            ctx.do_exit = True

class CommandIfJump(CommandIf):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        if instr.args[0] > 5:
            print("IfJump error: no operator %d" % instr.args[0])
            return
        cond = Command.cmd_op[instr.args[0]](ctx.cmp1, ctx.cmp2)
        if self.checkPreviousVisit(ctx, conditionals, cond):
            return
        if cond:
            ctx.pc = instr.args[1]
        else:
            Command.execute(self, open_ctxs, conditionals, ctx, instr)

    def exploreTrue(self, conditionals, ctx, instr):
        ctx.pc = instr.args[1]

class CommandIfCall(CommandIf):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        if instr.args[0] > 5:
            print("IfCall error: no operator %d" % instr.args[0])
            return
        cond = Command.cmd_op[instr.args[0]](ctx.cmp1, ctx.cmp2)
        if self.checkPreviousVisit(ctx, conditionals, cond):
            return
        if cond:
            ctx.stack.append(instr.next_addr)
            ctx.pc = instr.args[1]
        else:
            Command.execute(self, open_ctxs, conditionals, ctx, instr)

    def exploreTrue(self, conditionals, ctx, instr):
        ctx.stack.append(instr.next_addr)
        ctx.pc = instr.args[1]

class CommandStd(Command):
    def funcAddr(self, n):
        return mem.readU32(0x08160450 + n * 4)
    def inPrint(self, jumps, instr):
        jumps.append(self.funcAddr(instr.args[-1]))

class CommandCallStd(CommandStd):
    def format(self, instr):
        return  "call std%#x(0x%08x)" % (instr.args[0], self.funcAddr(instr.args[0]))
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.stack.append(instr.next_addr)
        ctx.pc = self.funcAddr(instr.args[0])
class CommandGotoStd(CommandStd):
    def format(self, instr):
        return  "goto std%#x(0x%08x)" % (instr.args[0], self.funcAddr(instr.args[0]))
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.pc = self.funcAddr(instr.args[0])

class CommandIfStd(CommandStd):
    def format(self, instr):
        op = ["<", "==", ">", "<=", ">=", "!=", "?"][min(6, instr.args[0])]
        cmd = "goto" if instr.opcode == 0x0a else "call"
        return  "if %s %s std%#x(0x%08x)" % (
            op, cmd, instr.args[1], self.funcAddr(instr.args[1]))

    def exploreFalse(self, conditionals, ctx, instr):
        ctx.pc = instr.next_addr

    def explore(self, open_ctxs, conditionals, ctx, instr):
        if instr.addr not in conditionals:
            conditionals[instr.addr] = True
            jump_ctx = ctx.copyTo(open_ctxs)
            self.exploreTrue(conditionals, jump_ctx, instr)
            self.exploreFalse(conditionals, ctx, instr)
        else:
            ctx.do_exit = True

class CommandIfJumpStd(CommandIfStd):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        if instr.args[0] > 5:
            print("IfJumpStd error: no operator %d" % instr.args[0])
            return
        cond = Command.cmd_op[instr.args[0]](ctx.cmp1, ctx.cmp2)
        if self.checkPreviousVisit(ctx, conditionals, cond):
            return
        if cond:
            ctx.pc = self.funcAddr(instr.args[1])
        else:
            Command.execute(self, open_ctxs, conditionals, ctx, instr)

    def exploreTrue(self, conditionals, ctx, instr):
        ctx.pc = self.funcAddr(instr.args[1])

class CommandIfCallStd(CommandIfStd):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        if instr.args[0] > 5:
            print("IfCallStd error: no operator %d" % instr.args[0])
            return
        cond = Command.cmd_op[instr.args[0]](ctx.cmp1, ctx.cmp2)
        if self.checkPreviousVisit(ctx, conditionals, cond):
            return
        if cond:
            ctx.stack.append(instr.next_addr)
            ctx.pc = self.funcAddr(instr.args[1])
        else:
            Command.execute(self, open_ctxs, conditionals, ctx, instr)

    def exploreTrue(self, conditionals, ctx, instr):
        ctx.stack.append(instr.next_addr)
        ctx.pc = self.funcAddr(instr.args[1])

class CommandLoadPointer(Command):
    def format(self, instr):
        return "loadpointer %d \"%s\"" % (instr.args[0], self.unrolledString(instr.args[1]))
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.setBank(instr.args[0], instr.args[1])
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandSetByte(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.setBank(instr.args[0], instr.args[1])
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandLoadByteFromPtr(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.setBank(instr.args[0], mem.readU8(instr.args[1]))
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCopyScriptBanks(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.setBank(instr.args[0], ctx.getBank(instr.args[1]))
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandSetVar(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.setVar(instr.args[0], instr.args[1])
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandAddVar(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.setVar(instr.args[0], ctx.getVar(instr.args[0]) + instr.args[1])
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandSubVar(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.setVar(instr.args[0], ctx.getVar(instr.args[0]) - instr.args[1])
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCopyVar(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.setVar(instr.args[0], ctx.getVar(instr.args[1]))
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCopyVarIfNotZero(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        if Script.isVar(instr.args[1]) or Script.isSpcVar(instr.args[1]):
            CommandCopyVar.execute(self, open_ctxs, conditionals, ctx, instr)
        else:
            CommandSetVar.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCompareBanks(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.compare8(ctx.getBank(instr.args[0]), ctx.getBank(instr.args[1]))
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCompareBankToByte(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.compare8(ctx.getBank(instr.args[0]), instr.args[1])
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCompareBankToFarByte(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.compare8(ctx.getBank(instr.args[0]), mem.readU8(instr.args[1]))
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCompareFarByteToBank(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.compare8(mem.readU8(instr.args[0]), ctx.getBank(instr.args[1]))
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCompareFarByteToByte(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.compare8(mem.readU8(instr.args[0]), instr.args[1])
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCompareFarBytes(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.compare8(mem.readU8(instr.args[0]), mem.readU8(instr.args[1]))
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCompare(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.compare(ctx.getVar(instr.args[0]), instr.args[1])
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCompareVars(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.compare(ctx.getVar(instr.args[0]), ctx.getVar(instr.args[1]))
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandBufferString(Command):
    def format(self, instr):
        return "bufferstring %d \"%s\"" % (instr.args[0], self.unrolledString(instr.args[1]))

class CommandCheckMoney(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        if not instr.args[1]:
            ctx.setVar(Script.LASTRESULT, db.player.money >= instr.args[0])
        Command.execute(self, open_ctxs, conditionals, ctx, instr)
    def explore(self, open_ctxs, conditionals, ctx, instr):
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCheckGender(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.setVar(Script.LASTRESULT, db.player.gender)
        Command.execute(self, open_ctxs, conditionals, ctx, instr)
    def explore(self, open_ctxs, conditionals, ctx, instr):
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCheckCoins(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.setVar(instr.args[0], db.player.coins)
        Command.execute(self, open_ctxs, conditionals, ctx, instr)
    def explore(self, open_ctxs, conditionals, ctx, instr):
        ctx.setVar(instr.args[0], 0)
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandGetPartySize(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.setVar(Script.LASTRESULT, db.getPartySize())
        Command.execute(self, open_ctxs, conditionals, ctx, instr)
    def explore(self, open_ctxs, conditionals, ctx, instr):
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCheckItemRoom(Command):
    def checkHasSpace(self, item_id, count):
        if item_id == 0 or db.items[item_id].pocket == 0:
            return False
        item = db.items[item_id]
        pocket = db.bag[item.pocket-1]
        for inbag_item in pocket:
            if inbag_item.idx == item_id:
                return inbag_item.quantity + count <= 999
        # If there are still empty pockets, return True
        return len(pocket) < pocket.capacity

    def execute(self, open_ctxs, conditionals, ctx, instr):
        item_id = ctx.getVar(instr.args[0])
        quantity = ctx.getVar(instr.args[1])
        ctx.setVar(Script.LASTRESULT, self.checkHasSpace(item_id, quantity))
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

    def explore(self, open_ctxs, conditionals, ctx, instr):
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCheckItem(Command):
    def hasItem(self, item_id, count):
        if item_id == 0 or db.items[item_id].pocket == 0:
            return False
        item = db.items[item_id]
        pocket = db.bag[item.pocket-1]
        for inbag_item in pocket:
            if inbag_item.idx == item_id:
                return inbag_item.quantity >= count
        return False

    def execute(self, open_ctxs, conditionals, ctx, instr):
        item_id = ctx.getVar(instr.args[0])
        quantity = ctx.getVar(instr.args[1])
        ctx.setVar(Script.LASTRESULT, self.hasItem(item_id, quantity))
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

    def explore(self, open_ctxs, conditionals, ctx, instr):
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCheckItemType(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        item_id = ctx.getVar(instr.args[0])
        ctx.setVar(Script.LASTRESULT, db.items[item_id].pocket)
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

    def explore(self, open_ctxs, conditionals, ctx, instr):
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandHideSprite(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        local_id = ctx.getVar(instr.args[0]) # Local ids are 1-indexed
        if local_id == 0xFF: # Player id
            return Command.execute(self, open_ctxs, conditionals, ctx, instr)
        if len(instr.args) == 1:
            bank_id = ctx.parent.bank_id
            map_id = ctx.parent.map_id
        else:
            bank_id = instr.args[1]
            map_id = instr.args[2]
        vis_flag = db.banks[bank_id][map_id].persons[local_id-1].idx
        if vis_flag != 0:
            ctx.setFlag(vis_flag, 1)
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandShowSprite(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        local_id = ctx.getVar(instr.args[0]) # Local ids are 1-indexed
        if local_id == 0xFF: # Player id
            return Command.execute(self, open_ctxs, conditionals, ctx, instr)
        if len(instr.args) == 1:
            bank_id = ctx.parent.bank_id
            map_id = ctx.parent.map_id
        else:
            bank_id = instr.args[1]
            map_id = instr.args[2]
        vis_flag = db.banks[bank_id][map_id].persons[local_id-1].idx
        if vis_flag != 0:
            ctx.setFlag(vis_flag, 0)
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandTrainerBattle(Command):
    def format(self, instr):
        cmd_type = instr.args[0]
        if cmd_type > 9:
            cmd_type = 0
        ttext = ["normal",
                 "run_after_win", "run_after_win",
                 "continue_caller",
                 "double",
                 "rematch",
                 "double_special",
                 "double_rematch",
                 "double_special",
                 "tutorial"][cmd_type]
        fmt = "trainerbattle %s" % ttext
        fmt += "(%#x)" % instr.args[0]
        fmt += " %#x %#x" % instr.args[1:3]
        for i, arg in enumerate(instr.args[3:]):
            if (cmd_type == 1 or cmd_type == 2) and i == 2:
                fmt += " @0x%08x" % instr.args[3+i]
            else:
                fmt += ' "%s"' % self.unrolledString(instr.args[3+i])
        return fmt

    def inPrint(self, jumps, instr):
        if instr.args[0] == 1 or instr.args[0] == 2:
            jumps.append(instr.args[5])

    def argsFormat(self, instr):
        cmd_type = mem.readU8(instr.addr + 1)
        if cmd_type > 9:
            cmd_type = 0
        nptrs = [2, 3, 3, 1, 3, 2, 4, 3, 4, 2][cmd_type]
        return self.fmt[:3+nptrs]

    def explore(self, open_ctxs, conditionals, ctx, instr):
        if instr.args[0] == 1 or instr.args[0] == 2:
            jump_ctx = ctx.copyTo(open_ctxs)
            jump_ctx.pc = instr.args[5]
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandCheckTrainerFlag(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.compare(ctx.getFlag(ctx.getVar(instr.args[0]) + 0x500), 1)
        Command.execute(self, open_ctxs, conditionals, ctx, instr)
class CommandSetTrainerFlag(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.setFlag(ctx.getVar(instr.args[0]) + 0x500, 1)
        Command.execute(self, open_ctxs, conditionals, ctx, instr)
class CommandClearTrainerFlag(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.setFlag(ctx.getVar(instr.args[0]) + 0x500, 0)
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandPrepareMsg(Command):
    def format(self, instr):
        if instr.args[0] == 0:
            return self.str_fmt % instr.args
        return "preparemsg \"%s\"" % self.unrolledString(instr.args[0])

class CommandYesNoBox(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        # Only allow passing through once
        if self.checkPreviousVisit(ctx, conditionals):
            return

        # Update pc before forking
        Command.execute(self, open_ctxs, conditionals, ctx, instr)
        # Yes in another context
        yes_ctx = ctx.copyTo(open_ctxs)
        yes_ctx.setVar(Script.LASTRESULT, 1)
        yes_ctx.choices.append(0)

        # No in current context
        ctx.setVar(Script.LASTRESULT, 0)
        ctx.choices.append(1)
    def explore(self, open_ctxs, conditionals, ctx, instr):
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandMultichoice(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        # Only allow passing through once
        if self.checkPreviousVisit(ctx, conditionals):
            return

        mchoice = db.multi_choices[instr.args[2]]
        nchoices = mchoice.nb_choices

        # Update pc before forking
        Command.execute(self, open_ctxs, conditionals, ctx, instr)
        # B-button back out
        if instr.args[-1] == 0:
            tmp_ctx = ctx.copyTo(open_ctxs)
            tmp_ctx.choices.append(0x7f)
            tmp_ctx.setVar(Script.LASTRESULT, 0x7f)
        # One context per choice, last choice in current context
        for i in range(nchoices):
            if i == nchoices-1:
                tmp_ctx = ctx
            else:
                tmp_ctx = ctx.copyTo(open_ctxs)
            tmp_ctx.choices.append(i)
            tmp_ctx.setVar(Script.LASTRESULT, i)
    def explore(self, open_ctxs, conditionals, ctx, instr):
        Command.execute(self, open_ctxs, conditionals, ctx, instr)
    def format(self, instr):
        mchoice = db.multi_choices[instr.args[2]]
        s = "multichoice x=%d,y=%d id%#x(%s)" % (
            instr.args[0], instr.args[1], instr.args[2],
            "/".join(mchoice.choices))
        for x in instr.args[3:]:
            s += " %#x" % x
        return s

class CommandCheckAttack(Command):
    def format(self, instr):
        return "checkattack \"%s\"" % db.moves[instr.args[0]].name
    def execute(self, open_ctxs, conditionals, ctx, instr):
        out = 0x6
        for i, p in enumerate(db.pteam):
            if p.growth.species_idx == 0:
                break
            if instr.args[0] in p.attacks.move_ids:
                out = i
                break
        ctx.setVar(Script.LASTRESULT, out)
        Command.execute(self, open_ctxs, conditionals, ctx, instr)
    def explore(self, open_ctxs, conditionals, ctx, instr):
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandSetFlag(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.setFlag(instr.args[0], 1)
        Command.execute(self, open_ctxs, conditionals, ctx, instr)
class CommandClearFlag(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.setFlag(instr.args[0], 0)
        Command.execute(self, open_ctxs, conditionals, ctx, instr)
class CommandCheckFlag(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        ctx.compare(ctx.getFlag(instr.args[0]), 1)
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class CommandResetVars(Command):
    def execute(self, open_ctxs, conditionals, ctx, instr):
        for v in range(0x8000, 0x8003):
            ctx.setVar(v, 0)
        Command.execute(self, open_ctxs, conditionals, ctx, instr)

class Instruction:
    def __init__(self, addr):
        self.addr = addr
        self.opcode = mem.readU8(addr)
        self.cmd = cmds[self.opcode]
        self.args_fmt = self.cmd.argsFormat(self)
        self.args = mem.unpack(addr+1, self.args_fmt)
        self.size = struct.calcsize("<" + self.args_fmt) + 1 # +1 for bytecode
        self.next_addr = self.addr + self.size

    def __len__(self):
        return self.size

    def __str__(self):
        return self.cmd.format(self)

class Script:
    FLAG_COUNT = 0x900
    BANK_COUNT = 0x04
    BUFF_COUNT = 0x03
    VAR_OFFSET = 0x4000
    VAR_COUNT = 0x100
    SPCVAR_OFFSET = 0x8000
    SPCVAR_COUNT = 0x1F
    SPCFLAG_OFFSET = 0x4000
    SPCFLAG_COUNT = 0x10
    FACING = 0x800C
    LASTRESULT = 0x800D
    ITEM_ID = 0x800E
    LASTTALKED = 0x800F

    cache = {}

    class Type(enum.IntEnum):
        PERSON = 0
        SIGN = enum.auto()
        SCRIPT = enum.auto()
        MAPSCRIPT = enum.auto()
        STD = enum.auto()
        NONE = enum.auto()

    class Storage:
        def __init__(self, fmt, val):
            self.fmt = fmt
            self.val = val
        def __int__(self):
            return self.val
        def __eq__(self, other):
            return self.val == other.val and type(self) == type(other)
        def __str__(self):
            return self.fmt % self.val
        def __hash__(self):
            return hash(str(self))

    class Flag(Storage):
        def __init__(self, val):
            super().__init__("flag(0x%x)", val)
    class Var(Storage):
        def __init__(self, val):
            super().__init__("var(0x%x)", val)
    class Bank(Storage):
        def __init__(self, val):
            super().__init__("bank(%d)", val)
    class Buffer(Storage):
        def __init__(self, val):
            super().__init__("buffer(%d)", val)

    def isFlag(x):
        return x < Script.FLAG_COUNT
    def isSpcFlag(x):
        return Script.SPCFLAG_COUNT <= x < Script.SPCFLAG_OFFSET + Script.SPCFLAG_COUNT
    def isBank(x):
        return x < Script.BANK_COUNT
    def isVar(x):
        return Script.VAR_OFFSET <= x < Script.VAR_OFFSET + Script.VAR_COUNT
    def isSpcVar(x):
        return Script.SPCVAR_OFFSET <= x < Script.SPCVAR_OFFSET + Script.SPCVAR_COUNT

    class Context:
        def __init__(self, other=None):
            if other is None:
                ptr = mem.readU32(0x03005008)
                self.flags = np.frombuffer(mem.bufferFromAddr(ptr + 0xEE0)[:Script.FLAG_COUNT >> 3], dtype=np.uint8).copy()
                self.spcflags = np.zeros(Script.SPCFLAG_COUNT >> 3, dtype=np.uint8)
                self.variables = np.frombuffer(mem.bufferFromAddr(ptr + 0x1000)[:Script.VAR_COUNT * 2], dtype=np.uint16).copy()
                self.spcvars = np.zeros(Script.SPCVAR_COUNT, dtype=np.uint16)
                self.banks = np.zeros(Script.BANK_COUNT, dtype=np.uint32)
                self.cmp1 = self.cmp2 = 0
                self.pc = 0
                self.stack = []
                self.inputs = set()
                self.outputs = set()
                self.do_exit = False
                self.choices = []
                self.parent = None
            else:
                self.flags = other.flags.copy()
                self.spcflags = other.spcflags.copy()
                self.variables = other.variables.copy()
                self.spcvars = other.spcvars.copy()
                self.banks = other.banks.copy()
                self.cmp1 = other.cmp1
                self.cmp2 = other.cmp2
                self.pc = other.pc
                self.stack = other.stack.copy()
                self.inputs = other.inputs.copy()
                self.outputs = other.outputs.copy()
                self.do_exit = other.do_exit
                self.choices = other.choices.copy()
                self.parent = other.parent

        def initFor(self, parent):
            self.parent = parent
            self.pc = parent.addr
            if parent.type == Script.Type.PERSON:
                self.setVar(Script.LASTTALKED, parent.idx+1, track=False)

        def copy(self):
            return Script.Context(self)
        def copyTo(self, open_ctxs):
            other = self.copy()
            open_ctxs.append(other)
            return other

        def getCallStack(self):
            return tuple(self.stack + [self.pc])

        def getFlag(self, idx, track=True):
            raw = idx
            if not (Script.isFlag(idx) or Script.isSpcFlag(idx)) and Script.isVar(idx):
                idx = self.getVar(idx)
            if track:
                self.inputs.add(Script.Flag(idx))
            if Script.isFlag(idx):
                return bool(self.flags[idx >> 3] & (1 << (idx % 8)))
            if Script.isSpcFlag(idx):
                idx = idx - Script.SPCFLAG_OFFSET
                return bool(self.spcflags[idx >> 3] & (1 << (idx % 8)))
            print("Context error: flag %d(raw=%d) does not exist" % (idx, raw))
            return 0

        def getVar(self, idx, track=True):
            if Script.isVar(idx):
                if track:
                    self.inputs.add(Script.Var(idx))
                return self.variables[idx - Script.VAR_OFFSET]
            elif Script.isSpcVar(idx):
                if track:
                    self.inputs.add(Script.Var(idx))
                return self.spcvars[idx - Script.SPCVAR_OFFSET]
            else:
                return idx
            return 0

        def getBank(self, idx, track=True):
            if Script.isBank(idx):
                if track:
                    self.inputs.add(Script.Bank(idx))
                return self.banks[idx]
            print("Context error: bank %d does not exist" % idx)
            return 0

        def setFlag(self, idx, val, track=True):
            raw = idx
            if not (Script.isFlag(idx) or Script.isSpcFlag(idx)) and Script.isVar(idx):
                idx = self.getVar(idx)
            if track:
                self.outputs.add(Script.Flag(idx))
            if Script.isFlag(idx) or Script.isSpcFlag(idx):
                flagbuf = self.flags if Script.isFlag(idx) else self.spcflags
                idx = idx if Script.isFlag(idx) else idx - Script.SPCFLAG_OFFSET
                if val:
                    flagbuf[idx >> 3] |= (1 << (idx % 8))
                else:
                    flagbuf[idx >> 3] &= ~(1 << (idx % 8))
            else:
                print("Context error: flag %d(raw=%d) does not exist" % (idx, raw))

        def setVar(self, idx, val, track=True):
            if Script.isVar(idx):
                if track:
                    self.outputs.add(Script.Var(idx))
                self.variables[idx - Script.VAR_OFFSET] = val
            elif Script.isSpcVar(idx):
                if track:
                    self.outputs.add(Script.Var(idx))
                self.spcvars[idx - Script.SPCVAR_OFFSET] = val
            else:
                print("Context error: variable %d does not exist" % idx)

        def setBank(self, idx, val, track=True):
            if Script.isBank(idx):
                if track:
                    self.outputs.add(Script.Bank(idx))
                self.banks[idx] = val
            else:
                print("Context error: bank %d does not exist" % idx)

        def compare(self, a, b):
            self.cmp1 = a
            self.cmp2 = b

        def compare8(self, a, b):
            self.compare(np.uint8(a), np.uint8(b))

    def __init__(self, addr, bid=-1, mid=-1, idx=-1, stype=-1):
        self.bank_id = bid
        self.map_id = mid
        self.idx = idx
        self.type = Script.Type.NONE
        if stype != -1:
            self.type = stype
        self.addr = addr
        self.ctxs = self.explore()
        self.outflags = set()
        for ctx in self.ctxs:
            for storage in ctx.outputs:
                if type(storage) is Script.Flag:
                    self.outflags.add(int(storage))
        self.inflags = set()
        for ctx in self.ctxs:
            for storage in ctx.inputs:
                if type(storage) is Script.Flag:
                    self.inflags.add(int(storage))

    def clearCache():
        Script.cache.clear()
    def loadCache():
        for bid, bank in enumerate(db.banks):
            for mid, m in enumerate(bank):
                for idx in range(len(m.persons)):
                    if m.persons[idx].script_ptr == 0:
                        continue
                    Script.getPerson(idx, bid, mid)
                for idx in range(len(m.signs)):
                    if m.signs[idx].type != 0: # Hidden items
                        continue
                    Script.getSign(idx, bid, mid)
                for idx in range(len(m.scripts)):
                    Script.getScript(idx, bid, mid)
                for idx in range(len(m.map_scripts)):
                    Script.getMapScript(idx, bid, mid)
    def printCache(path="resources/scripts.txt"):
        with open(path, "w") as out:
            for (bid, mid, idx, stype), s in Script.cache.items():
                sname = ["person","sign","script","mapscript","std","none"][stype]
                print("\n" + "-"*80, file=out)
                print("%s#%02d @ map[%d,%d]" % (sname, idx, bid, mid), file=out)
                s.print(out)

    def getAt(addr):
        return Script(addr)

    def getGeneric(idx, stype, bank_id=-1, map_id=-1):
        def getCached(addr, bank_id, map_id, idx, stype):
            cache_idx = (bank_id, map_id, idx, stype)
            if cache_idx in Script.cache:
                return Script.cache[cache_idx]
            s = Script(addr, bank_id, map_id, idx, stype)
            Script.cache[cache_idx] = s
            return s

        if stype == Script.Type.STD and idx < 10:
            return getCached(mem.readU32(0x08160450 + n * 4), -1, -1, idx, stype)
        if stype < Script.Type.STD and bank_id == -1 and map_id == -1:
            bank_id = db.player.bank_id
            map_id = db.player.map_id
        if bank_id >= len(db.banks) or map_id >= len(db.banks[bank_id]):
            print("getScript error: map [%d, %d] not found" %
                  (bank_id, map_id))
            return None
        m = db.banks[bank_id][map_id]
        if stype == Script.Type.PERSON and idx < len(m.persons):
            addr = m.persons[idx].script_ptr
        elif stype == Script.Type.SIGN and idx < len(m.signs):
            addr = m.signs[idx].script_ptr
        elif stype == Script.Type.SCRIPT and idx < len(m.scripts):
            addr = m.scripts[idx].script_ptr
        elif stype == Script.Type.MAPSCRIPT and idx < len(m.map_scripts):
            addr = m.map_scripts[idx].script_ptr
        else:
            print("getGeneric error: cannot find script %d of type %d in map [%d, %d]" % (idx, stype, bank_id, map_id))
            return None
        return getCached(addr, bank_id, map_id, idx, stype)

    def getStd(idx):
        return Script.getGeneric(idx, Script.Type.STD)
    def getPerson(idx, bank_id=-1, map_id=-1):
        return Script.getGeneric(idx, Script.Type.PERSON, bank_id, map_id)
    def getSign(idx, bank_id=-1, map_id=-1):
        return Script.getGeneric(idx, Script.Type.SIGN, bank_id, map_id)
    def getScript(idx, bank_id=-1, map_id=-1):
        return Script.getGeneric(idx, Script.Type.SCRIPT, bank_id, map_id)
    def getMapScript(idx, bank_id=-1, map_id=-1):
        return Script.getGeneric(idx, Script.Type.MAPSCRIPT, bank_id, map_id)

    def print(self, out=sys.stdout):
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
                print(header + str(instr), file=out)
                # Store destination of jumps and conditions
                instr.cmd.inPrint(jumps, instr)
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
                print("", file=out)
            subPrint(addr)

    def explore(self):
        context = Script.Context()
        context.initFor(self)
        conditionals = {}
        open_ctxs = [context]
        closed_ctxs = []
        while len(open_ctxs) > 0:
            ctx = open_ctxs.pop(0)
            while True:
                instr = Instruction(ctx.pc)
                instr.cmd.explore(open_ctxs, conditionals, ctx, instr)
                if ctx.do_exit:
                    closed_ctxs.append(ctx)
                    break
        return closed_ctxs

    def execute(self, context=None):
        if context is None:
            context = Script.Context()
        context.initFor(self)
        conditionals = {}
        open_ctxs = [context]
        closed_ctxs = []
        while len(open_ctxs) > 0:
            ctx = open_ctxs.pop(0)
            while True:
                instr = Instruction(ctx.pc)
                instr.cmd.execute(open_ctxs, conditionals, ctx, instr)
                if ctx.do_exit:
                    closed_ctxs.append(ctx)
                    break
        return closed_ctxs

cmds = [
    Command(0x00, "nop", ""),
    Command(0x01, "nop1", ""),
    CommandEnd(0x02, "end", ""),
    CommandReturn(0x03, "return", ""),
    CommandCall(0x04, "call 0x%08x", "ptr"),
    CommandGoto(0x05, "goto 0x%08x", "ptr"),
    CommandIfJump(0x06, "if %#x jump 0x%08x", "byte ptr"),
    CommandIfCall(0x07, "if %#x call 0x%08x", "byte ptr"),
    CommandGotoStd(0x08, "gotostd %#x", "byte"),
    CommandCallStd(0x09, "callstd %#x", "byte"),
    CommandIfJumpStd(0x0A, "gotostdif %#x %#x", "byte byte"),
    CommandIfCallStd(0x0B, "callstdif %#x %#x", "byte byte"),
    Command(0x0C, "jumpram", ""),
    Command(0x0D, "killscript", ""),
    Command(0x0E, "setmysteryeventstatus %#x", "byte"),
    CommandLoadPointer(0x0F, "loadpointer %d %#x", "bank dword"),
    CommandSetByte(0x10, "setbyte %d %#x", "bank byte"),
    Command(0x11, "writebytetooffset %#x 0x%08x", "byte ptr"),
    CommandLoadByteFromPtr(0x12, "loadbytefrompointer %d 0x%08x", "bank ptr"),
    Command(0x13, "setfarbyte %d 0x%08x", "bank ptr"),
    CommandCopyScriptBanks(0x14, "copyscriptbanks %d %d", "bank bank"),
    Command(0x15, "copybyte 0x%08x 0x%08x", "ptr ptr"),
    CommandSetVar(0x16, "setvar %#x %#x", "var word"),
    CommandAddVar(0x17, "addvar %#x %#x", "var word"),
    CommandSubVar(0x18, "subvar %#x %#x", "var word/var"),
    CommandCopyVar(0x19, "copyvar %#x %#x", "var var"),
    CommandCopyVarIfNotZero(0x1A, "copyvarifnotzero %#x %#x", "var word/var"),
    CommandCompareBanks(0x1B, "comparebanks %d %d", "bank bank"),
    CommandCompareBankToByte(0x1C, "comparebanktobyte %d %#x", "bank byte"),
    CommandCompareBankToFarByte(0x1D, "comparebanktofarbyte %d 0x%08x", "bank ptr"),
    CommandCompareFarByteToBank(0x1E, "comparefarbytetobank 0x%08x %d", "ptr bank"),
    CommandCompareFarByteToByte(0x1F, "comparefarbytetobyte 0x%08x %#x", "ptr byte"),
    CommandCompareFarBytes(0x20, "comparefarbytes 0x%08x 0x%08x", "ptr ptr"),
    CommandCompare(0x21, "compare %#x %#x", "var word"),
    CommandCompareVars(0x22, "comparevars %#x %#x", "var var"),
    Command(0x23, "callasm 0x%08x", "ptr"),
    Command(0x24, "gotoasm 0x%08x", "ptr"),
    Command(0x25, "special %#x", "word"),
    Command(0x26, "specialvar %#x %#x", "var word"),
    Command(0x27, "waitstate", ""),
    Command(0x28, "pause %#x", "word"),
    CommandSetFlag(0x29, "setflag %#x", "flag/var"),
    CommandClearFlag(0x2A, "clearflag %#x", "flag/var"),
    CommandCheckFlag(0x2B, "checkflag %#x", "flag/var"),
    Command(0x2C, "initclock(nop)", ""),
    Command(0x2D, "checkdailyflags(nop)", ""),
    CommandResetVars(0x2E, "resetvars", ""),
    Command(0x2F, "sound %#x", "word"),
    Command(0x30, "waitsound", ""),
    Command(0x31, "fanfare %#x", "word/var"),
    Command(0x32, "waitfanfare", ""),
    Command(0x33, "playsong %#x %#x", "word byte"),
    Command(0x34, "savesong %#x", "word"),
    Command(0x35, "fadedefault", ""),
    Command(0x36, "fadesong %#x", "word"),
    Command(0x37, "fadeout %#x", "byte"),
    Command(0x38, "fadein %#x", "byte"),
    Command(0x39, "warp (bank=%d,map=%d) warp#%d (x=%d,y=%d)", "byte byte byte byte/var byte/var"),
    Command(0x3A, "warpsilent (bank=%d,map=%d) warp#%d (x=%d,y=%d)", "byte byte byte byte/var byte/var"),
    Command(0x3B, "warpdoor (bank=%d,map=%d) warp#%d (x=%d,y=%d)", "byte byte byte byte/var byte/var"),
    Command(0x3C, "warphole %#x %#x", "byte byte"),
    Command(0x3D, "warpteleport (bank=%d,map=%d) warp#%d (x=%d,y=%d)", "byte byte byte byte/var byte/var"),
    Command(0x3E, "setwarp (bank=%d,map=%d) warp#%d (x=%d,y=%d)", "byte byte byte byte/var byte/var"),
    Command(0x3F, "setdynamicwarp %#x %#x %#x %#x %#x", "byte byte byte word word"),
    Command(0x40, "setdivewarp (bank=%d,map=%d) warp#%d (x=%d,y=%d)", "byte byte byte byte/var byte/var"),
    Command(0x41, "setholewarp (bank=%d,map=%d) warp#%d (x=%d,y=%d)", "byte byte byte byte/var byte/var"),
    Command(0x42, "getplayerpos %#x %#x", "var var"),
    CommandGetPartySize(0x43, "getpartysize", ""),
    Command(0x44, "additem %#x %#x", "word/var byte/var"),
    Command(0x45, "removeitem %#x %#x", "word/var byte/var"),
    CommandCheckItemRoom(0x46, "checkitemroom %#x %#x", "word/var byte/var"),
    CommandCheckItem(0x47, "checkitem %#x %#x", "word/var byte/var"),
    CommandCheckItemType(0x48, "checkitemtype %#x", "word/var"),
    Command(0x49, "addpcitem %#x %#x", "word/var word/var"),
    Command(0x4A, "checkpcitem %#x %#x", "word/var word/var"),
    Command(0x4B, "adddecoration %#x", "word/var"),
    Command(0x4C, "removedecoration %#x", "word/var"),
    Command(0x4D, "testdecoration %#x", "word/var"),
    Command(0x4E, "checkdecoration %#x", "word/var"),
    Command(0x4F, "applymovement %#x 0x%08x", "byte/var ptr"),
    Command(0x50, "applymovementat %#x 0x%08x", "word ptr"),
    Command(0x51, "waitmovement %#x", "byte/var"),
    Command(0x52, "waitmovementat %#x %#x %#x", "byte/var byte byte"),
    CommandHideSprite(0x53, "removesprite %#x", "byte/var"),
    CommandHideSprite(0x54, "removespriteat %#x (bank=%d,map=%d)", "byte/var byte byte"),
    CommandShowSprite(0x55, "addsprite %#x", "byte/var"),
    CommandShowSprite(0x56, "addspriteat %#x (bank=%d,map=%d)", "byte/var byte byte"),
    Command(0x57, "setspritexy %#x %#x %#x", "var var var"),
    CommandShowSprite(0x58, "showspriteat %#x (bank=%d,map=%d)", "byte/var byte byte"),
    CommandHideSprite(0x59, "hidespriteat %#x (bank=%d,map=%d)", "byte/var byte byte"),
    Command(0x5A, "faceplayer", ""),
    Command(0x5B, "turnsprite %#x dir=%d", "byte/var byte"),
    CommandTrainerBattle(0x5C, "trainerbattle %#x %#x %#x 0x%08x 0x%08x 0x%08x 0x%08x", "byte word word ptr ptr ptr ptr"),
    Command(0x5D, "repeattrainerbattle", ""),
    Command(0x5E, "gotopostbattlescript", ""),
    Command(0x5F, "gotobeatenscript", ""),
    CommandCheckTrainerFlag(0x60, "checktrainerflag %#x", "word/var"),
    CommandSetTrainerFlag(0x61, "settrainerflag %#x", "word/var"),
    CommandClearTrainerFlag(0x62, "cleartrainerflag %#x", "word/var"),
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
    CommandYesNoBox(0x6E, "yesnobox %#x %#x", "byte byte"),
    CommandMultichoice(0x6F, "multichoice %#x %#x %#x %#x", "byte byte byte byte"),
    CommandMultichoice(0x70, "multichoicedefault %#x %#x %#x %#x %#x", "byte byte byte byte byte"),
    CommandMultichoice(0x71, "multichoicegrid %#x %#x %#x %#x %#x", "byte byte byte byte byte"),
    Command(0x72, "drawbox(nop)", ""),
    Command(0x73, "erasebox (l=%d,t=%d,r=%d,b=%d)", "byte byte byte byte"),
    Command(0x74, "drawboxtext(nop)", ""),
    Command(0x75, "showpokepic %#x %#x %#x", "word/var byte byte"),
    Command(0x76, "hidepokepic", ""),
    Command(0x77, "showcontestwinner %#x", "byte"),
    Command(0x78, "braille %#x", "ptr/bank0"),
    Command(0x79, "givepokemon %#x %#x %#x %#x %#x %#x", "word/var byte word dword dword byte"),
    Command(0x7A, "giveegg species=%#x", "word/var"),
    Command(0x7B, "setpokemonmove partyIdx=%d slot=%d move=%#x", "byte byte word"),
    CommandCheckAttack(0x7C, "checkattack %#x", "word"),
    Command(0x7D, "bufferpokemon %d %#x", "buffer word/var"),
    Command(0x7E, "bufferfirstpokemon %d", "buffer"),
    Command(0x7F, "bufferpartypokemon %d %#x", "buffer word/var"),
    Command(0x80, "bufferitem %d %#x", "buffer word/var"),
    Command(0x81, "bufferdecoration %#x", "word/var"),
    Command(0x82, "bufferattack %d %#x", "buffer word/var"),
    Command(0x83, "buffernumber %d %#x", "buffer word/var"),
    Command(0x84, "bufferstd %d %#x", "buffer word/var"),
    CommandBufferString(0x85, "bufferstring %d 0x%08x", "buffer ptr"),
    Command(0x86, "pokemart 0x%08x", "ptr"),
    Command(0x87, "pokemartdeco 0x%08x", "ptr"),
    Command(0x88, "pokemartdeco2 0x%08x", "ptr"),
    Command(0x89, "playslotmachine idx=%#x", "word/var"),
    Command(0x8A, "setberrytree(nop)", ""),
    Command(0x8B, "choosecontestpkmn", ""),
    Command(0x8C, "startcontest", ""),
    Command(0x8D, "showcontestresults", ""),
    Command(0x8E, "contestlinktransfer", ""),
    Command(0x8F, "random %#x", "word/var"),
    Command(0x90, "givemoney %#x %#x", "dword byte"),
    Command(0x91, "paymoney %#x %#x", "dword byte"),
    CommandCheckMoney(0x92, "checkmoney >=%d, ignore=%d", "dword byte"),
    Command(0x93, "showmoney %#x %#x", "byte byte"),
    Command(0x94, "hidemoney %#x %#x", "byte byte"),
    Command(0x95, "updatemoney %#x %#x", "byte byte"),
    Command(0x96, "getpokenewsactive(nop)", ""),
    Command(0x97, "fadescreen mode=%#d", "byte"),
    Command(0x98, "fadescreenspeed mode=%d speed=%d", "byte byte"),
    Command(0x99, "setflashlevel %#x", "word/var"),
    Command(0x9A, "animateflash %#x", "byte"),
    Command(0x9B, "messageautoscroll 0x%08x", "ptr/bank0"),
    Command(0x9C, "doanimation %#x", "word"),
    Command(0x9D, "setanimation %#x %#x", "byte word/var"),
    Command(0x9E, "waitanimation %#x", "word"),
    Command(0x9F, "sethealingplace %#x", "word"),
    CommandCheckGender(0xA0, "checkgender", ""),
    Command(0xA1, "cry %#x %#x", "word/var word"),
    Command(0xA2, "setmaptile %#x %#x %#x %#x", "word word word word"),
    Command(0xA3, "resetweather", ""),
    Command(0xA4, "setweather %#x", "word"),
    Command(0xA5, "doweather", ""),
    Command(0xA6, "setstepcallback %#x", "byte"),
    Command(0xA7, "setmaplayoutindex %#x", "word/var"),
    Command(0xA8, "setobjectsubpriority idx=%#x (bank=%d,map=%d) priority=%d", "word/var byte byte byte"),
    Command(0xA9, "resetobjectsubpriority idx=%#x (bank=%d,map=%d)", "word/var byte byte"),
    Command(0xAA, "createvobject gid=%d vid=%d x=%#x y=%#x elev=%d dir=%d", "byte byte word/var word/var byte byte"),
    Command(0xAB, "turnvobject vid=%d dir=%d", "byte byte"),
    Command(0xAC, "opendoor %#x %#x", "word word"),
    Command(0xAD, "closedoor %#x %#x", "word word"),
    Command(0xAE, "waitdooranim", ""),
    Command(0xAF, "setdooropen %#x %#x", "word word"),
    Command(0xB0, "setdoorclosed %#x %#x", "word word"),
    Command(0xB1, "addelevmenuitem(nop)", ""),
    Command(0xB2, "showelevmenu(nop)", ""),
    CommandCheckCoins(0xB3, "checkcoins %#x", "word/var"),
    Command(0xB4, "addcoins %#x", "word/var"),
    Command(0xB5, "removecoins %#x", "word/var"),
    Command(0xB6, "setwildbattle %#x %#x %#x", "word byte word"),
    Command(0xB7, "dowildbattle", ""),
    Command(0xB8, "setvaddress 0x%08x", "ptr"),
    Command(0xB9, "vgoto 0x%08x", "ptr"), # TODO: implement vfuncs
    Command(0xBA, "vcall 0x%08x", "ptr"),
    Command(0xBB, "vgotoif %#x 0x%08x", "byte ptr"),
    Command(0xBC, "vcallif %#x 0x%08x", "byte ptr"),
    Command(0xBD, "vmessage 0x%08x", "ptr"),
    Command(0xBE, "vbuffermessage 0x%08x", "ptr"),
    Command(0xBF, "vbufferstring idx=%d 0x%08x", "byte ptr"),
    Command(0xC0, "showcoinsbox x=%d y=%d", "byte byte"),
    Command(0xC1, "hidecoinsbox x=%d y=%d", "byte byte"),
    Command(0xC2, "updatecoinsbox %#x %#x", "byte byte"),
    Command(0xC3, "incrementgamestat %d", "hidden"),
    Command(0xC4, "setescapewarp (bank=%d,map=%d) warp#%d (x=%d,y=%d)", "byte byte byte byte/var byte/var"),
    Command(0xC5, "waitcry", ""),
    Command(0xC6, "bufferboxname %d %#x", "buffer word/var"),
    Command(0xC7, "textcolor %#x", "byte"),
    Command(0xC8, "loadhelp %#x", "ptr/bank0"),
    Command(0xC9, "unloadhelp", ""),
    Command(0xCA, "signmsg", ""),
    Command(0xCB, "normalmsg", ""),
    Command(0xCC, "comparehiddenvar %d %#x", "hidden dword"),
    Command(0xCD, "setobedience %#x", "word"),
    Command(0xCE, "checkobedience %#x", "word/var"),
    Command(0xCF, "executeram", ""),
    Command(0xD0, "setworldmapflag %#x", "flag/var"),
    Command(0xD1, "warpteleport2 (bank=%d,map=%d) warp#%d (x=%d,y=%d)", "byte byte byte byte/var byte/var"),
    Command(0xD2, "setcatchlocation %#x %#x", "word/var byte"),
    Command(0xD3, "braille2 %#x", "ptr/bank0"),
    Command(0xD4, "bufferitems %d %#x %#x", "buffer word/var word/var"),
    Command(0xD5, "tableend(nop)", "")
]
