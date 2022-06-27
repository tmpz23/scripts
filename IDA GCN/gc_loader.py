import ctypes
import idaapi
import idautils
import idc
import os
import struct


__version__ = "1.9"
__license__ = "The GNU General Public License (GPL) Version 2, June 1991"
__status__ = "developpement"


# https://forum.tuts4you.com/files/file/2222-rel-dol-loader/ (cpp)
# https://github.com/P1kachu/idapython-dol-loader/blob/master/gc_wii_dol_loader.py (rewrited in python)
# tested on a friend computer who buyed IDA 6.8 on windows


DOL_HEADER_SIZE = 0x100
DOL_FORMAT_NAME = "Nintendo GameCube dol"
RAW_FORMAT_NAME = "Nintendo GameCube dol MRAM dump"
MAX_CODE_SECTION = 7
MAX_DATA_SECTION = 11


class DolHeader(ctypes.BigEndianStructure):
    _fields_ = [
        ("text_offsets", ctypes.c_uint * MAX_CODE_SECTION),
        ("data_offsets", ctypes.c_uint * MAX_DATA_SECTION),
        ("text_addresses", ctypes.c_uint * MAX_CODE_SECTION),
        ("data_addresses", ctypes.c_uint * MAX_DATA_SECTION),
        ("text_sizes", ctypes.c_uint * MAX_CODE_SECTION),
        ("data_sizes", ctypes.c_uint * MAX_DATA_SECTION),
        ("bss_address", ctypes.c_uint),
        ("bss_size", ctypes.c_uint),
        ("entry_point", ctypes.c_uint)]


def get_dol_header(file_input):
    file_input.seek(0)
    header = DolHeader()
    string = file_input.read(DOL_HEADER_SIZE)
    fit = min(len(string), ctypes.sizeof(header))
    ctypes.memmove(ctypes.addressof(header), string, fit)
    return header


class AskSectionsInfoForm(Form):
    def __init__(self, fmt):
        inputs = {
            'STACK_ADDRESS':            Form.NumericInput(tp=Form.FT_HEX),
            'STACK_SIZE':               Form.NumericInput(tp=Form.FT_HEX),
            'SDA_BASE':                 Form.NumericInput(tp=Form.FT_HEX),
            'SDA2_BASE':                Form.NumericInput(tp=Form.FT_HEX),
            'ARENA_START_ADDRESS':      Form.NumericInput(tp=Form.FT_HEX),
            'ARENA_END_ADDRESS':        Form.NumericInput(tp=Form.FT_HEX)}

        content = "STARTITEM 0\n" + \
            "BUTTON CANCEL NONE\n" + \
            "Loader configuration.\n\n"

        if fmt == RAW_FORMAT_NAME:
            inputs['DOL_FILENAME'] = Form.FileInput(open=True, swidth=54)
            content += "<#Required - dol file:{DOL_FILENAME}>\n"
        
        content += "<Stack address      :{STACK_ADDRESS}> <Stack size                :{STACK_SIZE}>\n" + \
            "<__SDA_BASE__ (r13) address:{SDA_BASE}> <__SDA2_BASE__ (r2) address:{SDA2_BASE}>\n" + \
            "<ArenaStart address        :{ARENA_START_ADDRESS}> <ArenaEnd address          :{ARENA_END_ADDRESS}>\n" + \
            "Start Dolphin Emulator in debug mode and enable full logs on the logs options.\n" + \
            "ArenaStart & ArenaEnd -> Arena in dolphin OS logs during GameCube init. After __init_registers:\n" + \
            "__SDA_BASE__ = R13;\n" + \
            "__SDA2_BASE__ = R2;\n" + \
            "Stack address = R1;\n" + \
            "Default Stack size = 0x10000 bytes."

        Form.__init__(self, content, inputs)

        # Compile (in order to populate the controls)
        self.Compile()

        self.STACK_SIZE.value = 0x10000
        if fmt == RAW_FORMAT_NAME:
            self.DOL_FILENAME.value = os.getcwd()


class SectionsInfos:
    DOL_FILENAME = None
    STACK_ADDRESS = None
    STACK_SIZE = None
    SDA_BASE = None
    SDA2_BASE = None
    ARENA_START_ADDRESS = None
    ARENA_END_ADDRESS = None
    ARENA_LO = None
    ARENA_HI = None
    def __init__(self, form):
        if hasattr(form, "DOL_FILENAME"):
            self.DOL_FILENAME = form.DOL_FILENAME.value
        self.STACK_ADDRESS = form.STACK_ADDRESS.value & 0xFFFFFFFF
        self.STACK_SIZE = form.STACK_SIZE.value & 0xFFFFFFFF
        self.SDA_BASE = form.SDA_BASE.value & 0xFFFFFFFF
        self.SDA2_BASE = form.SDA2_BASE.value & 0xFFFFFFFF
        self.ARENA_START_ADDRESS = form.ARENA_START_ADDRESS.value & 0xFFFFFFFF
        self.ARENA_END_ADDRESS = form.ARENA_END_ADDRESS.value & 0xFFFFFFFF
        self.ARENA_LO = 0
        self.ARENA_HI = 0
    def is_stack_valid(self):
        return 0x80001300 < self.STACK_ADDRESS <= 0x81800000 and self.STACK_SIZE > 0
    def is_arena_valid(self):
        return 0x80001300 < self.ARENA_START_ADDRESS <= 0x81800000 and \
            self.ARENA_START_ADDRESS < self.ARENA_END_ADDRESS <= 0x81800000
    def is_allocated_arenas_valids(self):
        return self.is_arena_valid() and self.ARENA_START_ADDRESS < self.ARENA_LO <= self.ARENA_HI < self.ARENA_END_ADDRESS
    def is_sda_valid(self):  return 0x80003100 <= self.SDA_BASE <= 0x81800000
    def is_sda2_valid(self): return 0x80003100 <= self.SDA2_BASE <= 0x81800000


#################################################################
# Helpers
#################################################################
def remove_intervals_from_interval(interval, intervals_to_remove):
    """
    Get non-overlapping intervals from interval by removing intervals_to_remove
    intervals_to_remove has to be sorted by left val
    return [[a,b], ...] or None
    """
    interval = interval[:]
    result_intervals = []
    for interval_to_remove in intervals_to_remove:
        if interval_to_remove[1] < interval[0]: continue # end before
        if interval_to_remove[0] > interval[1]: break # begin after

        if interval_to_remove[0] <= interval[0]: # begin before
            if interval_to_remove[1] >= interval[1]: # total overlap
                return result_intervals
            interval[0] = interval_to_remove[1] # begin truncate
        elif interval_to_remove[1] >= interval[1]: # end truncate
            interval[1] = interval_to_remove[0]
            break
        else: # middle truncate
            result_intervals.append( [interval[0], interval_to_remove[0]] )
            interval[0] = interval_to_remove[1]

    return result_intervals + [interval]


#################################################################
# Creation and configurations
#################################################################
def configure_compiler():
    idaapi.set_processor_type("PPC", SETPROC_ALL|SETPROC_FATAL)

    # Clean includes dirs
    idaapi.set_c_header_path("")

    # Set Compiler defaults GNU C++
    compiler_info = idc.GetLongPrm(idc.INF_COMPILER) # Get idaapi.compiler_info_t
    compiler_info.id = COMP_GNU           # Compiler ID / could also be VC++

    # Memory model & calling convention
    # cedecl calling convention; (near, near); ptr_s = (4, 6); args = GP and FP
    compiler_info.cm = idaapi.CM_CC_CDECL | idaapi.C_PC_FLAT | idaapi.ARGREGS_GP_ONLY
    compiler_info.defalign = 2            # default align
    compiler_info.size_i = 4              # sizeof(int)
    compiler_info.size_s = 2              # sizeof(short)
    compiler_info.size_b = 4              # sizeof(bool)
    compiler_info.size_l = 4              # sizeof(long)
    compiler_info.size_e = 4              # sizeof(enum)
    compiler_info.size_ll = 8             # sizeof(longlong)
    idc.SetLongPrm(idc.INF_COMPILER, compiler_info)


