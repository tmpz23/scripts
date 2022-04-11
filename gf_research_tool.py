import os
from pathlib import Path
import shutil
from urllib import request


__version__ = "0.1.4"
__author__ = "algoflash"
__license__ = "MIT"
__status__ = "developpement"


# Original Gotcha Force GCM iso PATH
GF_ISO_PATH = Path("ROM/Gotcha Force (USA).iso")
# https://fr.dolphin-emu.org/download/
dolphin_path = Path("C:/Program Files/Dolphin/Dolphin.exe")

# Possible camera float value :
# 163, # black screen when adding 20

# knowns values:
blacklist_offsets = [
    44, 45, 46, 47,     # move speed
    108, 109, 110, 111, # falling acceleration
    120, 121, 122, 123, # jetpack_distancea
    124, 125, 126, 127, # falling_speed
    184, 185, 186, 187, # camera_focus_z
    188, 189, 190, 191, # camera_focus_z_after_shoot
    192, 193, 194, 195, # camera_distance
    196, 197, 198, 199, # camera_initial_distance
    200, 201, 202, 203, # camera_distance_after_shoot
    204, 205, 206, 207, # camera_z_after_kill
    240, 241, 242, 243, # camera_move_delta_distance
    416, 419, 420, 421, 422, 423, 424, 425, 426, 427, 428] # collection menu properties
###############################################################
# MANUAL
###############################################################
    # set GF_ISO_PATH with the path of your iso & dolphin_path with you dolphin emu install
    #
    # It will create this folder config:
    # gf_patch/
    #   afsdata_unpack/
    #       root # afs files
    #       sys # afs sys and config files
    #   iso_unpack/
    #       root # iso files
    #       sys  # sys iso files
    #   pzz_unpack/
    #   tools/ # Ours tools
    #   gf_patched.iso # our patched iso to test
    #   gf_research_tool.py <- this script !
###############################################################
# TOOLS PATHS
###############################################################
# https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/pzztool/pzztool.py
pzztool_path = Path("tools/pzztool.py")
# https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/afstool/afstool.py
afstool_path = Path("tools/afstool.py")
# https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/gcmtool/gcmtool.py
gcmtool_path = Path("tools/gcmtool.py")
###############################################################
# Paths
###############################################################
borg_data_backup_path = Path("borg/pl0615data.bin.back")
borg_data_path = Path("borg/pl0615data.bin")

afs_unpack = Path("afsdata_unpack")
iso_unpack = Path("iso_unpack")
pzz_unpack = Path("pzz_unpack")
###############################################################
# Helpers
###############################################################
class Dumper:
    __path = None
    __data = None
    def __init__(self, path:Path):
        self.__path = path
        self.__data = path.read_bytes()
    def dump(self, offset:int, length:int):
        buff_str = ""
        beg = offset - (offset % 16)
        if beg > 16:
            beg -= 16

        for i in range(0x30):
            current_offset = beg + i
            if current_offset >= len(self.__data):
                break
            if current_offset % 16 == 0:
                buff_str += f"\n0x{current_offset:08x}:{current_offset:08}: "
            if current_offset == offset:
                buff_str += "["
            elif current_offset == offset + length:
                buff_str = buff_str[:-1] + "] "
            buff_str += f"{self.__data[current_offset]:02x} "
        print(buff_str[1:])

###############################################################
# FUNCTIONS
###############################################################
def install_tools(tools_path):
    tools_path.mkdir(parents=True)
    request.urlretrieve("https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/pzztool/pzztool.py", tools_path / "pzztool.py")
    request.urlretrieve("https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/afstool/afstool.py", tools_path / "afstool.py")
    request.urlretrieve("https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/gcmtool/gcmtool.py", tools_path / "gcmtool.py")


