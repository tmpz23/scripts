''' **************************************************************************************************
*   Nintendo GameCube Gekko CPU Extension Module
*
*   The PowerPC processor module in IDA Pro does not handle Gekko Paired Single instructions.
*   Fortunately IDA Pro supports the concept of extension modules that can add support for
*   non-standard instructions, so this extension adds support for the PS instruction set.
*
*   INSTALLATION
*   ------------
*   Place the processor extension modules (gekkoPS.py) within your IDA Pro 'plugins' directory.
*   By default the plugin is active when dealing with PPC code, but you can disable/re-enable the
*   plugin by using the entry in the Edit/Plugins menu. If you want the plugin to be disabled on
*   load, you will have to edit this source code. Change the value of g_HookState to 'kDisabled'.
*
*   CHANGES
*   -------
*   2022        Algoflash           Support IDA Pro 6.8 - translated in python for a friend that has Ida pro
*   2007.12.22  HyperIris   V1.0    Created, base on Dean's PowerPC Altivec/VMX Extension Module
*                                   Support IDA Pro 5.2
**************************************************************************************************'''
import idaapi


GEKKO_VERSION = "2022_0.1.0"


# -------------------------------------------------------------------------------------------------
# Data needed to maintain plugin state
HookState = ["kDefault", "kEnabled", "kDisabled"]

g_HookState = HookState.index("kEnabled")
g_GekkoNode = idaapi.netnode()
g_GekkoNodeName = "$ PowerPC Gekko Extension Parameters"


# -------------------------------------------------------------------------------------------------
# Macros used to define opcode table
def OP(x):
    return (x & 0x3f) << 26
OP_MASK = OP(0x3f)
def OPS(op, xop):
    return OP(op) | ((xop & 0x1f) << 1)
def OPSC(op, xop, rc):
    return OPS(op, xop) | (rc & 1)
#define OPSC(op, xop, rc) (OPS ((op), (xop)) | rc)
OPS_MASK = OPSC(0x3f, 0x1f, 1)
OPS_MASK_DOT = OPSC(0x3f, 0x1f, 1)
def OPM(op, xop):
    return OP(op) | ((xop & 0x3f) << 1)
def OPMC(op, xop, rc):
    return OPM(op, xop) | (rc & 1)
OPM_MASK = OPMC(0x3f, 0x3f, 0)
def OPL(op, xop):
    return OP(op) | ((xop & 0x3ff) << 1)
def OPLC(op, xop, rc):
    return OPL(op, xop) | (rc & 1)
#define OPLC(op, xop, rc) (OPL ((op), (xop)) | rc)
OPL_MASK     = OPLC(0x3f, 0x3ff, 1)
OPL_MASK_DOT = OPLC(0x3f, 0x3ff, 1)


# -------------------------------------------------------------------------------------------------
# Operand identifiers (they map into g_gekkoPsOperands array)
NO_OPERAND = 0
FA = 1
FB = 2
FC = 3
FD = 4
FS = 4 # FS = FD
crfD = 5
WB = 6
IB = 7
WC = 8
IC = 9
#  D,
RA = 10
RB = 11
DRA = 12
DRB = 13


# -------------------------------------------------------------------------------------------------
# Structure used to define an operand
class gekko_ps_operand:
    bits = None # int
    shift = None # int
    def __init__(self, bits, shift):
        self.bits = bits
        self.shift = shift


g_gekkoPsOperands = [
    gekko_ps_operand(0, 0  ),  # No Operand
    gekko_ps_operand(5, 16 ),  # FA
    gekko_ps_operand(5, 11 ),  # FB
    gekko_ps_operand(5, 6  ),  # FC
    gekko_ps_operand(5, 21 ),  # FD/FS
    gekko_ps_operand(3, 23 ),  # crfD,
    gekko_ps_operand(1, 16 ),  # WB,
    gekko_ps_operand(3, 12 ),  # IB,
    gekko_ps_operand(1, 10 ),  # WC,
    gekko_ps_operand(3, 7  ),  # IC,
    # { 12, 0 },  # D,
    gekko_ps_operand(5, 16 ),  # RA
    gekko_ps_operand(5, 11 ),  # RB
    gekko_ps_operand(5, 16 ),  # DRA,
    gekko_ps_operand(5, 11 )   # DRB,
]


