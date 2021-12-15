from pathlib import Path
import shutil
import os

################################################################
# Inital state
################################################################
# Your gf_patch folder has to contains:
# gf_patch/
#   afs_data/
#      files
#   back/
#      pl0615/ <- original pzz file uncompressed with pzztool.py
#         000C_pl0615data.bin
#         001....
#         ...
#      pl0615data.bin <- original file
#   afs_data.afs
#   pzztool.py
#   pl0615/ <- uncompressed pzz file with pzztool.py
#         000C ...
#         ...
#   binreverse_patch_gf_interval.py <- this script !

p1 = Path("pl0615/000C_pl0615data.bin")
p2 = Path("pl0615data.bin")

known_offsets = [416, 419, 420, 421, 422, 423, 424, 425, 426, 427, 428]

# Patch both data files adding val=1 on each bytes
def patch(beg:int, end:int, val:int = 1):
    with p1.open("rb+") as data1, p2.open("rb+") as data2:
        for i in range(beg, end+1):
            if i in known_offsets:
                continue
            data1.seek(i)
            tmp1 = data1.read(1)
            tmp1 = (int.from_bytes(tmp1, "big") + val) % 256
            data1.seek(i)
            data1.write(tmp1.to_bytes(1, "big"))

            data2.seek(i)
            tmp2 = data2.read(1)
            tmp2 = (int.from_bytes(tmp2, "big") + val) % 256
            data2.seek(i)
            data2.write(tmp2.to_bytes(1, "big"))


# Reset to default data files with files in back/ folder
def reset():
    if p1.is_file():
        p1.unlink()
    if p2.is_file():
        p2.unlink()
    shutil.copy("back/pl0615/000C_pl0615data.bin", str(p1))
    shutil.copy("back/pl0615data.bin", str(p2))


# Patch afs_data with new data files
def patch_afs():
    if Path("afs_data/pl0615.pzz").is_file():
        Path("afs_data/pl0615.pzz").unlink()
    if Path("afs_data/pl0615data.bin").is_file():
        Path("afs_data/pl0615data.bin").unlink()
    shutil.copy("pl0615.pzz", "afs_data/pl0615.pzz")
    shutil.copy("pl0615data.bin", "afs_data/pl0615data.bin")


###############################################################
# Main
###############################################################

# Reset both pl0615 data files in gf_patch folder
reset()

# Here is the interval that you can set for patching data files and test what's going on ingame
mini = (p1.stat().st_size // 16) * 6
maxi = (p1.stat().st_size // 16) * 7

patch(mini, maxi)

# PZZ back the pl0615
os.system("python pzztool.py -pzz pl0615 > logs.txt")

# Import back both file in afs_data.afs
patch_afs()

# Change here with the path of your AFSPacker.exe
os.system("..\\AFSPacker.exe -c afs_data patched_afs_data.afs > logs.txt")


"""
# Import back of the afs_data.afs in the iso file
I'm looking for a cmd line solution
For now you can use GCRebuilder 1.1 to import back the patched_afs_data.afs in the iso.
Then run the patched iso in dolphin emulator.

# Run the game with dolphin
os.system('"C:\\Program Files\\Dolphin\\Dolphin.exe" /e patched_iso.iso')
"""
