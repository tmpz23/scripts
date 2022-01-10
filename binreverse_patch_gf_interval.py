from pathlib import Path
import shutil
import os


__version__ = "0.0.1"
__author__ = "algoflash"
__license__ = "MIT"
__status__ = "developpement"


# Original Gotcha Force iso PATH
GF_ISO_PATH = Path("../ROM/Gotcha Force (USA).iso")
################################################################
# MANUAL
################################################################
# for AFSPacker.exe install dotnet : https://dotnet.microsoft.com/en-us/download/dotnet/3.1 (x64)
# pip install py7zr
# set GF_ISO_PATH with the path of your iso
#
# It will create this folder config :
# gf_patch/
#   gf_iso_extract/
#       dev  # our working dir with backup and uncompressed patched_afs_data
#       root # iso files
#       sys  # sys iso files
#   tools/ # Ours tools
#   gf_patched.iso # our patched iso to test
#   binreverse_patch_gf_interval.py <- this script !
################################################################
# TOOLS PATHS
################################################################
# https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/pzztool.py
pzztool_path = Path("tools/pzztool.py")
# https://github.com/MaikelChan/AFSPacker
afspacker_path = Path("tools/AFSPacker.exe")
# https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/gcmtool.py
gcmtool_path = Path("tools/gcmtool.py")
# https://fr.dolphin-emu.org/download/
dolphin_path = Path("C:/Program Files/Dolphin/Dolphin.exe")
###############################################################
# BORG FILES TO PATCH
###############################################################
backup_1 = Path("gf_iso_extract/dev/back/000C_pl0615data.bin")
backup_2 = Path("gf_iso_extract/dev/back/pl0615data.bin")

patch_1 = Path("gf_iso_extract/dev/pl0615/000C_pl0615data.bin")
patch_2 = Path("gf_iso_extract/dev/pl0615data.bin")

dest_patch1 = Path("gf_iso_extract/dev/patched_afs_data/pl0615.pzz")
dest_patch2 = Path("gf_iso_extract/dev/patched_afs_data/pl0615data.bin")

###############################################################
# FUNCTIONS
###############################################################
def install():
    Path("gf_patch/tools").mkdir(parents=True, exist_ok=True)
    Path("gf_patch/gf_iso_extract/dev/back").mkdir(parents=True, exist_ok=True)
    print("Downloading tools")
    from urllib import request
    request.urlretrieve("https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/pzztool.py", "gf_patch/tools/pzztool.py")
    request.urlretrieve("https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/gcmtool.py", "gf_patch/tools/gcmtool.py")
    request.urlretrieve("https://github.com/MaikelChan/AFSPacker/releases/download/v2.1.1/AFSPacker-v2.1.1-win-x64.7z", "gf_patch/tools/AFSPacker.7z")
    import py7zr
    with py7zr.SevenZipFile('gf_patch/tools/AFSPacker.7z', mode='r') as z:
        z.extractall()
    Path("readme.txt").unlink()
    Path("gf_patch/tools/AFSPacker.7z").unlink()
    shutil.move("AFSPacker.exe", "gf_patch/tools/AFSPacker.exe")
    print("Extracting iso files")
    os.system(f"python gf_patch/tools/gcmtool.py -u \"{str(GF_ISO_PATH)}\" gf_patch/gf_iso_extract/")
    print("Extracting afs_data.afs files")
    os.system("gf_patch\\tools\\AFSPacker.exe -e gf_patch/gf_iso_extract/root/afs_data.afs gf_patch/gf_iso_extract/dev/patched_afs_data > NUL")
    print("Extracting borg files.")
    os.system("python gf_patch/tools/pzztool.py --unpack gf_patch/gf_iso_extract/dev/patched_afs_data/pl0615.pzz gf_patch/gf_iso_extract/dev/pl0615")
    os.system("python gf_patch/tools/pzztool.py --decompress gf_patch/gf_iso_extract/dev/pl0615/000C_pl0615.pzzp")
    Path("gf_patch/gf_iso_extract/dev/pl0615/000C_pl0615.pzzp").unlink()
    shutil.copy("gf_patch/gf_iso_extract/dev/patched_afs_data/pl0615data.bin", "gf_patch/gf_iso_extract/dev/pl0615data.bin")
    print("Creating borg backup files")
    shutil.copy("gf_patch/gf_iso_extract/dev/pl0615data.bin", "gf_patch/gf_iso_extract/dev/back/pl0615data.bin")
    shutil.copy("gf_patch/gf_iso_extract/dev/pl0615/000C_pl0615data.bin", "gf_patch/gf_iso_extract/dev/back/000C_pl0615data.bin")
    print("Moving this script in gf_patch folder.")
    shutil.move("binreverse_patch_gf_interval.py", "gf_patch/binreverse_patch_gf_interval.py")
    print("Installation is now completed.")