def create_dolphin_os_globals_vars():
    'https://www.gc-forever.com/yagcd/chap4.html#sec4.2.1.1'

    # DVD Disc ID
    MakeNameEx(0x80000000, "BI_GAMECODE", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80000000, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x80000000, "Boot Info - DVD Disc ID: Gamecode.")
    MakeStr(0x80000000, 0x80000004)

    MakeNameEx(0x80000004, "BI_COMPANY", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80000004, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0x80000004, "Boot Info - DVD Disc ID: Company.")
    MakeStr(0x80000004, 0x80000006)

    MakeNameEx(0x80000006, "BI_DISCID", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80000006, idaapi.FF_BYTE, 1, 0)
    MakeRptCmt(0x80000006, "Boot Info - DVD Disc ID: Disc ID.")

    MakeNameEx(0x80000007, "BI_DVDVERSION", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80000007, idaapi.FF_BYTE, 1, 0)
    MakeRptCmt(0x80000007, "Boot Info - DVD Disc ID: Version.")
    MakeStr(0x80000004, 0x80000006)

    MakeNameEx(0x80000008, "BI_STREAMING", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80000008, idaapi.FF_BYTE, 1, 0)
    MakeRptCmt(0x80000008, "Boot Info - DVD Disc ID: Streaming.")

    MakeNameEx(0x80000009, "BI_STREAMBUFFSIZE", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80000009, idaapi.FF_BYTE, 1, 0)
    MakeRptCmt(0x80000009, "Boot Info - DVD Disc ID: StreamBuffSize.")

    # System Info
    MakeNameEx(0x8000001c, "BI_DVDMAGIC", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x8000001c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x8000001c, "Boot Info - System Info: DVD Magic Number.")

    MakeNameEx(0x80000020, "BI_MAGIC", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80000020, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x80000020, "Boot Info - System Info: Magic word (how did the console boot?).")

    MakeNameEx(0x80000024, "BI_SYSTEMVERSION", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80000024, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x80000024, "Boot Info - System Info: Version (usually set to 1 by apploader).")

    MakeNameEx(0x80000028, "BI_PHYMEMSIZE", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80000028, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x80000028, "Boot Info - System Info: physical Memory Size.")

    MakeNameEx(0x8000002c, "BI_CONSOLETYPE", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x8000002c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x8000002c, "Boot Info - System Info: Console type.")

    MakeNameEx(0x80000030, "BI_ARENALO", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80000030, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x80000030, "Boot Info - System Info: ArenaLo.")

    MakeNameEx(0x80000034, "BI_ARENAHI", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80000034, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x80000034, "Boot Info - System Info: ArenaHi.")

    MakeNameEx(0x80000038, "BI_FSTADDR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80000038, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x80000038, "Boot Info - System Info: FST Location in ram.")

    MakeNameEx(0x8000003c, "BI_FSTMAXLEN", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x8000003c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x8000003c, "Boot Info - System Info: FST Max Length.")

    # Debugger Info
    MakeNameEx(0x80000040, "BI_ISDEBUGGERPRESENT", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80000040, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x80000040, "Boot Info - Debugger Info: flag for \"debugger present\" (used by __OSIsDebuggerPresent).")

    MakeNameEx(0x80000044, "BI_DEBUGGEREXCEPTIONMASK", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80000044, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x80000044, "Boot Info - Debugger Info: Debugger Exception mask Bitmap, set to 0 at sdk lib start.")

    MakeNameEx(0x80000048, "BI_EXCEPTIONHOOKADDR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80000048, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x80000048, "Boot Info - Debugger Info: Exception hook destination (physical address).")

    MakeNameEx(0x8000004c, "BI_LRRETURNFROMEXCEPTION", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x8000004c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x8000004c, "Boot Info - Debugger Info: Temp for LR, Return from exception address (to return from hook).")

    # Debugger Hook
    MakeNameEx(0x80000060, "BI_debugger_hook", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeFunction(0x80000060, 0x80000084)

    # Dolphin OS Globals
    MakeNameEx(0x800000c0, "BI_CURRENTOSCONTEXTPHY", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800000c0, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800000c0, "Dolphin OS Globals: Current OS context (physical address).")

    MakeNameEx(0x800000c4, "BI_PREVIOUSOSINTERRUPTMASK", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800000c4, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800000c4, "Dolphin OS Globals: Previous OS interrupt mask.")

    MakeNameEx(0x800000c8, "BI_CURRENTOSINTERRUPTMASK", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800000c8, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800000c8, "Dolphin OS Globals: current OS interrupt mask.")

    MakeNameEx(0x800000cc, "BI_TVMODE", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800000cc, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800000cc, "Dolphin OS Globals: TV Mode.")

    MakeNameEx(0x800000d0, "BI_ARAMSIZE", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800000d0, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800000d0, "Dolphin OS Globals: ARAM size (internal+expansion) in bytes. set by ARAM driver, usually 16mb..")

    MakeNameEx(0x800000d4, "BI_CURRENTOSCONTEXTADDR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800000d4, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800000d4, "Dolphin OS Globals: current OS Context (logical address).")

    MakeNameEx(0x800000d8, "BI_DEFAULTOSTHREAD", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800000d8, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800000d8, "Dolphin OS Globals: default OS thread (logical address).")

    MakeNameEx(0x800000dc, "BI_HEADTHREAD", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800000dc, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800000dc, "Dolphin OS Globals: active Thread queue, head thread (logical address).")

    MakeNameEx(0x800000e0, "BI_TAILTHREAD", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800000e0, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800000e0, "Dolphin OS Globals: active Thread queue, tail thread (logical address).")

    MakeNameEx(0x800000e4, "BI_CURRENTOSTHREAD", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800000e4, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800000e4, "Dolphin OS Globals: Current OS thread.")

    MakeNameEx(0x800000e8, "BI_DEBUGMONITORSIZE", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800000e8, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800000e8, "Dolphin OS Globals: Debug monitor size (in bytes).")

    MakeNameEx(0x800000ec, "BI_DEBUGMONITORADDR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800000ec, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800000ec, "Dolphin OS Globals: Debug monitor location (usually at the top of main memory).")

    MakeNameEx(0x800000f0, "BI_CONSOLESIMULATEDMEMSIZE", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800000f0, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800000f0, "Dolphin OS Globals: Console Simulated Memory Size, 0x01800000 (usually same as physical memory size).")

    MakeNameEx(0x800000f4, "BI_DVDBI2ADDR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800000f4, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800000f4, "Dolphin OS Globals: DVD BI2 location in main memory (size of BI2 is 0x2000 bytes).")

    MakeNameEx(0x800000f8, "BI_BUSCLOCKSPEED", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800000f8, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800000f8, "Dolphin OS Globals: Bus Clock Speed, 162 MHz (=0x09a7ec80, 162000000).")

    MakeNameEx(0x800000fc, "BI_CPUCLOCKSPEED", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800000fc, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800000fc, "Dolphin OS Globals: CPU Clock Speed, 486 MHz (=0x1cf7c580, 486000000).")

    # Exception Handlers
    MakeNameEx(0x80000100, "SYS_INT_Reset", idc.SN_CHECK | idaapi.SN_PUBLIC) # System Reset Interrupt
    MakeFunction(0x80000100)
    SetFunctionCmt(0x80000100, "System Reset Interrupt.", 0)
    
    MakeNameEx(0x80000200, "SYS_INT_MachineCheck", idc.SN_CHECK | idaapi.SN_PUBLIC) # Machine Check Interrupt
    MakeFunction(0x80000200)
    SetFunctionCmt(0x80000200, "Machine Check Interrupt.", 0)
    
    MakeNameEx(0x80000300, "SYS_INT_DSI", idc.SN_CHECK | idaapi.SN_PUBLIC) # DSI Interrupt
    MakeFunction(0x80000300)
    SetFunctionCmt(0x80000300, "DSI Interrupt.", 0)
    
    MakeNameEx(0x80000400, "SYS_INT_ISI", idc.SN_CHECK | idaapi.SN_PUBLIC) # ISI Interrupt
    MakeFunction(0x80000400)
    SetFunctionCmt(0x80000400, "ISI Interrupt.", 0)
    
    MakeNameEx(0x80000500, "SYS_INT_External", idc.SN_CHECK | idaapi.SN_PUBLIC) # External Interrupt
    MakeFunction(0x80000500)
    SetFunctionCmt(0x80000500, "External Interrupt.", 0)
    
    MakeNameEx(0x80000600, "SYS_INT_Alignment", idc.SN_CHECK | idaapi.SN_PUBLIC) # Alignment Interrupt
    MakeFunction(0x80000600)
    SetFunctionCmt(0x80000600, "Alignment Interrupt.", 0)
    
    MakeNameEx(0x80000700, "SYS_INT_Program", idc.SN_CHECK | idaapi.SN_PUBLIC) # Program Interrupt
    MakeFunction(0x80000700)
    SetFunctionCmt(0x80000700, "Program Interrupt.", 0)
    
    MakeNameEx(0x80000800, "SYS_INT_FPUnavailable", idc.SN_CHECK | idaapi.SN_PUBLIC) # FP unavailable Interrupt
    MakeFunction(0x80000800)
    SetFunctionCmt(0x80000800, "FP unavailable Interrupt.", 0)
    
    MakeNameEx(0x80000900, "SYS_INT_Decrementer", idc.SN_CHECK | idaapi.SN_PUBLIC) # Decrementer Interrupt
    MakeFunction(0x80000900)
    SetFunctionCmt(0x80000900, "Decrementer Interrupt.", 0)
    
    MakeNameEx(0x80000C00, "SYS_INT_Syscall", idc.SN_CHECK | idaapi.SN_PUBLIC) # System Call Interrupt
    MakeFunction(0x80000C00)
    SetFunctionCmt(0x80000C00, "System Call Interrupt.", 0)
    
    MakeNameEx(0x80000d00, "SYS_INT_Trace", idc.SN_CHECK | idaapi.SN_PUBLIC) # Trace Interrupt
    MakeFunction(0x80000d00)
    SetFunctionCmt(0x80000d00, "Trace Interrupt.", 0)
    
    MakeNameEx(0x80000f00, "SYS_INT_Perfmon", idc.SN_CHECK | idaapi.SN_PUBLIC) # Performance Monitor Interrupt
    MakeFunction(0x80000f00)
    SetFunctionCmt(0x80000f00, "Performance Monitor Interrupt.", 0)
    
    MakeNameEx(0x80001300, "SYS_INT_IABR", idc.SN_CHECK | idaapi.SN_PUBLIC) # IABR Interrupt
    MakeFunction(0x80001300)
    SetFunctionCmt(0x80001300, "IABR Interrupt.", 0)
    
    MakeNameEx(0x80001700, "SYS_INT_Thermal", idc.SN_CHECK | idaapi.SN_PUBLIC) # Thermal Interrupt
    MakeFunction(0x80001700)
    SetFunctionCmt(0x80001700, "Thermal Interrupt.", 0)

    # Dolphin-OS globals
    MakeNameEx(0x80003000, "DOG_EXCEPTIONHANDLERVECTORS", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80003000, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x80003000, "Dolphin OS Globals: exception handler vectors (from sdk libs & ipl).")
    MakeArray(0x80003000, 15)

    MakeNameEx(0x80003040, "DOG_EXTERNALINTERRUPTHANDLERVECTOR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x80003040, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x80003040, "Dolphin OS Globals: external interrupt handler vectors (from sdk libs & ipl).")
    MakeArray(0x80003040, 25)

    MakeNameEx(0x800030c0, "DOG_UNKN0", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030c0, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800030c0, "Dolphin OS Globals: ?.")

    MakeNameEx(0x800030c4, "DOG_UNKN1", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030c4, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800030c4, "Dolphin OS Globals: ?.")

    MakeNameEx(0x800030c8, "DOG_FIRSTMODULEHEADERADDR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030c8, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800030c8, "Dolphin OS Globals: First Module Header Pointer in Module Queue.")

    MakeNameEx(0x800030cc, "DOG_LASTMODULEHEADERADDR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030cc, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800030cc, "Dolphin OS Globals: Last Module Header Pointer in Module Queue.")

    MakeNameEx(0x800030d0, "DOG_MODULESTRINGTABLEADDR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030d0, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800030d0, "Dolphin OS Globals: Module String Table Pointer.")

    MakeNameEx(0x800030d4, "DOG_DOLSIZE", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030d4, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800030d4, "Dolphin OS Globals: DOL size (total size of text/data sections), in bytes (*1).")

    MakeNameEx(0x800030d8, "DOG_OSSYSTEMTIME", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030d8, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800030d8, "Dolphin OS Globals: OS system time (set, when console is powered up).")

    MakeNameEx(0x800030dc, "DOG_UNKN2", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030dc, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800030dc, "Dolphin OS Globals: ?.")

    MakeNameEx(0x800030e0, "DOG_UNKN3", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030e0, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800030e0, "Dolphin OS Globals: ? (6=production pads ?).")

    MakeNameEx(0x800030e4, "DOG_UNKN4", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030e4, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0x800030e4, "Dolphin OS Globals: ?.")

    MakeNameEx(0x800030e6, "DOG_UNKN5", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030e6, idaapi.FF_BYTE, 1, 0)
    MakeRptCmt(0x800030e6, "Dolphin OS Globals: ?.")

    MakeNameEx(0x800030e7, "DOG_UNKN6", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030e7, idaapi.FF_BYTE, 1, 0)
    MakeRptCmt(0x800030e7, "Dolphin OS Globals: ?.")

    MakeNameEx(0x800030e8, "DOG_UNKN7", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030e8, idaapi.FF_BYTE, 1, 0)
    MakeRptCmt(0x800030e8, "Dolphin OS Globals: set by OsInit() (debugger stuff?).")

    MakeNameEx(0x800030e9, "DOG_UNKN8", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030e9, idaapi.FF_BYTE, 1, 0)
    MakeRptCmt(0x800030e9, "Dolphin OS Globals: set by OsInit() (debugger stuff?).")

    MakeNameEx(0x800030ea, "DOG_UNKN9", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030ea, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0x800030ea, "Dolphin OS Globals: ?.")

    MakeNameEx(0x800030ec, "DOG_UNKN10", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030ec, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800030ec, "Dolphin OS Globals: ?.")

    MakeNameEx(0x800030f0, "DOG_UNKN11", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030f0, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0x800030f0, "Dolphin OS Globals: ?.")

    MakeNameEx(0x800030f2, "DOG_BOOTSTATUS", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030f2, idaapi.FF_BYTE, 1, 0)
    MakeRptCmt(0x800030f2, "Dolphin OS Globals: Boot status.")

    MakeNameEx(0x800030f3, "DOG_UNKN12", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030f3, idaapi.FF_BYTE, 1, 0)
    MakeRptCmt(0x800030f3, "Dolphin OS Globals: ?.")

    MakeNameEx(0x800030f4, "DOG_UNKN13", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030f4, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800030f4, "Dolphin OS Globals: ?.")

    MakeNameEx(0x800030f8, "DOG_UNKN14", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030f8, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800030f8, "Dolphin OS Globals: ?.")

    MakeNameEx(0x800030fc, "DOG_UNKN15", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0x800030fc, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0x800030fc, "Dolphin OS Globals: ?.")


def create_hardware_registers_sections():
    """
    Create hardware registers as seen Here:
    * https://github.com/Cuyler36/Ghidra-GameCube-Loader/blob/master/src/main/java/gamecubeloader/common/SystemMemorySections.java
    * https://www.gc-forever.com/yagcd/chap4.html#sec4
    """
    # Command Processor Register
    AddSegEx(0xCC000000, 0xCC000080, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
    RenameSeg(0xCC000000, "CP")
    SetSegmentType(0xCC000000, SEG_BSS)

    MakeNameEx(0xCC000000, "CP.SR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000000, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000000, "Command Processor: SR - Status Register (R/W).")

    MakeNameEx(0xCC000002, "CP.CR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000002, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000002, "Command Processor: CR - Control Register (R/W).")

    MakeNameEx(0xCC000004, "CP.CLEAR_REG", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000004, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000004, "Command Processor: Clear Register (R).")

    MakeNameEx(0xCC00000e, "CP.TOKEN_REG", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00000e, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00000e, "Command Processor: token register (R/W).")

    MakeNameEx(0xCC000010, "CP.bounding_box_left", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000010, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000010, "Command Processor: bounding box - left (R/W).")

    MakeNameEx(0xCC000012, "CP.bounding_box_right", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000012, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000012, "Command Processor: bounding box - right (R/W).")

    MakeNameEx(0xCC000014, "CP.bounding_box_top", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000014, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000014, "Command Processor: bounding box - top (R/W).")

    MakeNameEx(0xCC000016, "CP.bounding_box_bottom", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000016, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000016, "Command Processor: bounding box - bottom (R/W).")

    MakeNameEx(0xCC000020, "CP.cp_FIFO_base_lo", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000020, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000020, "Command Processor: cp FIFO base lo (R/W).")

    MakeNameEx(0xCC000022, "CP.cp_FIFO_base_hi", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000022, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000022, "Command Processor: cp FIFO base hi (R/W).")

    MakeNameEx(0xCC000024, "CP.cp_FIFO_end_lo", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000024, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000024, "Command Processor: cp FIFO end lo (R/W).")

    MakeNameEx(0xCC000026, "CP.cp_FIFO_end_hi", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000026, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000026, "Command Processor: cp FIFO end hi (R/W).")

    MakeNameEx(0xCC000028, "CP.cp_FIFO_high_watermark_lo", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000028, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000028, "Command Processor: cp FIFO high watermark lo (R/W). (The low and high watermark control the assertion of the CP interrupt.)")

    MakeNameEx(0xCC00002a, "CP.cp_FIFO_high_watermark_hi", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00002a, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00002a, "Command Processor: cp FIFO high watermark hi (R/W). (The low and high watermark control the assertion of the CP interrupt.)")

    MakeNameEx(0xCC00002c, "CP.cp_FIFO_low_watermark_lo", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00002c, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00002c, "Command Processor: cp FIFO low watermark lo (R/W). (The low and high watermark control the assertion of the CP interrupt.)")

    MakeNameEx(0xCC00002e, "CP.cp_FIFO_low_watermark_hi", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00002e, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00002e, "Command Processor: cp FIFO low watermark hi (R/W). (The low and high watermark control the assertion of the CP interrupt.)")

    MakeNameEx(0xCC000030, "CP.cp FIFO_read_write_distance_lo", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000030, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000030, "Command Processor: cp FIFO read/write distance lo (R/W).")

    MakeNameEx(0xCC000032, "CP.cp_FIFO_read_write_distance_hi", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000032, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000032, "Command Processor: cp FIFO read/write distance hi (R/W).")

    MakeNameEx(0xCC000034, "CP.cp_FIFO_write_pointer_lo", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000034, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000034, "Command Processor: cp FIFO write pointer lo (R/W).")

    MakeNameEx(0xCC000036, "CP.cp_FIFO_write_pointer_hi", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000036, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000036, "Command Processor: cp FIFO write pointer hi (R/W).")

    MakeNameEx(0xCC000038, "CP.cp_FIFO_read_pointer_lo", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC000038, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC000038, "Command Processor: cp FIFO read pointer lo (R/W).")

    MakeNameEx(0xCC00003a, "CP.cp_FIFO_read_pointer_hi", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00003a, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00003a, "Command Processor: cp FIFO read pointer hi (R/W).")

    MakeNameEx(0xCC00003c, "CP.cp_FIFO_bp_lo", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00003c, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00003c, "Command Processor: cp FIFO bp lo (R/W).")

    MakeNameEx(0xCC00003e, "CP.cp_FIFO_bp_hi", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00003e, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00003e, "Command Processor: cp FIFO bp hi (R/W).")

    # Pixel Engine Register
    AddSegEx(0xCC001000, 0xCC001100, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
    RenameSeg(0xCC001000, "PE")
    SetSegmentType(0xCC001000, SEG_BSS)

    MakeNameEx(0xCC001000, "PE.Z_configuration", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC001000, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC001000, "Command Processor: Z configuration (R/W).")

    MakeNameEx(0xCC001002, "PE.Alpha_configuration", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC001002, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC001002, "Command Processor: Alpha configuration (R/W).")

    MakeNameEx(0xCC001004, "PE.destination_alpha", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC001004, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC001004, "Command Processor: destination alpha (R/W).")

    MakeNameEx(0xCC001006, "PE.Alpha_Mode", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC001006, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC001006, "Command Processor: Alpha Mode (R/W).")

    MakeNameEx(0xCC001008, "PE.Alpha_Read", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC001008, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC001008, "Command Processor: Alpha Read (?) (R/W).")

    MakeNameEx(0xCC00100a, "PE.INT_STATUS_REG", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00100a, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00100a, "Command Processor: Interrupt Status Register (R/W).")

    MakeNameEx(0xCC00100e, "PE.TOKEN", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00100e, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00100e, "Command Processor: PE Token ? (R/W). PE Token (asserted from last PE Token Interrupt).")

    # Video Interface Register
    AddSegEx(0xCC002000, 0xCC002100, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
    RenameSeg(0xCC002000, "VI")
    SetSegmentType(0xCC002000, SEG_BSS)

    MakeNameEx(0xCC002000, "VI.VTR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002000, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC002000, "Video Interface: VTR - Vertical Timing Register (R/W).")

    MakeNameEx(0xCC002002, "VI.DCR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002002, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC002002, "Video Interface: DCR - Display Configuration Register (R/W).")

    MakeNameEx(0xCC002004, "VI.HTR0", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002004, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002004, "Video Interface: HTR0 - Horizontal Timing 0 (R/W).")

    MakeNameEx(0xCC002008, "VI.HTR1", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002008, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002008, "Video Interface: HTR1 - Horizontal Timing 1 (R/W).")

    MakeNameEx(0xCC00200c, "VI.VTO", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00200c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00200c, "Video Interface: VTO - Odd Field Vertical Timing Register (R/W).")

    MakeNameEx(0xCC002010, "VI.VTE", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002010, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002010, "Video Interface: VTE - Even Field Vertical Timing Register (R/W).")

    MakeNameEx(0xCC002014, "VI.BBEI", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002014, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002014, "Video Interface: BBEI - Odd Field Burst Blanking Interval Register (R/W).")

    MakeNameEx(0xCC002018, "VI.BBOI", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002018, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002018, "Video Interface: BBOI - Even Field Burst Blanking Interval Register (R/W).")

    MakeNameEx(0xCC00201c, "VI.TFBL", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00201c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00201c, "Video Interface: TFBL - Top Field Base Register (L) (External Framebuffer Half 1) (R/W).")

    MakeNameEx(0xCC002020, "VI.TFBR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002020, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002020, "Video Interface: TFBR - Top Field Base Register (R) (Only valid in 3D Mode) (R/W).")

    MakeNameEx(0xCC002024, "VI.BFBL", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002024, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002024, "Video Interface: BFBL - Bottom Field Base Register (L) (External Framebuffer Half 2) (R/W).")

    MakeNameEx(0xCC002028, "VI.BFBR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002028, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002028, "Video Interface: BFBR - Bottom Field Base Register (R) (Only valid in 3D Mode) (R/W).")

    MakeNameEx(0xCC00202c, "VI.DPV", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00202c, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00202c, "Video Interface: DPV - current vertical Position (R).")

    MakeNameEx(0xCC00202e, "VI.DPH", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00202e, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00202e, "Video Interface: DPH - current horizontal Position (?) (R).")

    MakeNameEx(0xCC002030, "VI.DI0", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002030, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002030, "Video Interface: DI0 - Display Interrupt 0 (R/W).")

    MakeNameEx(0xCC002034, "VI.DI1", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002034, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002034, "Video Interface: DI1 - Display Interrupt 1 (R/W).")

    MakeNameEx(0xCC002038, "VI.DI2", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002038, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002038, "Video Interface: DI2 - Display Interrupt 2 (R/W).")

    MakeNameEx(0xCC00203c, "VI.DI3", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00203c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00203c, "Video Interface: DI3 - Display Interrupt 3 (R/W).")

    MakeNameEx(0xCC002040, "VI.DL0", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002040, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002040, "Video Interface: DL0 - Display Latch Register 0 (R/W).")

    MakeNameEx(0xCC002044, "VI.DL1", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002044, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002044, "Video Interface: DL1 - Display Latch Register 1 (R/W).")

    MakeNameEx(0xCC002048, "VI.HSW", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002048, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC002048, "Video Interface: HSW - Scaling Width Register (R/W).")

    MakeNameEx(0xCC00204a, "VI.HSR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00204a, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00204a, "Video Interface: HSR - Horizontal Scaling Register (R/W).")

    MakeNameEx(0xCC00204c, "VI.FCT0", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00204c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00204c, "Video Interface: FCT0 - Filter Coefficient Table 0 (AA stuff) (R/W).")

    MakeNameEx(0xCC002050, "VI.FCT1", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002050, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002050, "Video Interface: FCT1 - Filter Coefficient Table 1 (AA stuff) (R/W).")

    MakeNameEx(0xCC002054, "VI.FCT2", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002054, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002054, "Video Interface: FCT2 - Filter Coefficient Table 2 (AA stuff) (R/W).")

    MakeNameEx(0xCC002058, "VI.FCT3", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002058, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002058, "Video Interface: FCT3 - Filter Coefficient Table 3 (AA stuff) (R/W).")

    MakeNameEx(0xCC00205c, "VI.FCT4", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00205c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00205c, "Video Interface: FCT4 - Filter Coefficient Table 4 (AA stuff) (R/W).")

    MakeNameEx(0xCC002060, "VI.FCT5", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002060, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002060, "Video Interface: FCT5 - Filter Coefficient Table 5 (AA stuff) (R/W).")

    MakeNameEx(0xCC002064, "VI.FCT6", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002064, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002064, "Video Interface: FCT6 - Filter Coefficient Table 6 (AA stuff) (R/W).")

    MakeNameEx(0xCC002068, "VI.unkn0", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002068, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002068, "Video Interface: ? (AA stuff) (R/W).")

    MakeNameEx(0xCC00206c, "VI.VICLK", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00206c, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00206c, "Video Interface: VICLK - VI Clock Select Register (R/W).")

    MakeNameEx(0xCC00206e, "VI.VISEL", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00206e, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00206e, "Video Interface: VISEL - VI DTV Status Register (R/W).")

    MakeNameEx(0xCC002070, "VI.unkn1", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002070, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC002070, "Video Interface: ? (R/W).")

    MakeNameEx(0xCC002072, "VI.Border_HBE", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002072, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC002072, "Video Interface: HBE - Border HBE (R/W).")

    MakeNameEx(0xCC002074, "VI.Border_HBS", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002074, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC002074, "Video Interface: HBS - Border HBS (R/W).")

    MakeNameEx(0xCC002076, "VI.unkn2", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002076, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC002076, "Video Interface: ? (unused?).")

    MakeNameEx(0xCC002078, "VI.unkn3", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC002078, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC002078, "Video Interface: ? (unused?).")

    MakeNameEx(0xCC00207c, "VI.unkn4", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00207c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00207c, "Video Interface: ? (unused?).")

    # Processor Interface Register
    AddSegEx(0xCC003000, 0xCC003100, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
    RenameSeg(0xCC003000, "PI")
    SetSegmentType(0xCC003000, SEG_BSS)

    MakeNameEx(0xCC003000, "PI.INTSR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC003000, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC003000, "Processor Interface: INTSR - interrupt cause (R).")

    MakeNameEx(0xCC003004, "PI.INTMR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC003004, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC003004, "Processor Interface: INTMR - interrupt mask (R/W).")

    MakeNameEx(0xCC00300c, "PI.FIFO_Base_Start", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00300c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00300c, "Processor Interface: FIFO Base Start (R/W).")

    MakeNameEx(0xCC003010, "PI.unkn0", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC003010, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC003010, "Processor Interface: FIFO Base End?.")

    MakeNameEx(0xCC003014, "PI.unkn1", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC003014, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC003014, "Processor Interface: PI (cpu) FIFO current Write Pointer?.")

    MakeNameEx(0xCC003018, "PI.unkn2", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC003018, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC003018, "Processor Interface: ?.")

    MakeNameEx(0xCC00301c, "PI.unkn3", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00301c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00301c, "Processor Interface: ?.")

    MakeNameEx(0xCC003020, "PI.unkn4", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC003020, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC003020, "Processor Interface: ?.")

    MakeNameEx(0xCC003024, "PI.unkn5", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC003024, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC003024, "Processor Interface: ?.")

    MakeNameEx(0xCC00302c, "PI.unkn6", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00302c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00302c, "Processor Interface: ?.")

    # Memory Interface Register
    AddSegEx(0xCC004000, 0xCC004080, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
    RenameSeg(0xCC004000, "MI")
    SetSegmentType(0xCC004000, SEG_BSS)

    MakeNameEx(0xCC004000, "MI.Protected_Region_No1", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004000, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC004000, "Memory Interface: Protected Region No1 (R/W).")

    MakeNameEx(0xCC004004, "MI.Protected_Region_No2", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004004, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC004004, "Memory Interface: Protected Region No2 (R/W).")

    MakeNameEx(0xCC004008, "MI.Protected_Region_No3", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004008, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC004008, "Memory Interface: Protected Region No3 (R/W).")

    MakeNameEx(0xCC00400c, "MI.Protected_Region_No4", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00400c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00400c, "Memory Interface: Protected Region No4 (R/W).")

    MakeNameEx(0xCC004010, "MI.protection_type", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004010, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004010, "Memory Interface: type of the protection, 4*2 bits (R/W).")

    MakeNameEx(0xCC00401c, "MI.interrupt_mask", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00401c, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00401c, "Memory Interface: MI interrupt mask (?/W).")

    MakeNameEx(0xCC00401e, "MI.interrupt_cause", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00401e, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00401e, "Memory Interface: interrupt cause (R/W).")

    MakeNameEx(0xCC004020, "MI.unkn0", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004020, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004020, "Memory Interface: ? (?/?).")

    MakeNameEx(0xCC004022, "MI.ADDRLO", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004022, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004022, "Memory Interface: ADDRLO - address which failed protection rules (R/?).")

    MakeNameEx(0xCC004024, "MI.ADDRHI", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004024, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004024, "Memory Interface: ADDRHI - address, which failed protection rules (R/?).")

    MakeNameEx(0xCC004032, "MI.unkn1", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004032, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004032, "Memory Interface: TIMERHI (R/?).")

    MakeNameEx(0xCC004034, "MI.unkn2", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004034, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004034, "Memory Interface: TIMERLO (R/?).")

    MakeNameEx(0xCC004036, "MI.unkn3", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004036, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004036, "Memory Interface: TIMERHI (R/?).")

    MakeNameEx(0xCC004038, "MI.unkn4", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004038, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004038, "Memory Interface: TIMERLO (R/?).")

    MakeNameEx(0xCC00403a, "MI.unkn5", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00403a, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00403a, "Memory Interface: TIMERHI (R/?).")

    MakeNameEx(0xCC00403c, "MI.unkn6", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00403c, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00403c, "Memory Interface: TIMERLO (R/?).")

    MakeNameEx(0xCC00403e, "MI.unkn7", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00403e, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00403e, "Memory Interface: TIMERHI (R/?).")

    MakeNameEx(0xCC004040, "MI.unkn8", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004040, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004040, "Memory Interface: TIMERLO (R/?).")

    MakeNameEx(0xCC004042, "MI.unkn9", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004042, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004042, "Memory Interface: TIMERHI (R/?).")

    MakeNameEx(0xCC004044, "MI.unkn10", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004044, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004044, "Memory Interface: TIMERLO (R/?).")

    MakeNameEx(0xCC004046, "MI.unkn11", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004046, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004046, "Memory Interface: TIMERHI (R/?).")

    MakeNameEx(0xCC004048, "MI.unkn12", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004048, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004048, "Memory Interface: TIMERLO (R/?).")

    MakeNameEx(0xCC00404a, "MI.unkn13", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00404a, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00404a, "Memory Interface: TIMERHI (R/?).")

    MakeNameEx(0xCC00404c, "MI.unkn14", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00404c, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00404c, "Memory Interface: TIMERLO (R/?).")

    MakeNameEx(0xCC00404e, "MI.unkn15", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00404e, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00404e, "Memory Interface: TIMERHI (R/?).")

    MakeNameEx(0xCC004050, "MI.unkn16", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004050, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004050, "Memory Interface: TIMERLO (R/?).")

    MakeNameEx(0xCC004052, "MI.unkn17", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004052, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004052, "Memory Interface: TIMERHI (R/?).")

    MakeNameEx(0xCC004054, "MI.unkn18", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004054, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004054, "Memory Interface: TIMERLO (R/?).")

    MakeNameEx(0xCC004056, "MI.unkn19", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004056, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004056, "Memory Interface: TIMERHI (R/?).")

    MakeNameEx(0xCC004058, "MI.unkn20", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC004058, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC004058, "Memory Interface: TIMERLO (R/?).")

    MakeNameEx(0xCC00405a, "MI.unkn21", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00405a, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00405a, "Memory Interface: ? (R/?).")

    # Digital Signal Processor Register
    AddSegEx(0xCC005000, 0xCC005200, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
    RenameSeg(0xCC005000, "DSP")
    SetSegmentType(0xCC005000, SEG_BSS)

    MakeNameEx(0xCC005000, "DSP.Mailbox_Hi", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC005000, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC005000, "Digital Signal Processor Interface: DSP Mailbox High (to DSP) (R/W).")

    MakeNameEx(0xCC005002, "DSP.Mailbox_Lo", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC005002, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC005002, "Digital Signal Processor Interface: DSP Mailbox Low (to DSP) (R/W).")

    MakeNameEx(0xCC005004, "DSP.CPU_Mailbox_Hi", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC005004, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC005004, "Digital Signal Processor Interface: CPU Mailbox High (from DSP) (R).")

    MakeNameEx(0xCC005006, "DSP.CPU_Mailbox_Lo", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC005006, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC005006, "Digital Signal Processor Interface: CPU Mailbox Low (from DSP) (R).")

    MakeNameEx(0xCC00500a, "DSP.AI_DSP_CSR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00500a, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00500a, "Digital Signal Processor Interface: AI DSP CSR - Control Status Register (DSP Status) (?/W).")

    MakeNameEx(0xCC005012, "DSP.AR_SIZE", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC005012, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC005012, "Digital Signal Processor Interface: AR_SIZE (?/?).")

    MakeNameEx(0xCC005016, "DSP.AR_MODE", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC005016, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC005016, "Digital Signal Processor Interface: AR_MODE (?/?).")

    MakeNameEx(0xCC00501a, "DSP.AR_REFRESH", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00501a, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00501a, "Digital Signal Processor Interface: AR_REFRESH (?/?).")

    MakeNameEx(0xCC005020, "DSP.AR_DMA_MMADDR_H", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC005020, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC005020, "Digital Signal Processor Interface: AR_DMA_MMADDR_H (?/?).")

    MakeNameEx(0xCC005022, "DSP.AR_DMA_MMADDR_L", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC005022, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC005022, "Digital Signal Processor Interface: AR_DMA_MMADDR_L (?/?).")

    MakeNameEx(0xCC005024, "DSP.AR_DMA_ARADDR_H", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC005024, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC005024, "Digital Signal Processor Interface: AR_DMA_ARADDR_H (?/?).")

    MakeNameEx(0xCC005026, "DSP.AR_DMA_ARADDR_L", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC005026, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC005026, "Digital Signal Processor Interface: AR_DMA_ARADDR_L (?/?).")

    MakeNameEx(0xCC005028, "DSP.AR_DMA_CNT_H", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC005028, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC005028, "Digital Signal Processor Interface: AR_DMA_CNT_H (?/?).")

    MakeNameEx(0xCC00502a, "DSP.AR_DMA_CNT_L", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00502a, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00502a, "Digital Signal Processor Interface: AR_DMA_CNT_L (?/?).")

    MakeNameEx(0xCC005030, "DSP.DSP_DMA_start_addr_Hi", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC005030, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC005030, "Digital Signal Processor Interface: DMA Start address (High) (?/W).")

    MakeNameEx(0xCC005032, "DSP.DMA_start_addr_Lo", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC005032, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC005032, "Digital Signal Processor Interface: DMA Start address (Low) (?/W).")

    MakeNameEx(0xCC005036, "DSP.DMA_Control_or_len", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC005036, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC005036, "Digital Signal Processor Interface: DMA Control/DMA length (Length of Audio Data) (?/W).")

    MakeNameEx(0xCC00503a, "DSP.DMA_Bytes_left", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00503a, idaapi.FF_WORD, 2, 0)
    MakeRptCmt(0xCC00503a, "Digital Signal Processor Interface: DMA Bytes left (R/?).")

    # DVD Interface Register
    AddSegEx(0xCC006000, 0xCC006040, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
    RenameSeg(0xCC006000, "DI")
    SetSegmentType(0xCC006000, SEG_BSS)

    MakeNameEx(0xCC006000, "DI.DISR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006000, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006000, "DVD Interface: DISR - DI Status Register (R/W).")

    MakeNameEx(0xCC006004, "DI.DICVR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006004, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006004, "DVD Interface: DICVR - DI Cover Register (status2) (R/W).")

    MakeNameEx(0xCC006008, "DI.DICMDBUF0", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006008, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006008, "DVD Interface: DICMDBUF0 - DI Command Buffer 0 (R/W).")

    MakeNameEx(0xCC00600c, "DI.DICMDBUF1", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00600c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00600c, "DVD Interface: DICMDBUF1 - DI Command Buffer 1 (offset in 32 bit words) (R/W).")

    MakeNameEx(0xCC006010, "DI.DICMDBUF2", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006010, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006010, "DVD Interface: DICMDBUF2 - DI Command Buffer 2 (source length) (R/W).")

    MakeNameEx(0xCC006014, "DI.DIMAR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006014, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006014, "DVD Interface: DIMAR - DMA Memory Address Register (R/W).")

    MakeNameEx(0xCC006018, "DI.DILENGTH", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006018, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006018, "DVD Interface: DILENGTH - DI DMA Transfer Length Register (R/W).")

    MakeNameEx(0xCC00601c, "DI.DICR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00601c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00601c, "DVD Interface: DICR - DI Control Register (R/W).")

    MakeNameEx(0xCC006020, "DI.DIIMMBUF", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006020, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006020, "DVD Interface: DIIMMBUF - DI immediate data buffer (error code ?) (R/W).")

    MakeNameEx(0xCC006024, "DI.DICFG", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006024, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006024, "DVD Interface: DICFG - DI Configuration Register (R).")

    # Serial Interface Register
    AddSegEx(0xCC006400, 0xCC006500, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
    RenameSeg(0xCC006400, "SI")
    SetSegmentType(0xCC006400, SEG_BSS)

    MakeNameEx(0xCC006400, "SI.SIC0OUTBUF", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006400, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006400, "Serial Interface: SIC0OUTBUF - SI Channel 0 Output Buffer (Joy-channel 1 Command) (R/W).")

    MakeNameEx(0xCC00640c, "SI.SIC1OUTBUF", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00640c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00640c, "Serial Interface: SIC1OUTBUF - SI Channel 1 Output Buffer (Joy-channel 2 Command) (R/W).")

    MakeNameEx(0xCC006418, "SI.SIC2OUTBUF", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006418, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006418, "Serial Interface: SIC2OUTBUF - SI Channel 2 Output Buffer (Joy-channel 3 Command) (R/W).")

    MakeNameEx(0xCC006424, "SI.SIC3OUTBUF", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006424, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006424, "Serial Interface: SIC3OUTBUF - SI Channel 3 Output Buffer (Joy-channel 4 Command) (R/W).")

    MakeNameEx(0xCC006404, "SI.Joy_channel_1_Buttons_1", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006404, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006404, "Serial Interface: Joy-channel 1 Buttons 1 (R).")

    MakeNameEx(0xCC006410, "SI.SIC1INBUFH", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006410, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006410, "Serial Interface: SIC1INBUFH - SI Channel 1 Input Buffer High (Joy-channel 2 Buttons 1) (R).")

    MakeNameEx(0xCC00641c, "SI.Joy_channel_3_Buttons_1", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00641c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00641c, "Serial Interface: Joy-channel 3 Buttons 1 (R).")

    MakeNameEx(0xCC006428, "SI.Joy_channel_4_Buttons_1", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006428, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006428, "Serial Interface: Joy-channel 4 Buttons 1 (R).")

    MakeNameEx(0xCC006408, "SI.Joy_channel_1_Buttons_2", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006408, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006408, "Serial Interface: Joy-channel 1 Buttons 2 (R/W).")

    MakeNameEx(0xCC006414, "SI.Joy_channel_2_Buttons_2", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006414, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006414, "Serial Interface: Joy-channel 2 Buttons 2 (R/W).")

    MakeNameEx(0xCC006420, "SI.Joy_channel_3_Buttons_2", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006420, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006420, "Serial Interface: Joy-channel 3 Buttons 2 (R/W).")

    MakeNameEx(0xCC00642c, "SI.SIC3INBUFL", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00642c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00642c, "Serial Interface: SIC3INBUFL - SI Channel 3 Input Buffer Low (Joy-channel 4 Buttons 2) (R).")

    MakeNameEx(0xCC006430, "SI.SIPOLL", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006430, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006430, "Serial Interface: SIPOLL - SI Poll Register (Joy-channel Control (?) (Calibration gun ?)) (R/W).")

    MakeNameEx(0xCC006434, "SI.SICOMCSR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006434, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006434, "Serial Interface: SICOMCSR - SI Communication Control Status Register (command) (R/W).")

    MakeNameEx(0xCC006438, "SI.SISR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006438, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006438, "Serial Interface: SISR - SI Status Register (channel select & status2) (R/W).")

    MakeNameEx(0xCC00643c, "SI.SIEXILK", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00643c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00643c, "Serial Interface: SIEXILK - SI EXI Clock Lock (R/W).")

    MakeNameEx(0xCC006480, "SI.IO_buffer", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006480, idaapi.FF_BYTE, 0x1, 0)
    MakeArray(0xCC006480, 0x80)
    MakeRptCmt(0xCC006480, "Serial Interface: SI i/o buffer (access by word) (R/W).")

    # External Interface Register
    AddSegEx(0xCC006800, 0xCC006840, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
    RenameSeg(0xCC006800, "EXI")
    SetSegmentType(0xCC006800, SEG_BSS)

    MakeNameEx(0xCC006800, "EXI.EXI0CSR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006800, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006800, "External Interface: EXI0CSR - EXI Channel 0 Parameter Register (Status?) (R/W).")

    MakeNameEx(0xCC006814, "EXI.EXI1CSR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006814, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006814, "External Interface: EXI1CSR - EXI Channel 1 Parameter Register (R/W).")

    MakeNameEx(0xCC006828, "EXI.EXI2CSR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006828, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006828, "External Interface: EXI2CSR - EXI Channel 2 Parameter Register (R/W).")

    MakeNameEx(0xCC006804, "EXI.EXI0MAR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006804, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006804, "External Interface: EXI0MAR - EXI Channel 0 DMA Start Address (R/W).")

    MakeNameEx(0xCC006818, "EXI.EXI1MAR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006818, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006818, "External Interface: EXI1MAR - EXI Channel 1 DMA Start Address (R/W).")

    MakeNameEx(0xCC00682c, "EXI.EXI2MAR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00682c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00682c, "External Interface: EXI2MAR - EXI Channel 2 DMA Start Address (R/W).")

    MakeNameEx(0xCC006808, "EXI.EXI0LENGTH", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006808, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006808, "External Interface: EXI0LENGTH - EXI Channel 0 DMA Transfer Length (R/W).")

    MakeNameEx(0xCC00681c, "EXI.Channel_1_DMA_Transfer_Length", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00681c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00681c, "External Interface: EXI Channel 1 DMA Transfer Length (R/W).")

    MakeNameEx(0xCC006830, "EXI.Channel_2_DMA_Transfer_Length", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006830, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006830, "External Interface: EXI Channel 2 DMA Transfer Length (R/W).")

    MakeNameEx(0xCC00680c, "EXI.EXI0CR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC00680c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC00680c, "External Interface: EXI0CR - EXI Channel 0 Control Register (R/W).")

    MakeNameEx(0xCC006820, "EXI.EXI1CR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006820, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006820, "External Interface: EXI1CR - EXI Channel 1 Control Register (R/W).")

    MakeNameEx(0xCC006834, "EXI.EXI2CR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006834, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006834, "External Interface: EXI2CR - EXI Channel 2 Control Register (R/W).")

    MakeNameEx(0xCC006810, "EXI.EXI0DATA", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006810, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006810, "External Interface: EXI0DATA - EXI Channel 0 Immediate Data (R/W).")

    MakeNameEx(0xCC006824, "EXI.EXI1DATA", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006824, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006824, "External Interface: EXI1DATA - EXI Channel 1 Immediate Data (R/W).")

    MakeNameEx(0xCC006838, "EXI.EXI2DATA", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006838, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006838, "External Interface: EXI2DATA - EXI Channel 2 Immediate Data (R/W).")

    # Audio Interface Register
    AddSegEx(0xCC006C00, 0xCC006C20, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
    RenameSeg(0xCC006C00, "AI")
    SetSegmentType(0xCC006C00, SEG_BSS)

    MakeNameEx(0xCC006C00, "AI.AICR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006C00, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006C00, "Audio Streaming Interface: AICR - Audio Interface Control Register (R/W).")

    MakeNameEx(0xCC006C04, "AI.AIVR", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006C04, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006C04, "Audio Streaming Interface: AIVR - Audio Interface Volume Register (R/W).")

    MakeNameEx(0xCC006C08, "AI.AISCNT", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006C08, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006C08, "Audio Streaming Interface: AISCNT - Audio Interface Sample Counter (R).")

    MakeNameEx(0xCC006C0c, "AI.AIIT", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC006C0c, idaapi.FF_DWRD, 4, 0)
    MakeRptCmt(0xCC006C0c, "Audio Streaming Interface: AIIT - Audio Interface Interrupt Timing (R/W).")

    # Graphics FIFO Register
    AddSegEx(0xCC008000, 0xCC008008, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
    RenameSeg(0xCC008000, "GXFIFO")
    SetSegmentType(0xCC008000, SEG_BSS)

    MakeNameEx(0xCC008000, "GXFIFO", idc.SN_CHECK | idaapi.SN_PUBLIC)
    MakeData(0xCC008000, idaapi.FF_QWRD, 8, 0)
    MakeRptCmt(0xCC008000, "Graphic display lists Interface. (R/W).")


def create_sections(loader_input, sections_infos, fmt):
    header = None
    if fmt == DOL_FORMAT_NAME:
        header = get_dol_header(loader_input)
    else:
        dol_file = open(sections_infos.DOL_FILENAME, "r")
        header = get_dol_header(dol_file)
        dol_file.close()

    # Add text sections
    sections_intervals = [] # used to split the bss
    for i in xrange(MAX_CODE_SECTION):
        if header.text_offsets[i] == 0 or header.text_addresses[i] == 0 or header.text_sizes[i] == 0:
            continue

        addr = header.text_addresses[i]
        size = header.text_sizes[i]
        off = header.text_offsets[i]

        sections_intervals.append( [addr, addr + size] )

        AddSegEx(addr, addr + size, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
        RenameSeg(addr, ".text{0}".format(i))
        SetSegmentType(addr, SEG_CODE)
        if fmt == RAW_FORMAT_NAME:
            loader_input.file2base(addr & 0x01FFFFFF, addr, addr + size, 0)
        else:
            loader_input.file2base(off, addr, addr + size, 0)

    # Add data sections
    for i in xrange(MAX_DATA_SECTION):
        if header.data_sizes[i] == 0:
            continue

        addr = header.data_addresses[i]
        size = header.data_sizes[i]
        off = header.data_offsets[i]

        sections_intervals.append( [addr, addr + size] )

        AddSegEx(addr, addr + size, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
        RenameSeg(addr, ".data{0}".format(i))
        SetSegmentType(addr, SEG_DATA)
        if fmt == RAW_FORMAT_NAME:
            loader_input.file2base(addr & 0x01FFFFFF, addr, addr + size, 0)
        else:
            loader_input.file2base(off, addr, addr + size, 0)
    sections_intervals.sort(key=lambda x: x[0])
    
    # Add splited bss
    if header.bss_address:
        addr = header.bss_address
        size = header.bss_size

        # Get non-overlapping bss intervals
        bss_intervals = remove_intervals_from_interval([addr, addr + size], sections_intervals)
        sections_intervals += bss_intervals

        i = 0
        for bss_interval in bss_intervals:
            AddSegEx(bss_interval[0], bss_interval[1], 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
            RenameSeg(bss_interval[0], ".bss{0}".format(i))
            SetSegmentType(bss_interval[0], SEG_BSS)
            i += 1
            if fmt == RAW_FORMAT_NAME:
                loader_input.file2base(bss_interval[0] & 0x01FFFFFF, bss_interval[0], bss_interval[1], 0)

    # Add Stack
    if sections_infos.is_stack_valid():
        AddSegEx(sections_infos.STACK_ADDRESS - sections_infos.STACK_SIZE, sections_infos.STACK_ADDRESS, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
        RenameSeg(sections_infos.STACK_ADDRESS - sections_infos.STACK_SIZE, ".stack")
        SetSegmentType(sections_infos.STACK_ADDRESS - sections_infos.STACK_SIZE, SEG_DATA)
        if fmt == RAW_FORMAT_NAME:
            sections_intervals.append( [sections_infos.STACK_ADDRESS - sections_infos.STACK_SIZE, sections_infos.STACK_ADDRESS] )
            loader_input.file2base(sections_infos.STACK_ADDRESS - sections_infos.STACK_SIZE & 0x01FFFFFF, sections_infos.STACK_ADDRESS - sections_infos.STACK_SIZE, sections_infos.STACK_ADDRESS, 0)

    # If RAW parse OSGlobals
    # Add .AllocatedArenaLo and .AllocatedArenaHi
    if fmt == RAW_FORMAT_NAME:
        loader_input.seek(0x30)
        sections_infos.ARENA_LO = struct.unpack(">I", loader_input.read(4))[0]
        sections_infos.ARENA_HI = struct.unpack(">I", loader_input.read(4))[0]

        print(sections_infos.is_allocated_arenas_valids())
        print(sections_infos.ARENA_START_ADDRESS, sections_infos.ARENA_END_ADDRESS)
        print(sections_infos.ARENA_LO, sections_infos.ARENA_HI)

        if sections_infos.is_allocated_arenas_valids():
            AddSegEx(sections_infos.ARENA_START_ADDRESS, sections_infos.ARENA_LO, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
            RenameSeg(sections_infos.ARENA_START_ADDRESS, ".AllocatedArenaLo")
            SetSegmentType(sections_infos.ARENA_START_ADDRESS, SEG_DATA)
            loader_input.file2base(sections_infos.ARENA_START_ADDRESS & 0x01FFFFFF, sections_infos.ARENA_START_ADDRESS, sections_infos.ARENA_LO, 0)
            sections_intervals.append( [sections_infos.ARENA_START_ADDRESS, sections_infos.ARENA_LO] )

            AddSegEx(sections_infos.ARENA_HI, sections_infos.ARENA_END_ADDRESS, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
            RenameSeg(sections_infos.ARENA_HI, ".AllocatedArenaHi")
            SetSegmentType(sections_infos.ARENA_HI, SEG_DATA)
            loader_input.file2base(sections_infos.ARENA_HI & 0x01FFFFFF, sections_infos.ARENA_HI, sections_infos.ARENA_END_ADDRESS, 0)
            sections_intervals.append( [sections_infos.ARENA_HI, sections_infos.ARENA_END_ADDRESS] )

        # Add .FST
        fst_addr = struct.unpack(">I", loader_input.read(4))[0]
        
        AddSegEx(fst_addr, 0x81800000, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
        RenameSeg(fst_addr, ".FST")
        SetSegmentType(fst_addr, SEG_DATA)
        loader_input.file2base(fst_addr & 0x01FFFFFF, fst_addr, 0x81800000, 0)
        sections_intervals.append( [fst_addr, 0x81800000] )

    # else add Arena
    if not sections_infos.is_allocated_arenas_valids() and sections_infos.is_arena_valid():
        AddSegEx(sections_infos.ARENA_START_ADDRESS, sections_infos.ARENA_END_ADDRESS, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
        RenameSeg(sections_infos.ARENA_START_ADDRESS, ".Arena")
        SetSegmentType(sections_infos.ARENA_START_ADDRESS, SEG_DATA)
        if fmt == RAW_FORMAT_NAME:
            loader_input.file2base(sections_infos.ARENA_START_ADDRESS & 0x01FFFFFF, sections_infos.ARENA_START_ADDRESS, sections_infos.ARENA_END_ADDRESS, 0)
            sections_intervals.append( [sections_infos.ARENA_START_ADDRESS, sections_infos.ARENA_END_ADDRESS] )

    # add unmapped sections and rebase
    if fmt == RAW_FORMAT_NAME:
        sections_intervals.sort(key=lambda x: x[0])
        unmapped_intervals = remove_intervals_from_interval([0x80003100, 0x81800000], sections_intervals)
        
        for i, unmapped_interval in enumerate(unmapped_intervals):
            AddSegEx(unmapped_interval[0], unmapped_interval[1], 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
            RenameSeg(unmapped_interval[0], ".unmapped{0}".format(i))
            SetSegmentType(unmapped_interval[0], SEG_DATA)
            loader_input.file2base(unmapped_interval[0] & 0x01FFFFFF, unmapped_interval[0], unmapped_interval[1], 0)

    # resolve .sdata(2) .sbss(2) (.sdata next .sbss < SDA) renaming existing sections
    seg_start_ea_list = sorted(list(idautils.Segments()))
    if sections_infos.is_sda_valid():
        for i in range( len(seg_start_ea_list) ):
            if sections_infos.SDA_BASE - 0x8000 == seg_start_ea_list[i]:
                if GetSegmentAttr(seg_start_ea_list[i], idc.SEGATTR_TYPE) != idaapi.SEG_DATA:
                    break
                idc.RenameSeg(seg_start_ea_list[i], ".sdata")
                if len(seg_start_ea_list) > i + 1 and \
                    GetSegmentAttr(seg_start_ea_list[i + 1], idc.SEGATTR_TYPE) == idaapi.SEG_BSS and \
                    seg_start_ea_list[i + 1] < sections_infos.SDA_BASE + 0x8000:
                    idc.RenameSeg(seg_start_ea_list[i + 1], ".sbss")
                break
    if sections_infos.is_sda2_valid():
        for i in range( len(seg_start_ea_list) ):
            if sections_infos.SDA2_BASE - 0x8000 == seg_start_ea_list[i]:
                if GetSegmentAttr(seg_start_ea_list[i], idc.SEGATTR_TYPE) != idaapi.SEG_DATA:
                    break
                idc.RenameSeg(seg_start_ea_list[i], ".sdata2")
                if len(seg_start_ea_list) > i + 1 and \
                    GetSegmentAttr(seg_start_ea_list[i + 1], idc.SEGATTR_TYPE) == idaapi.SEG_BSS and \
                    seg_start_ea_list[i + 1] < sections_infos.SDA2_BASE + 0x8000:
                    idc.RenameSeg(seg_start_ea_list[i + 1], ".sbss2")
                break

    return idaapi.add_entry(header.entry_point, header.entry_point, "start", 1)


#################################################################
# API overload
#################################################################
def section_sanity_check(offset, addr, size, file_len):
    if offset != 0 and offset < DOL_HEADER_SIZE:
        print("Error - Invalid offset.")
        return False
    if (offset + size) > file_len:
        print("Error - Invalid size.")
        return False
    if addr and (addr & 0x80000000 == 0):
        print("Error - Invalid address.")
        return False
    return True


# n = 0 before load and 1 at load
def accept_file(loader_input, n):
    if n:
        return False

    loader_input.seek(0, os.SEEK_END)
    file_len = loader_input.tell()
    if file_len == 0x01800000:
        loader_input.seek(0x1c)
        # GCN DVD Magic check
        if loader_input.read(4) != b"\xc2\x33\x9f\x3d":
            return False
        else:
            return RAW_FORMAT_NAME

    if file_len < DOL_HEADER_SIZE:
        return False

    header = get_dol_header(loader_input)
    valid_ep = False

    for i in xrange(MAX_CODE_SECTION):
        if not section_sanity_check(header.text_offsets[i], header.text_addresses[i], header.text_sizes[i], file_len):
            print("Error - Invalid text section.")
            return False
        section_limit = header.text_addresses[i] + header.text_sizes[i]
        if header.entry_point >= header.text_addresses[i] < section_limit:
            print("Entry point: {:08x}".format(header.entry_point))
            valid_ep = True

    if not valid_ep:
        print("Error - Invalid EP.")
        return False

    for i in xrange(MAX_DATA_SECTION):
        if not section_sanity_check(header.data_offsets[i], header.data_addresses[i], header.data_sizes[i], file_len):
            print("Error - Invalid data section.")
            return False

    if not section_sanity_check(0, header.bss_address, header.bss_size, file_len):
        print("Error - Invalid bss section.")
        return False
    return DOL_FORMAT_NAME


def load_file(loader_input, neflags, fmt):
    if fmt not in [RAW_FORMAT_NAME, DOL_FORMAT_NAME]:
        Warning("Unknown format name: '{0}'".format(fmt))
        return False

    form = AskSectionsInfoForm(fmt)
    # Execute the form
    form.Execute()

    sections_infos = SectionsInfos(form)
    # Dispose the form
    form.Free()

    if fmt == RAW_FORMAT_NAME:
        if sections_infos.DOL_FILENAME is None:
            print("Error - dol file has to be specified.")
            return False
        try:
            dol_file = open(sections_infos.DOL_FILENAME)
            if accept_file(dol_file, 0) != DOL_FORMAT_NAME:
                print("Error - Invalid dol file format.")
                return False
            dol_file.close()
        except IOError:
            print("Error - Invalid dol file path.")
            return False
    
    configure_compiler()

    # Section
    AddSegEx(0x80000000, 0x80003100, 0, 1, idaapi.saRel32Bytes, scPub, ADDSEG_NOTRUNC | ADDSEG_OR_DIE)
    RenameSeg(0x80000000, ".OSGlobals")
    SetSegmentType(0x80000000, SEG_DATA)

    # Rebase before creating vars to allow MakeFunction handlers
    if fmt == RAW_FORMAT_NAME:
        loader_input.file2base(0, 0x80000000, 0x80003100, 0)

    create_dolphin_os_globals_vars()
    create_hardware_registers_sections()
    
    return create_sections(loader_input, sections_infos, fmt)
