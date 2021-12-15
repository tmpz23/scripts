from bitstring import BitStream
from pathlib import Path
import hashlib

########################################################################
# Initial conditions
########################################################################
# Create a folder named "pzz" and put in it all afs_data pzz files
# Then run :
# pzztool.py -bunpzz pzz pzzu
# download "https://raw.githubusercontent.com/Virtual-World-RE/NeoGF/main/data/NTSC_borgs.csv" and put the path in "CSV_PATH"

CSV_PATH =  "NTSC_borgs.csv"
TESTEDFILE_PATH_FORMAT = "pzzu/{0}/000C_{0}data.bin"
FILE_MASK_PATH = "mask_same_bytes"

RES_FILE_PATH = "vars_dump.txt"

# Renvoie la taille du plus petit fichier, ou -1 en cas d'erreur
# le nom de fichier doit se situer en position 0
def get_max_filelen(csv_lines:list):
    max_datafile_len = -1
    for csv_line in csv_lines:
        filename = csv_line[0]

        path = Path(TESTEDFILE_PATH_FORMAT.format(filename))
        if not path.is_file():
            continue

        if max_datafile_len == -1 or max_datafile_len > path.stat().st_size:
            max_datafile_len = path.stat().st_size
    return max_datafile_len


csv_lines = [csv_line.split(";") for csv_line in Path(CSV_PATH).open("r").read().split("\n")[1:]]
max_datafile_len = get_max_filelen(csv_lines)



with Path(RES_FILE_PATH).open("w") as study_file:
    # Here you can change offset of values you want to study
    for offset in range(max_datafile_len):
        study_file.write(f"offset {offset:04}:\n")

        # Here you can set the byte length by changing the range for instance you can see 4 bytes values if you want
        for value_bytelen in range(1, 2):
            study_file.write(f"    len={value_bytelen}\n")
            values = {}
            for csv_line in csv_lines:
                data = Path(TESTEDFILE_PATH_FORMAT.format(csv_line[0]))
                with data.open("rb") as data_file:
                    data_file.seek(offset)
                    new_value = int.from_bytes(data_file.read(value_bytelen), "big")
                    if not new_value in values:
                        values[new_value] = 1
                    else:
                        values[new_value] += 1
            # values contains values with the number of occurencies
            for value in sorted(values):
                study_file.write( ("        {0:0"+str(value_bytelen*2)+"x} ({1:03}) -> {0}\n").format(value, values[value]) )

print("Fini !")
