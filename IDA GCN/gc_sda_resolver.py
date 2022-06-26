import idaapi
import idc

__version__ = "1.0"
__license__ = "MIT"
__status__ = "developpement"


# For IDA 6.8 - tested on a friend computer
# Translated from http://hitmen.c02.at/files/releases/gc/ppc-sdabase-fix.idc
# Credits to Hitmen team


RE_ADDR = re.compile("^0x[a-fA-F0-9]{8}\((__SDA_BASE__|__SDA2_BASE__)\)$")
RE_OFFSET = re.compile("^-*0x[a-fA-F0-9]{1,4}\((r2|r13)\)$")


def make_sda_relative_opcode(ea, realaddr, sda_base, opreg1):
    global RE_ADDR
    global RE_OFFSET

    # Check if insn has already been processed
    opnd1 = idc.GetOpnd(ea, 1)
    if RE_ADDR.match(opnd1):
        return
    elif not RE_OFFSET.match(opnd1):
        print("Error - Unknow format at ea {0:08x}:{1}".format(ea, opnd1))

    # add data xref (from, to, drefType = Text)
    # doing this at first break sometimes .align collapsed areas discarding new dummy name
    idc.add_dref(ea, realaddr, idc.dr_T | XREF_USER)

    # get name as displayed on the screen
    name = idc.Name(realaddr)
    if name == "":
        idaapi.set_dummy_name(idaapi.BADADDR, realaddr)
        name = idc.Name(realaddr)

    output = "{0}({1})".format(
        name if name != "" else hex(realaddr)[:-1],
        "__SDA2_BASE__" if opreg1 == 2 else "__SDA_BASE__")

    # Set manually second operand with output
    idc.OpAlt(ea, 1, output)


def make_sda_imm_opcode(ea, realaddr, sda_base):
    global RE_ADDR
    global RE_OFFSET

    # Check if insn has already been processed
    opnd2 = idc.GetOpnd(ea, 2)
    if RE_ADDR.match(opnd2):
        return
    elif not RE_OFFSET.match(opnd2):
        print("Error - Unknow format at ea {0:08x}:{1}".format(ea, opnd2))

    # add data xref (from, to, drefType = Text)
    # doing this at first break sometimes .align collapsed areas discarding new dummy name
    idc.add_dref(ea, realaddr, idc.dr_T | XREF_USER)

    name = idc.Name(ea, realaddr)
    if name == "":
        idaapi.set_dummy_name(idaapi.BADADDR, realaddr)
        name = idc.Name(realaddr)

    # Set manually third operand with output
    idc.OpAlt(ea, 2, name if name != "" else hex(realaddr)[:-1])


def do_function(start_ea, sda_base, sda2_base):
    func_end_ea = idc.FindFuncEnd(start_ea)

    # aaaa Have to check if splited func chunks are correctly handled
    ea = idc.NextHead(start_ea, func_end_ea)

    while ea <= func_end_ea and ea != idaapi.BADADDR:
        # Get mnem str repr (may be different of the screen) or ""
        mnem  = idc.GetMnem(ea)

        if mnem in ["lbz", "lha", "lhz", "lwz", "lfd", "lfs", "lmw", "stb", "sth", "stmw", "stw"]:
            # Get second operand value
            opval1 = idc.GetOperandValue(ea, 1)
            opreg0 = (idc.Dword(ea) >> 21) & 0x1f
            opreg1 = (idc.Dword(ea) >> 16) & 0x1f
            if opreg0 != 13 and opreg1 == 13: # sda_base
                realaddr = (sda_base + opval1) & 0xffffffff
                make_sda_relative_opcode(ea, realaddr, sda_base, opreg1)
            elif opreg0 != 2 and opreg1 == 2: # sda2_base
                realaddr = (sda2_base + opval1) & 0xffffffff
                make_sda_relative_opcode(ea, realaddr, sda2_base, opreg1)
        elif mnem == "subi":
            opval2 = idc.GetOperandValue(ea, 2)
            opreg0 = (idc.Dword(ea) >> 21) & 0x1f
            opreg1 = (idc.Dword(ea) >> 16) & 0x1f
            if opreg0 != 13 and opreg1 == 13: # sda_base
                realaddr = (sda_base - opval2) & 0xffffffff
                make_sda_imm_opcode(ea, realaddr, sda_base)
            elif opreg0 !=2 and opreg1 == 2: # sda2_base
                realaddr = (sda2_base - opval2) & 0xffffffff
                make_sda_imm_opcode(ea, realaddr, sda2_base)
        # Get next instr or data defined
        ea = idc.NextHead(ea, func_end_ea)


def resolve_sda():
    print("Waiting end of autoanalysis")
    idc.Wait()

    start_ea = idc.NextFunction(0)
    current_ea = start_ea
    end_ea = 0x81700000

    __SDA_BASE__  = idaapi.get_segm_by_name(".sdata").startEA
    __SDA2_BASE__ = idaapi.get_segm_by_name(".sdata2").startEA

    while current_ea != idaapi.BADADDR:
        do_function(current_ea, __SDA_BASE__, __SDA2_BASE__)
        current_ea = idc.NextFunction(current_ea)

    print("Start analysis.")
    idc.AnalyzeArea(start_ea, end_ea)

    print("All done.")


resolve_sda()
