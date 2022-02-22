import os
from pathlib import Path
import shutil
from urllib import request


__version__ = "0.1.0"
__author__ = "algoflash"
__license__ = "MIT"
__status__ = "developpement"


# Original Gotcha Force GCM iso PATH
GF_ISO_PATH = Path("../ROM/Gotcha Force (USA).iso")
# https://fr.dolphin-emu.org/download/
dolphin_path = Path("C:/Program Files/Dolphin/Dolphin.exe")
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
# https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/pzztool.py
pzztool_path = Path("tools/pzztool.py")
# https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/afstool.py
afstool_path = Path("tools/afstool.py")
# https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/gcmtool.py
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
# FUNCTIONS
###############################################################
def install_tools(tools_path):
    tools_path.mkdir(parents=True)
    request.urlretrieve("https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/pzztool.py", tools_path / "pzztool.py")
    request.urlretrieve("https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/afstool.py", tools_path / "afstool.py")
    request.urlretrieve("https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/gcmtool.py", tools_path / "gcmtool.py")


def install():
    root_path = Path("gf_patch")

    install_tools(root_path / "tools")

    print("###############################################################")
    print("# Extracting iso files")
    print("###############################################################")
    if os.system(f"python {root_path / gcmtool_path} -u \"{GF_ISO_PATH}\" \"{root_path / iso_unpack}\"") != 0:
        raise Exception("Error while unpacking GCM iso.")

    print("###############################################################")
    print("# Rebuilding FST for faster rebuild of GCM ISO.")
    print("###############################################################")
    if os.system(f"python {root_path / gcmtool_path} -r \"{root_path / iso_unpack}\" -a=4") != 0:
        raise Exception("Error while rebuilding GCM FST.")

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
    config.set("Default", "# Documentation available here: https://github.com/Virtual-World-RE/NeoGF/blob/main/README.md#afs_rebuildconf--afs_rebuildcsv")
    config.set("Default", "files_rebuild_strategy", "index")
    config.set("FilenameDirectory", "toc_offset_of_fd_offset", "auto")
    config.set("FilenameDirectory", "fd_offset", "auto")
    config.write((root_path / afs_unpack / 'sys' / 'afs_rebuild.conf').open("w"))
    if os.system(f"python {root_path / afstool_path} -r {root_path / afs_unpack}") != 0:
        raise Exception("Error while rebuilding AFS.")

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

    print("Installation is now completed.")

def update():
    shutil.rmtree("tools")
    install_tools(Path("tools"))
    request.urlretrieve("https://raw.githubusercontent.com/tmpz23/scripts/main/gf_research_tool.py", f"gf_research_tool.py")


# Patch both data files adding val=1 on each bytes
def patch(file_path:Path, beg:int, end:int, val:int = 1):
    known_offsets = [416, 419, 420, 421, 422, 423, 424, 425, 426, 427, 428]
    with file_path.open("rb+") as patch_file:
        for i in range(beg, end):
            if i in known_offsets:
                continue
            patch_file.seek(i)
            tmp_val = ((int.from_bytes(patch_file.read(1), "big") + val) % 256).to_bytes(1, "big")
            patch_file.seek(i)
            patch_file.write(tmp_val)


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='Borg Research Tool - [GameCube] Gotcha Force v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-i', '--install', action='store_true', help="-i: install the patching config and needed tools inside gf_patch folder")
    group.add_argument('-u', '--update', action='store_true', help="-u: remove tools folder and download last version of this script & tools")
    group.add_argument('-pii', '--patch-interval-increment', nargs=3, metavar=("begin_offset", "ending_offset", "value_to_add"), type=int, help="-p begining_offset ending_offset value_to_add: patch the range with byte = (byte + value) % 256")
    group.add_argument('-pis', '--patch-interval-set', nargs=3, metavar=("begin_offset", "ending_offset", "value_to_set"), type=int, help="-p begining_offset ending_offset value_to_set: patch the range with byte = value")
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
    elif args.patch_interval_increment: # add while range > 1 with dichotomical choice after each exec
        print(f"# Patching Neo GRED Borg [{args.patch_interval_increment[0]}:{args.patch_interval_increment[1]}[ adding {args.patch_interval_increment[2]}")
        # Reset both pl0615 data files in gf_patch folder to their initial state
        shutil.copy(borg_data_backup_path, borg_data_path)

        # Here is the interval that you can set for patching data files and test what's going on ingame
        #mini = (patch_1.stat().st_size // 16) * 6
        #maxi = (patch_1.stat().st_size // 16) * 7

        patch(borg_data_path, args.patch_interval_increment[0], args.patch_interval_increment[1], args.patch_interval_increment[2])

        # PZZ back the pl0615
        if os.system(f"python {pzztool_path} -pzz {patch_1.parent} {dest_patch1} > NUL") != 0:
            raise Exception(f"Error during pzz of the file {patch_1.parent}")
        shutil.copy(patch_2, dest_patch2)
        # Pack afs_data
        if os.system(f"python {afstool_path} -p gf_iso_extract/dev/patched_afs_data gf_iso_extract/root/afs_data.afs") != 0:
            raise Exception("Error during AFS packing of the folder gf_iso_extract/dev/patched_afs_data")
        # Import back of the afs_data.afs in the iso file
        if os.system(f"python {gcmtool_path} -p gf_iso_extract gf_patched.iso") != 0:
            raise Exception("Error during packing of the GCM iso using folder gf_iso_extract.")
        # Run the game with dolphin
        if os.system(f"\"{dolphin_path}\" /e gf_patched.iso /b") != 0:
            raise Exception("Error with Dolphin Emulator run.")
    elif args.patch_interval_set: # add while range > 1 with dichotomical choice after each exec
        raise Exception("Error - Not implemented yet")
