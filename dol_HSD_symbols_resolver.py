from pathlib import Path


__version__ = "0.0.2"
__author__ = "algoflash"
__license__ = "MIT"
__status__ = "developpement"


class Dol:
    HEADER_LEN = 0x100
    __header = None
    __data = None
    __sections_info = None # can also identify text segments to improve search
    def __init__(self, path:Path):
        data = path.read_bytes()
        self.__header = data[:Dol.HEADER_LEN]
        self.__data = data[Dol.HEADER_LEN:]

        self.__sections_info = []
        for i in range(18):
            # offset, address, length
            if int.from_bytes(data[i*4:i*4+4], "big") != 0:
                self.__sections_info.append((
                    int.from_bytes(data[i*4:i*4+4], "big"),
                    int.from_bytes(data[0x48+i*4:0x48+i*4+4], "big"),
                    int.from_bytes(data[0x90+i*4:0x90+i*4+4], "big")))
    def __str__(self):
        res = ""
        for section in self.__sections_info:
            res += ( f"{section[0]:08x} {section[1]:08x} {section[2]:08x}\n" )
        return res[:-1]
    # search_raw: bytecode
    def search_raw(self, bytecode:bytes):
        if len(bytecode) == 0:
            raise Exception("Error - No bytecode.")
        offsets = []
        for i in range(len(self.__data) - len(bytecode) + 1):
            if self.__data[i:i+len(bytecode)] == bytecode:
                offsets.append(self.resolve_img2virtual(i + Dol.HEADER_LEN))
        return offsets if len(offsets) > 0 else None
    # Resolve a dol absolute offset to a virtual memory address
    def resolve_img2virtual(self, offset:int):
        memory_address = None
        for section_info in self.__sections_info:
            if offset >= section_info[0] and offset < section_info[0] + section_info[2]:
                return section_info[1] + offset - section_info[0]
        raise Exception(f"Not found: {offset:08x}")
    # Resolve a virtual memory address to a dol absolute offset
    def resolve_virtual2img(self, address:int):
        for section_info in self.__sections_info:
            if address >= section_info[1] and address < section_info[1] + section_info[2]:
                return section_info[0] + address - section_info[1]
        raise Exception(f"Not found: {address:08x}")
    # search by lib function length
    # identify functions using the bl graph and their bytecode length


def parse_gnt(path:Path):
    text = path.read_text().splitlines()
    asm_dict = {}
    current_label = None
    # assembly_dict[label] = (bytecode, mask)
    for line in text:
        if len(line) == 0: continue
        if line[0] == "." or line[0] == "\t":
            continue
        # Retrieve bytecode and instruction
        if line[:3] != "/* ": # Label
            current_label = line[:-1]
            asm_dict[current_label] = b""
        else:
            #print(splited[4:8])
            asm = line.split("*/\t")[1]
            splited = line.split(" ")
            asm_dict[current_label] += int(splited[4] + splited[5] + splited[6] + splited[7], 16).to_bytes(4, "big")
    return asm_dict

dol = Dol(Path("boot.dol"))

# Search the dol offset of a given virtual address:
print( f"{dol.resolve_virtual2img(0x80003258):08x}" )
# Search the virtual address of a given dol offset:
print( f"{dol.resolve_img2virtual(0x1234):08x}" )

# Search raw bytecode splited by chunks from parsing gnt4 already found labels & symbols
# print virtual address translated from the dol when found to allow compare of the gnt4
# identified labels
"""
# https://github.com/doldecomp/gnt4/tree/master/asm/sysdolphin
for gnt_asm_file_path in Path("asm/dvd").glob("*"):
    asm_dict = parse_gnt(gnt_asm_file_path)
    for key in asm_dict:
        offsets = None
        if len(asm_dict[key]) > 0:
            offsets = dol.search_raw(asm_dict[key])
        if offsets != None and len(offsets) < 3:
            print(key, " ".join([f"{offset:08x}" for offset in offsets]))
        else:
            print(key, "None")
"""