# -------------------------------------------------------------------------------------------------
# Opcode identifiers (they map into g_gekkoPsOpcodes array)
gekko_ps_insn_type_t = {
    "gekko_ps_insn_start"  : idaapi.CUSTOM_CMD_ITYPE,

    "gekko_psq_lx"         : idaapi.CUSTOM_CMD_ITYPE, # = gekko_ps_insn_start,
    "gekko_psq_stx"        : 0x8001,
    "gekko_psq_lux"        : 0x8002,
    "gekko_psq_stux"       : 0x8003,
    "gekko_psq_l"          : 0x8004,
    "gekko_psq_lu"         : 0x8005,
    "gekko_psq_st"         : 0x8006,
    "gekko_psq_stu"        : 0x8007,

    "gekko_ps_div"         : 0x8008,
    "gekko_ps_div_dot"     : 0x8009,
    "gekko_ps_sub"         : 0x800a,
    "gekko_ps_sub_dot"     : 0x800b,
    "gekko_ps_add"         : 0x800c,
    "gekko_ps_add_dot"     : 0x800d,
    "gekko_ps_sel"         : 0x800e,
    "gekko_ps_sel_dot"     : 0x800f,
    "gekko_ps_res"         : 0x8010,
    "gekko_ps_res_dot"     : 0x8011,
    "gekko_ps_mul"         : 0x8012,
    "gekko_ps_mul_dot"     : 0x8013,
    "gekko_ps_rsqrte"      : 0x8014,
    "gekko_ps_rsqrte_dot"  : 0x8015,
    "gekko_ps_msub"        : 0x8016,
    "gekko_ps_msub_dot"    : 0x8017,
    "gekko_ps_madd"        : 0x8018,
    "gekko_ps_madd_dot"    : 0x8019,
    "gekko_ps_nmsub"       : 0x801a,
    "gekko_ps_nmsub_dot"   : 0x801b,
    "gekko_ps_nmadd"       : 0x801c,
    "gekko_ps_nmadd_dot"   : 0x801d,
    "gekko_ps_neg"         : 0x801e,
    "gekko_ps_neg_dot"     : 0x801f,
    "gekko_ps_mr"          : 0x8020,
    "gekko_ps_mr_dot"      : 0x8021,
    "gekko_ps_nabs"        : 0x8022,
    "gekko_ps_nabs_dot"    : 0x8023,
    "gekko_ps_abs"         : 0x8024,
    "gekko_ps_abs_dot"     : 0x8025,

    "gekko_ps_sum0"        : 0x8026,
    "gekko_ps_sum0_dot"    : 0x8027,
    "gekko_ps_sum1"        : 0x8028,
    "gekko_ps_sum1_dot"    : 0x8029,
    "gekko_ps_muls0"       : 0x802a,
    "gekko_ps_muls0_dot"   : 0x802b,
    "gekko_ps_muls1"       : 0x802c,
    "gekko_ps_muls1_dot"   : 0x802d,
    "gekko_ps_madds0"      : 0x802e,
    "gekko_ps_madds0_dot"  : 0x802f,
    "gekko_ps_madds1"      : 0x8030,
    "gekko_ps_madds1_dot"  : 0x8031,
    "gekko_ps_cmpu0"       : 0x8032,
    "gekko_ps_cmpo0"       : 0x8033,
    "gekko_ps_cmpu1"       : 0x8034,
    "gekko_ps_cmpo1"       : 0x8035,
    "gekko_ps_merge00"     : 0x8036,
    "gekko_ps_merge00_dot" : 0x8037,
    "gekko_ps_merge01"     : 0x8038,
    "gekko_ps_merge01_dot" : 0x8039,
    "gekko_ps_merge10"     : 0x803a,
    "gekko_ps_merge10_dot" : 0x803b,
    "gekko_ps_merge11"     : 0x803c,
    "gekko_ps_merge11_dot" : 0x803d,
    "gekko_ps_dcbz_l"      : 0x803e
}

# -------------------------------------------------------------------------------------------------
# class used to define an opcode

