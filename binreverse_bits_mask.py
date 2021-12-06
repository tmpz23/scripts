from bitstring import BitStream
from pathlib import Path


############################################################
# Implémenté pour du BIG ENDIAN seulement (pour le moment)
############################################################
FILE_MASK_PATH = "mask"                               # Nom de base des fichiers mask_nbits créés
CSV_PATH =  "_autres/NTSC_borgs.csv"                  # Chemin du fichier csv - nom des fichiers en première position
PROPERTY_CSV_INDEX = 3                                # Index dans le csv de la propriété à test (seulement optimisé pour les entiers relatifs pour le moment)
TESTEDFILE_PATH_FORMAT = "pzzu/{0}/000C_{0}data.bin"  # Chemin des fichiers à tester avec {0} le nom du fichier dans le csv
MAX_ERRORS = 20                                       # Nombre max d'erreurs ... (intersection ou union)
READ_LEN = 2048                                       # Taille de lecture pour les fichiers (permet de réduire le nombre de lectures)


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


# Retourne la taille en bits minimum pour encoder l'ensemble des valeurs
def get_min_value_bitlen(csv_lines: list):
    max_value = 0
    negative = 0
    for csv_line in csv_lines:
        if int(csv_line[PROPERTY_CSV_INDEX]) < 0:
            negative = 1
        if max_value < abs(int(csv_line[PROPERTY_CSV_INDEX])):
            max_value = abs(int(csv_line[PROPERTY_CSV_INDEX]))
    return len(bin(max_value)[2:]) + negative


# Retourne la séquence de bits qui se répète le plus et sa freq dans un tuple
def get_max_freq(bits_list: list):
    counts = {}
    for bits in bits_list:
        if not bits.bin in counts:
            counts[bits.bin] = 1
        else:
            counts[bits.bin] += 1
    bits = max(counts, key = lambda k: counts[k])
    return (bits, counts[bits])


# On génère pour chaque valeur de la propriété étudiée le groupe de noms de fichiers
csv_lines = [csv_line.split(";") for csv_line in Path(CSV_PATH).open("r").read().split("\n")[1:]]
total_files = len(csv_lines)
max_datafile_len = get_max_filelen(csv_lines)

print(f"Taille du plus petit fichier : {max_datafile_len}")

filenames_grouped_by_values = {} # noms de fichiers regroupés par valeurs de la propriété étudiée

for csv_line in csv_lines:
    filename = csv_line[0]
    value    = csv_line[PROPERTY_CSV_INDEX]
    if not value in filenames_grouped_by_values:
        filenames_grouped_by_values[value] = [filename]
    else:
        filenames_grouped_by_values[value].append(filename)

min_value_bitlen = get_min_value_bitlen(csv_lines)
for value_bitlen in range(min_value_bitlen, min_value_bitlen+60):
    mask_file = Path(FILE_MASK_PATH+"_"+str(value_bitlen)+"bits")
    offset_found = False
    print(f"Test pour la taille : {value_bitlen:04} bits")
    with mask_file.open("wb+") as file_mask:
        file_mask.write(b"\x00"*max_datafile_len)
        # pour toutes les positions des octets du fichier
        for i in range(0, max_datafile_len, READ_LEN):
            # files_bitstreams va contenir une partie de chaque fichier afin de réduire les lectures au détriment de la mémoire
            files_bitstreams = {}

            for value in filenames_grouped_by_values:
                for filename in filenames_grouped_by_values[value]: # pour chaque fichier, on regarde l'octet à la position i
                    try:
                        with Path(TESTEDFILE_PATH_FORMAT.format(filename)).open("rb") as filecontent:
                            if not value in files_bitstreams:
                                files_bitstreams[value] = []
                            filecontent.seek(i)
                            # end_len permet de finir la recherche dans les bits finaux des READ_LEN octets
                            end_len =  (value_bitlen // 8) + 1 if (value_bitlen % 8) > 0 else value_bitlen // 8
                            files_bitstreams[value].append( BitStream(filecontent.read(READ_LEN + end_len)) )
                    except FileNotFoundError:
                        total_files -= 1
                        print(f"    Fichier absent : {TESTEDFILE_PATH_FORMAT.format(filename)}")

            for offset in range( len(files_bitstreams[next(iter(files_bitstreams))][0]) - value_bitlen + 1 ):
                arr_bits_freq = []
                # Pour chaque groupe de fichiers, on compte la fréquence max d'apparition d'un suite de bits quelconque
                for value in files_bitstreams:
                    bits = []
                    for file_bitstream in files_bitstreams[value]:
                        bits.append( file_bitstream[offset: offset+value_bitlen] )
                    # frequence max d'une suite de bits quelconque
                    arr_bits_freq.append(get_max_freq( bits ))

                # arr_bits_freq contient les tuples (bits, freq) pour chaque valeurs
                total_freq = 0 # On étudie le cumul de la taille des plus grandes répétitions par valeur
                intersect_errors = 0  # On compte les erreurs pour chaque octets les plus fréquents se recoupant les uns les autres
                freq_by_values = {} # Mémorise la plus grande fréquence pour chaque répétitions groupées pour chaque valeur

                for j in range(len(arr_bits_freq)):
                    bits = arr_bits_freq[j][0]
                    freq = arr_bits_freq[j][1]

                    # pour chaque valeur on prends la frequence max pour définir la répétition principale et on cumule les autres en tant qu'erreurs
                    # mettons on a ("1111", 10), ("0000", 5), ("1111", 3) alors on a 3 intersect_errors
                    # mettons on a ("1111", 10), ("1111", 5), ("1111", 3) alors on a 3 intersect_errors + 5 intersect_errors
                    if not bits in freq_by_values:
                        freq_by_values[bits] = freq
                    else:
                        tmp = freq_by_values[bits]
                        freq_by_values[bits] = max(freq_by_values[bits], freq)
                        intersect_errors += min(tmp, freq)
                        if intersect_errors > MAX_ERRORS:
                            break
                    total_freq += freq

                # Soit l'erreur est compté comme erreur dans total_files - total_freq, et sinon dans intersect_errors
                if total_files - total_freq <= MAX_ERRORS and intersect_errors <= MAX_ERRORS:
                    offset_found = True
                    byte_offset = i + offset // 8

                    aligned_value = (offset%8)*"0"+value_bitlen*"1"
                    if len(aligned_value)%8 > 0:
                        aligned_value += (8-len(aligned_value)%8)*"0"
                    tmp_bytelen = len(aligned_value) // 8
                    
                    file_mask.seek(byte_offset)
                    aligned_value = int(aligned_value, 2) | int.from_bytes(file_mask.read(tmp_bytelen), "big")

                    file_mask.seek(byte_offset)
                    file_mask.write(aligned_value.to_bytes(tmp_bytelen, "big"))
    if not offset_found:
        mask_file.unlink()
