from pathlib import Path
import random

# Create random files
FILE_LEN = 1240
for i in range(207):
    with Path(f"mask_test/{i}").open("wb") as test:
        for j in range(FILE_LEN):
            test.write( random.randint(0, 255).to_bytes(1, "big") )
        

#############################################################
# Ajoute la même valeur au même offset pour tous les fichiers
#############################################################
value = random.randint(0, 255).to_bytes(1, "big")+random.randint(0, 255).to_bytes(1, "big")+random.randint(0, 255).to_bytes(1, "big")+random.randint(0, 255).to_bytes(1, "big")
offset = random.randint(0+100, FILE_LEN-40)

for i in range(207):
    with Path(f"mask_test/{i}").open("rb+") as test:
        test.seek(offset)
        test.write( value )

# Ajoute des valeurs corrélées en créant aussi le fichier csv
bitlen = 11
values = []
for i in range(20): # On prends 20 valeurs différentes pour en assigner une à chaque fichier
    values.append( random.randint(0, 2000) )

with Path("mask_test/test.csv").open("w") as csv_file:
    csv_file.write("filename;cost")
    bit_offset = random.randint(0, 7)
    #print(f"bit_offset:{bit_offset}")
    for i in range(207):
        value = values[random.randint(0, 19)]
        csv_file.write(f"\n{i};{value}")

        with Path(f"mask_test/{i}").open("rb+") as test:
            #############################################################
            # On ajoute en position 0
            #############################################################
            test.seek(0)
            byte_len = bitlen // 8
            if bitlen % 8 > 0:
                byte_len += 1
            old_val = int.from_bytes(test.read(byte_len), "big")
            aligned_value = (value << (byte_len*8-bitlen)) | ( old_val & int((8-bitlen%8)*"1", 2))
            #print(f"{i:03}:old_val:{old_val:016b}:value:{value:011b}:aligned:{aligned_value:016b}")
            test.seek(0)
            test.write(aligned_value.to_bytes(byte_len, "big"))
            

            #############################################################
            # On ajoute en position 50 + bit_offset
            #############################################################
            tmp_mask = "1"*bit_offset + "0"*bitlen
            tmp_value = value
            if (bitlen+bit_offset)%8 > 0:
                tmp_mask += "1"*(8 - ((bitlen+bit_offset)%8))
                tmp_value <<= (8 - ((bitlen+bit_offset)%8))
            tmp_bytelen = len(tmp_mask) // 8
            tmp_mask = int(tmp_mask, 2)

            test.seek(50)
            old_val = int.from_bytes(test.read(tmp_bytelen), "big")
            #print(("{0:03}:old:{1:0"+str(tmp_bytelen*8)+"b}:value:{2:0"+str(bitlen)+"b}").format(i, old_val, value))
            old_val &= tmp_mask

            aligned_value = tmp_value | old_val

            test.seek(50)
            test.write(aligned_value.to_bytes(tmp_bytelen, "big"))

            #############################################################
            # On ajoute en position finale
            #############################################################
            tmp_bytelen = bitlen // 8
            if bitlen%8 > 0:
                tmp_bytelen += 1
            test.seek(FILE_LEN - tmp_bytelen)

            tmp_mask = int("1"*(tmp_bytelen*8 - bitlen) +"0"*bitlen, 2)
            old_val = int.from_bytes(test.read(tmp_bytelen), "big") & tmp_mask
            #print(("{0:03}:old_value:{1:0"+str(tmp_bytelen*8)+"b}:value:{2:0"+str(bitlen)+"b}").format(i, old_val, value), end="")
            aligned_value = value | old_val
            #print(f"aligned:{aligned_value:04x}")
            test.seek(FILE_LEN - tmp_bytelen)
            test.write(aligned_value.to_bytes(tmp_bytelen, "big"))
