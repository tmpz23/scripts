import ctypes
import idaapi


__version__ = "1.2"
__license__ = "The GNU General Public License (GPL) Version 2, June 1991"
__status__ = "developpement"


# https://forum.tuts4you.com/files/file/2222-rel-dol-loader/ (cpp)
# https://github.com/P1kachu/idapython-dol-loader/blob/master/gc_wii_dol_loader.py (rewrited in python)
# .data overlapping .bss sections are removed -> fix here spliting .bss in parts to keep .data sections
# tested on a friend computer who buyed IDA 6.8 on windows


DolHeaderSize = 0x100
DolFormatName = "Nintendo GC/Wii DOL" # Only tested on GC dol
MaxCodeSection = 7
MaxDataSection = 11


class DolHeader(ctypes.BigEndianStructure):
    _fields_ = [
        ("text_offsets", ctypes.c_uint * MaxCodeSection),
        ("data_offsets", ctypes.c_uint * MaxDataSection),
        ("text_addresses", ctypes.c_uint * MaxCodeSection),
        ("data_addresses", ctypes.c_uint * MaxDataSection),
        ("text_sizes", ctypes.c_uint * MaxCodeSection),
        ("data_sizes", ctypes.c_uint * MaxDataSection),
        ("bss_address", ctypes.c_uint),
        ("bss_size", ctypes.c_uint),
        ("entry_point", ctypes.c_uint),
        ]


def get_dol_header(li):
    li.seek(0)
    header = DolHeader()
    string = li.read(DolHeaderSize)
    fit = min(len(string), ctypes.sizeof(header))
    ctypes.memmove(ctypes.addressof(header), string, fit)
    return header


# Get non-overlapping intervals from interval by removing intervals_to_remove
# intervals_to_remove has to be sorted by left val
# return [[a,b], ...] or None
def remove_intervals_from_interval(interval, intervals_to_remove):
    interval = interval[:]
    result_intervals = []
    for interval_to_remove in intervals_to_remove:
        if interval_to_remove[1] < interval[0]: continue # end before
        if interval_to_remove[0] > interval[1]: break # begin after

        if interval_to_remove[0] <= interval[0]: # begin before
            if interval_to_remove[1] >= interval[1]: # total overlap
                return None
            interval[0] = interval_to_remove[1] # begin truncate
        elif interval_to_remove[1] >= interval[1]: # end truncate
            interval[1] = interval_to_remove[0]
            break
        else: # middle truncate
            result_intervals.append( [interval[0], interval_to_remove[0]] )
            interval[0] = interval_to_remove[1]

    return result_intervals + [interval]



def section_sanity_check(offset, addr, size, file_len):
    if offset != 0 and offset < DolHeaderSize:
        print("Error - Invalid offset.")
        return False
    if (offset + size) > file_len:
        print("Error - Invalid size.")
        return False
    if addr and (addr & 0x80000000 == 0):
        print("Error - Invalid address.")
        return False
    return True


def accept_file(li, n):
    valid_ep = False

    if n:
        return False

    li.seek(0, os.SEEK_END)
    file_len = li.tell()
    if file_len < DolHeaderSize:
        return False

    header = get_dol_header(li)

    for i in xrange(MaxCodeSection):
        if not section_sanity_check(header.text_offsets[i], header.text_addresses[i], header.text_sizes[i], file_len):
            print("Error - Invalid text section.")
            return False
        section_limit = header.text_addresses[i] + header.text_sizes[i]
        if header.entry_point >= header.text_addresses[i] and header.entry_point < section_limit:
            print("Entry point: {:08x}".format(header.entry_point))
            valid_ep = True

    if not valid_ep:
        print("Error - Invalid EP.")
        return False

    for i in xrange(MaxDataSection):
        if not section_sanity_check(header.data_offsets[i], header.data_addresses[i], header.data_sizes[i], file_len):
            print("Error - Invalid data section.")
            return False

    if not section_sanity_check(0, header.bss_address, header.bss_size, file_len):
        print("Error - Invalid bss section.")
        return False
    return DolFormatName


def load_file(li, neflags, fmt):
    if fmt != DolFormatName:
        Warning("Unknown format name: '{0}'".format(fmt))

    idaapi.set_processor_type("PPC", SETPROC_ALL|SETPROC_FATAL)
    idaapi.set_compiler_id(COMP_GNU)

    header = get_dol_header(li)

    idaapi.set_selector(1, 0);

    flags = ADDSEG_NOTRUNC|ADDSEG_OR_DIE

    sections_intervals = [] # used to split the bss
    for i in xrange(MaxCodeSection):
        if header.text_offsets[i] == 0 or header.text_addresses[i] == 0 or header.text_sizes[i] == 0:
            continue

        addr = header.text_addresses[i]
        size = header.text_sizes[i]
        off = header.text_offsets[i]

        sections_intervals.append( [addr, addr + size] )

        AddSegEx(addr, addr + size, 0, 1, saRelPara, scPub, flags)
        RenameSeg(addr, ".text{0}".format(i))
        SetSegmentType(addr, SEG_CODE)
        li.file2base(off, addr, addr + size, 0)

    for i in xrange(MaxDataSection):
        if header.data_sizes[i] == 0:
            continue

        addr = header.data_addresses[i]
        size = header.data_sizes[i]
        off = header.data_offsets[i]

        sections_intervals.append( [addr, addr + size] )

        AddSegEx(addr, addr + size, 0, 1, saRelPara, scPub, flags)
        RenameSeg(addr, ".data{0}".format(i))
        SetSegmentType(addr, SEG_DATA)
        li.file2base(off, addr, addr + size, 0)

    sections_intervals.sort(key=lambda x: x[0])
    
    if header.bss_address:
        addr = header.bss_address
        size = header.bss_size

        # Get non-overlapping bss intervals
        bss_intervals = remove_intervals_from_interval([addr, addr + size], sections_intervals)

        i = 0
        for bss_interval in bss_intervals:
            AddSegEx(bss_interval[0], bss_interval[1], 0, 1, saRelPara, scPub, flags)
            RenameSeg(bss_interval[0], ".bss{0}".format(i))
            SetSegmentType(bss_interval[0], SEG_BSS)
            i += 1

    idaapi.add_entry(header.entry_point, header.entry_point, "start", 1)

    return True