class gekko_ps_opcode:
    insn = None # gekko_ps_insn_type_t
    name = None # const char*
    opcode = None # unsigned int
    mask = None # unsigned int
    operands = None # unsigned char operands[6]
    description = None # const char*
    def __init__(self, insn, name, opcode, mask, operands, description):
        self.insn = insn
        self.name = name
        self.opcode = opcode
        self.mask = mask
        self.operands = operands
        self.description = description


g_gekkoPsOpcodes = [
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_psq_lx"],           "psq_lx",       OPM(4, 6),          OPM_MASK,   [ FD, RA, RB, WC, IC ], "Paired Single Quantized Load Indexed" ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_psq_stx"],          "psq_stx",      OPM(4, 7),          OPM_MASK,   [ FS, RA, RB, WC, IC ], "Paired Single Quantized Store Indexed"),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_psq_lux"],          "psq_lux",      OPM(4, 38),         OPM_MASK,   [ FD, RA, RB, WC, IC ], "Paired Single Quantized Load with update Indexed" ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_psq_stux"],         "psq_stux",     OPM(4, 39),         OPM_MASK,   [ FS, RA, RB, WC, IC ], "Paired Single Quantized Store with update Indexed"),

    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_psq_l"],            "psq_l",        OP(56),             OP_MASK,    [ FD, DRA, WB, IB ],    "Paired Single Quantized Load"  ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_psq_lu"],           "psq_lu",       OP(57),             OP_MASK,    [ FD, DRA, WB, IB ],    "Paired Single Quantized Load with Update"  ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_psq_st"],           "psq_st",       OP(60),             OP_MASK,    [ FS, DRA, WB, IB ],    "Paired Single Quantized Store" ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_psq_stu"],          "psq_stu",      OP(61),             OP_MASK,    [ FS, DRA, WB, IB ],    "Paired Single Quantized Store with update" ),

    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_div"],           "ps_div",       OPSC(4, 18, 0),     OPS_MASK,       [ FD, FA, FB ],      "Paired Single Divide"  ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_div_dot"],       "ps_div.",      OPSC(4, 18, 1),     OPS_MASK_DOT,   [ FD, FA, FB ],      "Paired Single Divide"  ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_sub"],           "ps_sub",       OPSC(4, 20, 0),     OPS_MASK,       [ FD, FA, FB ],      "Paired Single Subtract"    ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_sub_dot"],       "ps_sub.",      OPSC(4, 20, 1),     OPS_MASK_DOT,   [ FD, FA, FB ],      "Paired Single Subtract"    ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_add"],           "ps_add",       OPSC(4, 21, 0),     OPS_MASK,       [ FD, FA, FB ],      "Paired Single Add" ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_add_dot"],       "ps_add.",      OPSC(4, 21, 1),     OPS_MASK_DOT,   [ FD, FA, FB ],      "Paired Single Add" ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_sel"],           "ps_sel",       OPSC(4, 23, 0),     OPS_MASK,       [ FD, FA, FC, FB ],  "Paired Single Select"  ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_sel_dot"],       "ps_sel.",      OPSC(4, 23, 1),     OPS_MASK_DOT,   [ FD, FA, FC, FB ],  "Paired Single Select"  ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_res"],           "ps_res",       OPSC(4, 24, 0),     OPS_MASK,       [ FD, FB ],          "Paired Single Reciprocal Estimate" ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_res_dot"],       "ps_res.",      OPSC(4, 24, 1),     OPS_MASK_DOT,   [ FD, FB ],          "Paired Single Reciprocal Estimate" ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_mul"],           "ps_mul",       OPSC(4, 25, 0),     OPS_MASK,       [ FD, FA, FC ],      "Paired Single Multiply"    ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_mul_dot"],       "ps_mul.",      OPSC(4, 25, 1),     OPS_MASK_DOT,   [ FD, FA, FC ],      "Paired Single Multiply"    ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_rsqrte"],        "ps_rsqrte",    OPSC(4, 26, 0),     OPS_MASK,       [ FD, FB ],          "Paired Single Reciprocal Square Root Estimate" ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_rsqrte_dot"],    "ps_rsqrte.",   OPSC(4, 26, 1),     OPS_MASK_DOT,   [ FD, FB ],          "Paired Single Reciprocal Square Root Estimate" ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_msub"],          "ps_msub",      OPSC(4, 28, 0),     OPS_MASK,       [ FD, FA, FC, FB ],  "Paired Single Multiply-Subtract"   ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_msub_dot"],      "ps_msub.",     OPSC(4, 28, 1),     OPS_MASK_DOT,   [ FD, FA, FC, FB ],  "Paired Single Multiply-Subtract"   ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_madd"],          "ps_madd",      OPSC(4, 29, 0),     OPS_MASK,       [ FD, FA, FC, FB ],  "Paired Single Multiply-Add"    ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_madd_dot"],      "ps_madd.",     OPSC(4, 29, 1),     OPS_MASK_DOT,   [ FD, FA, FC, FB ],  "Paired Single Multiply-Add"    ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_nmsub"],         "ps_nmsub",     OPSC(4, 30, 0),     OPS_MASK,       [ FD, FA, FC, FB ],  "Paired Single Negative Multiply-Subtract"  ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_nmsub_dot"],     "ps_nmsub.",    OPSC(4, 30, 1),     OPS_MASK_DOT,   [ FD, FA, FC, FB ],  "Paired Single Negative Multiply-Subtract"  ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_nmadd"],         "ps_nmadd",     OPSC(4, 31, 0),     OPS_MASK,       [ FD, FA, FC, FB ],  "Paired Single Negative Multiply-Add"   ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_nmadd_dot"],     "ps_nmadd.",    OPSC(4, 31, 1),     OPS_MASK_DOT,   [ FD, FA, FC, FB ],  "Paired Single Negative Multiply-Add"   ),

    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_neg"],           "ps_neg",       OPLC(4, 40, 0),     OPL_MASK,       [ FD, FB ],         "Paired Single Negate"  ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_neg_dot"],       "ps_neg.",      OPLC(4, 40, 1),     OPL_MASK_DOT,   [ FD, FB ],         "Paired Single Negate"  ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_mr"],            "ps_mr",        OPLC(4, 72, 0),     OPL_MASK,       [ FD, FB ],         "Paired Single Move Register"   ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_mr_dot"],        "ps_mr.",       OPLC(4, 72, 1),     OPL_MASK_DOT,   [ FD, FB ],         "Paired Single Move Register"   ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_nabs"],          "ps_nabs",      OPLC(4, 136, 0),    OPL_MASK,       [ FD, FB ],         "Paired Single Negative Absolute Value" ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_nabs_dot"],      "ps_nabs.",     OPLC(4, 136, 1),    OPL_MASK_DOT,   [ FD, FB ],         "Paired Single Negative Absolute Value" ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_abs"],           "ps_abs",       OPLC(4, 264, 0),    OPL_MASK,       [ FD, FB ],         "Paired Single Absolute Value"  ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_abs_dot"],       "ps_abs.",      OPLC(4, 264, 1),    OPL_MASK_DOT,   [ FD, FB ],         "Paired Single Absolute Value"  ),

    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_sum0"],          "ps_sum0",      OPSC(4, 10, 0),     OPS_MASK,       [ FD, FA, FC, FB ], "Paired Single vector SUM high" ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_sum0_dot"],      "ps_sum0.",     OPSC(4, 10, 1),     OPS_MASK_DOT,   [ FD, FA, FC, FB ], "Paired Single vector SUM high" ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_sum1"],          "ps_sum1",      OPSC(4, 11, 0),     OPS_MASK,       [ FD, FA, FC, FB ], "Paired Single vector SUM low"  ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_sum1_dot"],      "ps_sum1.",     OPSC(4, 11, 1),     OPS_MASK_DOT,   [ FD, FA, FC, FB ], "Paired Single vector SUM low"  ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_muls0"],         "ps_muls0",     OPSC(4, 12, 0),     OPS_MASK,       [ FD, FA, FC ],     "Paired Single Multiply Scalar high"    ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_muls0_dot"],     "ps_muls0.",    OPSC(4, 12, 1),     OPS_MASK_DOT,   [ FD, FA, FC ],     "Paired Single Multiply Scalar high"    ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_muls1"],         "ps_muls1",     OPSC(4, 13, 0),     OPS_MASK,       [ FD, FA, FC ],     "Paired Single Multiply Scalar low"     ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_muls1_dot"],     "ps_muls1.",    OPSC(4, 13, 1),     OPS_MASK_DOT,   [ FD, FA, FC ],     "Paired Single Multiply Scalar low"     ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_madds0"],        "ps_madds0",    OPSC(4, 14, 0),     OPS_MASK,       [ FD, FA, FC, FB ], "Paired Single Multiply-Add Scalar high"),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_madds0_dot"],    "ps_madds0.",   OPSC(4, 14, 1),     OPS_MASK_DOT,   [ FD, FA, FC, FB ], "Paired Single Multiply-Add Scalar high"),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_madds1"],        "ps_madds1",    OPSC(4, 15, 0),     OPS_MASK,       [ FD, FA, FC, FB ], "Paired Single Multiply-Add Scalar low" ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_madds1_dot"],    "ps_madds1.",   OPSC(4, 15, 1),     OPS_MASK_DOT,   [ FD, FA, FC, FB ], "Paired Single Multiply-Add Scalar low" ),

    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_cmpu0"],         "ps_cmpu0",     OPL(4, 0),          OPL_MASK,       [ crfD, FA, FB ],   "Paired Singles Compare Unordered High" ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_cmpo0"],         "ps_cmpo0",     OPL(4, 32),         OPL_MASK,       [ crfD, FA, FB ],   "Paired Singles Compare Ordered High"   ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_cmpu1"],         "ps_cmpu1",     OPL(4, 64),         OPL_MASK,       [ crfD, FA, FB ],   "Paired Singles Compare Unordered Low"  ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_cmpo1"],         "ps_cmpo1",     OPL(4, 96),         OPL_MASK,       [ crfD, FA, FB ],   "Paired Singles Compare Ordered Low"    ),

    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_merge00"],       "ps_merge00",   OPLC(4, 528, 0),    OPL_MASK,       [ FD, FA, FB ],     "Paired Single MERGE high"      ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_merge00_dot"],   "ps_merge00.",  OPLC(4, 528, 1),    OPL_MASK_DOT,   [ FD, FA, FB ],     "Paired Single MERGE high"      ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_merge01"],       "ps_merge01",   OPLC(4, 560, 0),    OPL_MASK,       [ FD, FA, FB ],     "Paired Single MERGE direct"    ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_merge01_dot"],   "ps_merge01.",  OPLC(4, 560, 1),    OPL_MASK_DOT,   [ FD, FA, FB ],     "Paired Single MERGE direct"    ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_merge10"],       "ps_merge10",   OPLC(4, 592, 0),    OPL_MASK,       [ FD, FA, FB ],     "Paired Single MERGE swapped"   ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_merge10_dot"],   "ps_merge10.",  OPLC(4, 592, 1),    OPL_MASK_DOT,   [ FD, FA, FB ],     "Paired Single MERGE swapped"   ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_merge11"],       "ps_merge11",   OPLC(4, 624, 0),    OPL_MASK,       [ FD, FA, FB ],     "Paired Single MERGE low"       ),
    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_merge11_dot"],   "ps_merge11.",  OPLC(4, 624, 1),    OPL_MASK_DOT,   [ FD, FA, FB ],     "Paired Single MERGE low"       ),

    gekko_ps_opcode( gekko_ps_insn_type_t["gekko_ps_dcbz_l"],        "dcbz_l",       OPL(4, 1014),       OPL_MASK,       [ RA, RB ],         "Data Cache Block Set to Zero Locked" )
]


