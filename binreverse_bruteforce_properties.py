from pathlib import Path
from numbers import *

# CSV format :
    # https://gotchaforce.fandom.com/wiki/Machine_Dragon
    # 0 filename
    # 1 borgname
    # 2 Number
    # 3 Cost
    # 4 Data Crystals Required
    # 5 Tribe
    # 6 Type
    # 7 Rarity
    # 8 Has Alternate?
    # 9 Level 1 HP/Level 10 HP
    # 10 Defense
    # 11 Shot
    # 12 Attack
    # 13 Speed
    # 14 Jump Type
    # 15 Level-up Schedule


TESTEDFILE_PATH_FORMAT = "pzzu/{0}/000C_{0}data.bin"
CSV_PATH = "_autres/NTSC_borgs.csv"
MAX_ERRORS = 20


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


# Pour une valeur donnée, génère l'ensemble des encodages à tester
# Renvoie toutes ces valeurs dans une liste de tuples (bytes, nom_encodage)
# formats à tester :
#     GREY(value, bit_len)
#     BCD(value,  bit_len)
#     SA(value,   bit_len) # utile si value <= 0
#     CPL1(value, bit_len) # utile si value <= 0
#     CPL2(value, bit_len) # utile si value <= 0
#     FixedP(value, n, p) # n = partie entière ; p = partie fractionnelle
#     FloatingP(value, p, k, bias=False) # p = exposant ; k = pseudo-mantis
def get_encoded_values(value):
    encoded_tuples = []

    if type(value) != int:
        value = int(value)

    for test_value_len in range(1, 9):
        for test_value_endian in ["little", "big"]:
            if value == 0: # On ajoutes les différentes valeurs pour les 0
                encoded_tuples.append( (SA(value,   test_value_len*8)[0].to_bytes(test_value_len, test_value_endian), f"SA{test_value_len}_{test_value_endian}") )
                encoded_tuples.append( (SA(value,   test_value_len*8)[1].to_bytes(test_value_len, test_value_endian), f"SA{test_value_len}_{test_value_endian}") )
                encoded_tuples.append( (CPL1(value, test_value_len*8)[0].to_bytes(test_value_len, test_value_endian), f"CPL1{test_value_len}_{test_value_endian}") )
                encoded_tuples.append( (CPL1(value, test_value_len*8)[1].to_bytes(test_value_len, test_value_endian), f"CPL1{test_value_len}_{test_value_endian}") )
                encoded_tuples.append( (FixedP(value, test_value_len-1, 1)[0].to_bytes(test_value_len, test_value_endian), f"FixedP{test_value_len}_{test_value_endian}") )
                encoded_tuples.append( (FixedP(value, test_value_len-1, 1)[1].to_bytes(test_value_len, test_value_endian), f"FixedP{test_value_len}_{test_value_endian}") )
                encoded_tuples.append( (FloatingP(value, test_value_len-1, 1)[0].to_bytes(test_value_len, test_value_endian), f"FloatingP{test_value_len}_{test_value_endian}") )
                encoded_tuples.append( (FloatingP(value, test_value_len-1, 1)[1].to_bytes(test_value_len, test_value_endian), f"FloatingP{test_value_len}_{test_value_endian}") )
            else:
                try: encoded_tuples.append( (SA(value,   test_value_len*8).to_bytes(test_value_len, test_value_endian), f"SA{test_value_len}_{test_value_endian}") )
                except ValueError: pass
                try: encoded_tuples.append( (CPL1(value, test_value_len*8).to_bytes(test_value_len, test_value_endian), f"CPL1{test_value_len}_{test_value_endian}") )
                except ValueError: pass
                # min 2 bits pour la partie entière et 3 bits pour la partie fractionnelle
                for n in range(2, test_value_len*8-3):
                    try: encoded_tuples.append( (FixedP(value, n, test_value_len*8 - n - 1).to_bytes(test_value_len, test_value_endian), f"FixedP{test_value_len}_{test_value_endian}") )
                    except ValueError: pass
                    for flp_bias in [False, True]:
                        for pseudo_mantis in [False, True]:
                            try:
                                pm_str = "pseudo-mantis" if pseudo_mantis else ""
                                encoded_tuples.append( (FloatingP(value, n, test_value_len*8 - n - 1, pseudo_mantis=pseudo_mantis, bias=flp_bias).to_bytes(test_value_len, test_value_endian), f"FloatingP{pm_str}{test_value_len}_{test_value_endian}") )
                            except ValueError: pass
            try: encoded_tuples.append( (GREY(value,   test_value_len*8).to_bytes(test_value_len, test_value_endian), f"GREY{test_value_len}_{test_value_endian}") )
            except ValueError: pass
            try: encoded_tuples.append( (BCD(value,    test_value_len*8).to_bytes(test_value_len, test_value_endian), f"BCD{test_value_len}_{test_value_endian}") )
            except ValueError: pass
            try: encoded_tuples.append( (CPL2(value,   test_value_len*8).to_bytes(test_value_len, test_value_endian), f"CPL2{test_value_len}_{test_value_endian}") )
            except ValueError: pass
    
    # https://docs.python.org/3.6/library/codecs.html#standard-encodings
    # Strings encoding
    for encoding in ["ascii", "big5", "big5hkscs", "cp037", "cp273", "cp424", "cp437", "cp500", "cp720", "cp737", "cp775", "cp850", "cp852", "cp855", "cp856", "cp857", "cp858", "cp860", "cp861", "cp862", "cp863", "cp864", "cp865", "cp866", "cp869", "cp874", "cp875", "cp932", "cp949", "cp950", "cp1006", "cp1026", "cp1125", "cp1140", "cp1250", "cp1251", "cp1252", "cp1253", "cp1254", "cp1255", "cp1256", "cp1257", "cp1258", "cp65001", "euc_jp", "euc_jis_2004", "euc_jisx0213", "euc_kr", "gb2312", "gbk", "gb18030", "hz", "iso2022_jp", "iso2022_jp_1", "iso2022_jp_2", "iso2022_jp_2004", "iso2022_jp_3", "iso2022_jp_ext", "iso2022_kr", "latin_1", "iso8859_2", "iso8859_3", "iso8859_4", "iso8859_5", "iso8859_6", "iso8859_7", "iso8859_8", "iso8859_9", "iso8859_10", "iso8859_11", "iso8859_13", "iso8859_14", "iso8859_15", "iso8859_16", "johab", "koi8_r", "koi8_t", "koi8_u", "kz1048", "mac_cyrillic", "mac_greek", "mac_iceland", "mac_latin2", "mac_roman", "mac_turkish", "ptcp154", "shift_jis", "shift_jis_2004", "shift_jisx0213", "utf_32", "utf_32_be", "utf_32_le", "utf_16", "utf_16_be", "utf_16_le", "utf_7", "utf_8", "utf_8_sig"]:
        encoded_tuples.append( (str(value).encode(encoding), encoding+"_big") )
        encoded_tuples.append( (str(value).encode(encoding)[::-1], encoding+"_little") )
    
    return encoded_tuples

csv_lines = [csv_line.split(";") for csv_line in Path(CSV_PATH).open("r").read().split("\n")[1:]]
max_datafile_len = get_max_filelen(csv_lines)

print(f"Taille du plus petit fichier : {max_datafile_len}")

offsets = {} # On récupère tous les offsets où ça match
for csv_line in csv_lines:
    filename = csv_line[0]
    value = int(csv_line[2])
    filecontent = Path(TESTEDFILE_PATH_FORMAT.format(filename)).read_bytes()

    for (encoded_value, encoding_name) in get_encoded_values(value):
        offset = filecontent.find(encoded_value)
        if offset != -1:
            if not offset in offsets:
                offsets[offset] = {encoding_name: [filename]}
            elif not encoding_name in offsets[offset]:
                    offsets[offset][encoding_name] = [filename]
            else:
                offsets[offset][encoding_name].append(filename)

for offset in offsets:
    for encoding_name in offsets[offset]:
        if len(offsets[offset][encoding_name]) >= len(csv_lines) - MAX_ERRORS:
            print(f"offset: {offset} / {encoding_name}")