def install():
    root_path = Path("gf_patch")

    install_tools(root_path / "tools")

    print("###############################################################")
    print("# Extracting iso files")
    print("###############################################################")
    if os.system(f"python {root_path / gcmtool_path} -u \"{GF_ISO_PATH}\" \"{root_path / iso_unpack}\"") != 0:
        raise Exception("Error while unpacking GCM iso.")

    print("###############################################################")
    print("# Extracting afs_data.afs files")
    print("###############################################################")
    if os.system(f"python {root_path / afstool_path} -u {root_path / iso_unpack}/root/afs_data.afs {root_path / afs_unpack}") != 0:
        raise Exception("Error while unpacking AFS file.")
    
    print("###############################################################")
    print("# Writting new AFS rebuild config and rebuilding AFS.")
    print("###############################################################")
    from configparser import ConfigParser
    config = ConfigParser(allow_no_value=True) # allow_no_value to allow adding comments
    config.optionxform = str # makes options case sensitive
    config.read(root_path / afs_unpack / 'sys' / 'afs_rebuild.conf')
    config.set("Default", "# Documentation available here: https://github.com/Virtual-World-RE/NeoGF/tree/main/afstool#afs_rebuildconf")
    config.set("Default", "files_rebuild_strategy", "index")
    config.set("FilenameDirectory", "toc_offset_of_fd_offset", "auto")
    config.set("FilenameDirectory", "fd_offset", "auto")
    config.write((root_path / afs_unpack / 'sys' / 'afs_rebuild.conf').open("w"))
    if os.system(f"python {root_path / afstool_path} -r {root_path / afs_unpack}") != 0:
        raise Exception("Error while rebuilding AFS.")
    if os.system(f"python {root_path / afstool_path} -p {root_path / afs_unpack} {root_path / iso_unpack / 'root' / 'afs_data.afs'}") != 0:
        raise Exception("Error while packing AFS.")

    print("###############################################################")
    print("# Rebuilding FST for faster rebuild of GCM ISO.")
    print("###############################################################")
    if os.system(f"python {root_path / gcmtool_path} -r \"{root_path / iso_unpack}\" -a=4") != 0:
        raise Exception("Error while rebuilding GCM FST.")

    print("###############################################################")
    print("# Extracting borg files.")
    print("###############################################################")
    if os.system(f"python {root_path / pzztool_path} --unpack {root_path / afs_unpack}/root/pl0615.pzz {root_path / pzz_unpack}") != 0:
        raise Exception("Error while unpacking borg pzz.")
    if os.system(f"python {root_path / pzztool_path} --decompress {root_path / pzz_unpack}/000C_pl0615.pzzp") != 0:
        raise Exception("Error while decompressing borg pzz data file.")
    (root_path / pzz_unpack / "000C_pl0615.pzzp").unlink()

    print("###############################################################")
    print("# Creating borg data backup file")
    print("###############################################################")
    (root_path / "borg").mkdir()
    shutil.copy( root_path / afs_unpack / "root" / "pl0615data.bin", root_path / borg_data_backup_path)

    print("###############################################################")
    print(f"# Moving this script in {root_path} folder.")
    print("###############################################################")
    shutil.move("gf_research_tool.py", root_path / "gf_research_tool.py")

    print("###############################################################")
    print("Installation is now completed.")
    print("###############################################################")


def update():
    shutil.rmtree("tools")
    install_tools(Path("tools"))
    request.urlretrieve("https://raw.githubusercontent.com/tmpz23/scripts/main/gf_research_tool.py", f"gf_research_tool.py")


# Patch both data files adding val=1 on each bytes
def patch(file_path:Path, beg:int, end:int, val:int, set_bool:bool):
    print(blacklist_offsets)
    with file_path.open("rb+") as patch_file:
        for i in range(beg, end):
            if i in blacklist_offsets:
                continue
            patch_file.seek(i)
            tmp_val = val if set_bool else (int.from_bytes(patch_file.read(1), "big") + val) % 256
            patch_file.seek(i)
            patch_file.write(tmp_val.to_bytes(1, "big"))