"""***************************************************************************************************
*   FUNCTION        PluginAnalyse
*   DESCRIPTION     This is the main analysis function.. It can change cmd.itype and  operands infos
***************************************************************************************************"""
def PluginAnalyse(insn):
    global g_gekkoPsOpcodes
    global g_gekkoPsOperands
    global NO_OPERAND, FA, FB, FC, FD, FS, crfD, WB, IB, WC, IC, RA, RB, DRA, DRB

    # Get the CodeBytes
    codeBytes = idaapi.get_long(insn.ea)

    # When we check
    opBytes = codeBytes & OP_MASK

    # All our opcodes have a primary op setting of 4 or 56, 57, 60, 61. 
    if (opBytes == OP(4)) or (opBytes == OP(56)) or (opBytes == OP(57)) or (opBytes == OP(60)) or (opBytes == OP(61)):
        # Go through the entire opcode array looking for a match
        for currentOpcode in g_gekkoPsOpcodes:
            # Is this a match?
            if (codeBytes & currentOpcode.mask) == currentOpcode.opcode:
                # Ok, so we've got a match.. let's sort out the operands..

                for i in range(len(currentOpcode.operands)):
                    if currentOpcode.operands[i] == 0:
                        break

                    operandData = insn.Operands[i]
                    currentOperand = g_gekkoPsOperands[currentOpcode.operands[i]]

                    rawBits = (codeBytes >> currentOperand.shift) & ( ((1 << currentOperand.bits) ) - 1)
                    #extendedBits = ( (rawBits << (32 - currentOperand.bits)) & 0xffffffff) >> (32 - currentOperand.bits)

                    current_operand_id = currentOpcode.operands[i]
                    
                    # These are the main Gekko registers
                    if current_operand_id in [FA, FB, FC, FD, FS]:
                        operandData.type = idaapi.o_reg
                        operandData.reg = rawBits
                        # Mark the register as being an Gekko one.
                        operandData.specflag1 = 0x01
                    # Gekko PS memory loads are always via a CPU register
                    elif current_operand_id in [RA, RB]:
                        operandData.type = idaapi.o_reg
                        operandData.reg = rawBits
                        operandData.specflag1 = 0x00
                    elif current_operand_id in [crfD, WB, IB, WC, IC]:
                        operandData.type = idaapi.o_imm
                        operandData.dtyp = idaapi.dt_byte
                        operandData.value = rawBits
                    elif current_operand_id == DRA:
                        imm  = codeBytes & 0x7FF
                        sign = codeBytes & 0x800
                        displacement = 0

                        if sign == 0:
                            displacement = imm
                        else:
                            displacement = -1 * imm

                        operandData.type = idaapi.o_displ
                        operandData.phrase = rawBits
                        operandData.addr = displacement
                    # Next operand please...
                # Make a note of which opcode we are.. we need it to print our stuff out.
                insn.itype = currentOpcode.insn

                # The command is 4 bytes long.. 
                return 4
            # We obviously didn't find our opcode this time round.. go test the next one.
    # We didn't do anything.. honest.
    return 0