# Patch both data files adding val=1 on each bytes
def patch(beg:int, end:int, val:int = 1):
    known_offsets = [416, 419, 420, 421, 422, 423, 424, 425, 426, 427, 428]
    with patch_1.open("rb+") as patch_1_file:
        for i in range(beg, end):
            if i in known_offsets:
                continue
            patch_1_file.seek(i)
            tmp_val = ((int.from_bytes(patch_1_file.read(1), "big") + val) % 256).to_bytes(1, "big")
            patch_1_file.seek(i)
            patch_1_file.write(tmp_val)
    shutil.copy(str(patch_1), str(patch_2))


def get_argparser():
    import argparse
    parser = argparse.ArgumentParser(description='Borg Research Tool - [GameCube] Gotcha Force v' + __version__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    #parser.add_argument('begin_offset', type=int, metavar='begin_offset', help='Begining of patching')
    #parser.add_argument('ending_offset', type=int, metavar='ending_offset', help='Ending of patching')
    #parser.add_argument('value', type=int, metavar='value', help='Value to add to each byte in the range', nargs='?', default=1)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-i', '--install', action='store_true', help="-i : install the patching config and needed tools inside gf_patch folder")
    group.add_argument('-p', '--patch', nargs=3, metavar=("begin_offset", "ending_offset", "value_to_add"), type=int, help="-p begining_offset ending_offset value_to_add : patch the range with byte = byte + value ")
    return parser


###############################################################
# Main
###############################################################
if __name__ == '__main__':
    args = get_argparser().parse_args()

    if args.install:
        print("INSTALLING BASIC PATCH CONFIG IN FOLDER gf_patch")
        install()
    elif args.patch:
        print(f"PATCHING Neo GRED Borg {args.patch[0]}:{args.patch[1]} adding {args.patch[2]}")
        # Reset both pl0615 data files in gf_patch folder to their initial state
        shutil.copy(str(backup_1), str(patch_1))
        shutil.copy(str(backup_2), str(patch_2))

        # Here is the interval that you can set for patching data files and test what's going on ingame
        #mini = (patch_1.stat().st_size // 16) * 6
        #maxi = (patch_1.stat().st_size // 16) * 7

        patch(args.patch[0], args.patch[1], args.patch[2])

        # PZZ back the pl0615
        os.system(f"python {str(pzztool_path)} -pzz {str(patch_1.parent)} {str(dest_patch1)} > NUL")
        shutil.copy(str(patch_2), str(dest_patch2))
        # Pack afs_data
        os.system(f"{str(afspacker_path)} -c gf\\dev\\patched_afs_data gf\\root\\afs_data.afs > NUL")
        # Import back of the afs_data.afs in the iso file
        os.system(f"python {str(gcmtool_path)} -p gf_iso_extract gf_patched.iso")
        # Run the game with dolphin
        os.system(f'\"{str(dolphin_path)}\" /e gf_patched.iso')