def rebuild_run():
    shutil.copy(borg_data_path, afs_unpack / "root" / "pl0615data.bin")
    shutil.copy(borg_data_path, pzz_unpack / "000C_pl0615data.bin")

    # PZZ back the pl0615
    if os.system(f"python {pzztool_path} -pzz {pzz_unpack} {afs_unpack / 'root'/ 'pl0615.pzz'}") != 0:
        raise Exception(f"Error while pzz of folder {pzz_unpack}")
    # Pack afs_data
    if os.system(f"python {afstool_path} -p {afs_unpack} {iso_unpack / 'root' / 'afs_data.afs'}") != 0:
        raise Exception("Error while AFS pack")
    if Path("gf_patched.iso").is_file():
        Path("gf_patched.iso").unlink()
    # Import back of the afs_data.afs in the iso file
    if os.system(f"python {gcmtool_path} -p {iso_unpack} gf_patched.iso") != 0:
        raise Exception("Error while GCM pack.")
    # Run the game with dolphin
    if os.system(f"\"{dolphin_path}\" /e gf_patched.iso /b") != 0:
        raise Exception("Error with Dolphin Emulator run.")


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description=\
        " _____ _     _           _    _ _ _         _   _    _____ _____ \n"+
        "|  |  |_|___| |_ _ _ ___| |  | | | |___ ___| |_| |  | __  |   __|\n"+
        "|  |  | |  _|  _| | | .'| |  | | | | . |  _| | . |  |    -|   __|\n"+
        " \___/|_|_| |_| |___|__,|_|  |_____|___|_| |_|___|  |__|__|_____|\n"+
        "Gotcha Force modding - Borg research tool - [GameCube] v"+ __version__+"\nplxxxxdata.bin is in big endian", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-i', '--install', action='store_true', help="-i: install the patching config and needed tools inside gf_patch folder")
    group.add_argument('-u', '--update', action='store_true', help="-u: remove tools folder and download last version of this script & tools")
    group.add_argument('-d', '--dump', nargs='+', metavar="offset", type=int, help="-d offset length: dump selected offset")
    group.add_argument('-pii', '--patch-interval-increment', nargs=3, metavar=("begin_offset", "ending_offset", "value_to_add"), type=int, help="-pii begining_offset ending_offset value_to_add: patch the range with byte = (byte + value) %% 256")
    group.add_argument('-pis', '--patch-interval-set', nargs=3, metavar=("begin_offset", "ending_offset", "value_to_set"), type=int, help="-pis begining_offset ending_offset value_to_set: patch the range with byte = value")
    group.add_argument('-pr', '--patch-run', action='store_true', help=f"-pr: patch and run the game using the borg file {borg_data_path} as-is.")
    return parser


###############################################################
# Main
###############################################################
if __name__ == '__main__':
    args = get_argparser().parse_args()

    if args.install:
        print("# Installing basic config in folder gf_patch")
        if Path("tools").is_dir() or Path("iso_unpack").is_dir() or Path("gf_patch").is_dir():
            raise Exception("Error - This script is already installed. Remove old files before installing.")
        install()
    elif args.update:
        print("# Updating the script and tools")
        if not Path("tools").is_dir() or not Path("gf_research_tool.py").is_file():
            raise Exception("Error - This script is not installed. Install it before updating.")
        update()
    elif args.dump:
        dumper = Dumper(borg_data_backup_path)
        dumper.dump(args.dump[0], args.dump[1] if len(args.dump) > 1 else 1)
    elif args.patch_interval_increment or args.patch_interval_set:
        mini = None
        maxi = None
        val = None
        if args.patch_interval_increment:
            mini = args.patch_interval_increment[0]
            maxi = args.patch_interval_increment[1] + 1
            val = args.patch_interval_increment[2]
        else:
            mini = args.patch_interval_set[0]
            maxi = args.patch_interval_set[1] + 1
            val = args.patch_interval_set[2]

        print(f"# Patching Neo GRED Borg [{mini}:{maxi}] {'adding' if args.patch_interval_increment else 'with value'} {val}")

        # Here is the interval that you can set for patching data files and test what's going on ingame


        searched_range = range(mini, maxi)

        print(f"Patching {mini}-{maxi} to identify a change")
        # Reset both pl0615 data files in gf_patch folder to their initial state
        shutil.copy(borg_data_backup_path, borg_data_path)
        
        patch(borg_data_path, mini, maxi, val, args.patch_interval_set != None)
        rebuild_run()

        if len(searched_range) == 0: # bad args
            print("Not a valid range")
        while True:
            m = (mini + maxi) // 2
            if mini == m:
                print(f"last studied byte offset: {mini}")
                break

            print(f"tested range: {m}-{maxi}")
            # Reset both pl0615 data files in gf_patch folder to their initial state
            shutil.copy(borg_data_backup_path, borg_data_path)

            patch(borg_data_path, m, maxi, val, args.patch_interval_set != None)
            rebuild_run()

            # we patch trying rigth part and 
            # if we found the change in patched range we keep the interval
            if input("If the change is still here type y/Y:").lower() == "y":
                mini = m
            else:
                maxi = m
    elif args.patch_run:
        rebuild_run()