"""***************************************************************************************************
*   Class           Hooks
*
*   DESCRIPTION     This callback is responsible for distributing work associated with each
*                   intercepted event that we deal with. In our case we deal with the following
*                   event identifiers.
*
*                   custom_ana      :   Analyses a command (in 'cmd') to see if it is an Gekko PS
*                                       instruction. If so, then it extracts information from the
*                                       opcode in order to determine which opcode it is, along with
*                                       data relating to any used operands.
*
*                   custom_mnem     :   Generates the mnemonic for our Gekko PS instructions, by looking
*                                       into our array of opcode information structures.
*
*                   custom_outop    :   Outputs operands for Gekko PS instructions. In our case, we
*                                       have an alternate register set (vr0 to vr31), so our operands
*                                       may be marked as being Gekko registers.
*
*                   may_be_func     :   It's perfectly OK for an Gekko PS instruction to be the start
*                                       of a function, so I figured I should return 100 here. The
*                                       return value is a percentage probability..
*
*                   is_sane_insn    :   All our Gekko PS instructions (well, the ones we've identified
*                                       inside custom_ana processing), are ok.
***************************************************************************************************"""
class Hooks(idaapi.IDP_Hooks):
    # Analyse a command to see if it's an Gekko PS instruction.
    # if yes cmd.itype & cmd.size are changed
    def custom_ana(self):
        length = PluginAnalyse(idaapi.cmd)
        if length:
            idaapi.cmd.size = length
            # event processed

            # Output auto comments
            if idaapi.get_cmt(idaapi.cmd.ea, 1) == None:
                idaapi.set_cmt(idaapi.cmd.ea, g_gekkoPsOpcodes[idaapi.cmd.itype - gekko_ps_insn_type_t["gekko_ps_insn_start"]].description, 1)

            return True
        return False

    # Obtain mnemonic for our Gekko PS instructions.
    def custom_mnem(self):
        if idaapi.cmd.itype >= idaapi.CUSTOM_CMD_ITYPE:
            return g_gekkoPsOpcodes[idaapi.cmd.itype - gekko_ps_insn_type_t["gekko_ps_insn_start"]].name

    # Display operands that differ from PPC ones.. like our Gekko PS registers.
    def custom_outop(self, py_op):
        if idaapi.cmd.itype >= idaapi.CUSTOM_CMD_ITYPE:
            if (py_op.type == idaapi.o_reg) and (py_op.specflag1 & 0x01):
                idaapi.out_register("fr{0}".format(py_op.reg))
                return True
        return False
    
    # Can this be the start of a function? 
    def may_be_func(self, state):
        if idaapi.cmd.itype >= idaapi.CUSTOM_CMD_ITYPE:
            return 100
        return 0

    # If we've identified the command as an Gekko PS instruction, it's good to go.
    def is_sane_insn(self, no_crefs):
        if idaapi.cmd.itype >= idaapi.CUSTOM_CMD_ITYPE:
            return 1
        return 0
        

'''***************************************************************************************************
*   This 'PLUGIN' class is how IDA Pro interfaces with this plugin.
*   What's handled in it is the state of the plugin
***************************************************************************************************'''
class gekkoPS(idaapi.plugin_t):
    version       = idaapi.IDP_INTERFACE_VERSION
    flags         = 0
    comment       = "This plugin enables recognition of Gekko CPU Extension instructions\nwhen using IDA Pro's PowerPC processor module\n"
    help          = "Show strings and named xrefs"
    wanted_name   = "Nintendo GameCube Gekko CPU Extension " + GEKKO_VERSION
    wanted_hotkey = ""

    '''***************************************************************************************************
    *   method          init
    *
    *   DESCRIPTION     IDA will call this function only once. If this function returns PLUGIN_SKIP,
    *                   IDA will never load it again. If it returns PLUGIN_OK, IDA will unload the plugin
    *                   but remember that the plugin agreed to work with the database. The plugin will
    *                   be loaded again if the user invokes it by pressing the hotkey or selecting it
    *                   from the menu. After the second load, the plugin will stay in memory.
    *
    *   NOTES           In our case, we just hook into IDA'S callbacks if we need to be active
    *                   on plugin load.
    ***************************************************************************************************'''
    def init(self):
        global g_HookState
        global g_GekkoNode
        global g_GekkoNodeName

        if idaapi.ph.id != idaapi.PLFM_PPC:
            return idaapi.PLUGIN_SKIP

        # Create our node...
        g_GekkoNode.create(g_GekkoNodeName)

        # Retrieve any existing hook state that may be in the database.
        databaseHookState = g_GekkoNode.altval(0)

        # altval() returns 0 (which maps to kDefault) when the value isn't there.. so handle it.
        if databaseHookState != HookState.index("kDefault"):
            g_HookState = databaseHookState

        self.hooks = Hooks()
        
        if g_HookState == HookState.index("kEnabled"):
            #hook_to_notification_point(HT_IDP, PluginExtensionCallback, NULL);
            self.hooks.hook()
            idaapi.msg("Nintendo GameCube Gekko CPU Extension "+GEKKO_VERSION+" is enabled\n")
            return idaapi.PLUGIN_KEEP

        return idaapi.PLUGIN_OK


    '''***************************************************************************************************
    *   method          term
    *
    *   DESCRIPTION     IDA will call this function when the user asks to exit. This function is *not*
    *                   called in the case of emergency exits.
    *
    *   NOTES           All we can do here is to release from our callbacks..
    ***************************************************************************************************'''
    def term(self):
        self.hooks.unhook()


    '''***************************************************************************************************
    *   method          run
    *
    *   DESCRIPTION     Our plugin is all about hooking callbacks..
    ***************************************************************************************************'''
    def run(self, arg):
        global g_HookState
        global g_GekkoNode
        global g_GekkoNodeName
        if g_HookState == HookState.index("kEnabled"):
            self.hooks.unhook()
            g_HookState = HookState.index("kDisabled")
        elif g_HookState == HookState.index("kDisabled"):
            self.hooks.hook()
            g_HookState = HookState.index("kEnabled")

        g_GekkoNode.create(g_GekkoNodeName)
        g_GekkoNode.altset(0, g_HookState)

        pHookStateDescription = ["default", "enabled", "disabled"]
        idaapi.info("AUTOHIDE NONE\nNintendo GameCube Gekko CPU Extension "+GEKKO_VERSION+" is now " + pHookStateDescription[g_HookState])


def PLUGIN_ENTRY():
    return gekkoPS()
