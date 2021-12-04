# implémenter Aiken
# implémenter binaire excédant 3
# tester avec une implémentation IEEE 754 <- les floats python ?
####################################################
# UNSIGNED
####################################################
# Retourne la valeur encodée en GROS GRAY
def GREY(value:int, bit_len:int):
    if value < 0 or value > 2**bit_len-1:
        raise ValueError()
    bin_val = bin(value)[2:]
    grey = bin_val[0]
    for i in range(1, len(bin_val)):
        if bin_val[i-1] == bin_val[i]:
            grey += "0"
        else:
            grey += "1"
    return int(grey, 2)


# Retourne la valeur encodée en BCD
def BCD(value:int, bit_len:int, bin_str:str = ""):
    digits = str(value)
    if value < 0  or len(digits)*4 > bit_len:
        raise ValueError()
    
    if len(digits) > 1:
        return BCD(int(digits[:-1]), bit_len, "{0:04b}".format(int(digits[-1:])) + bin_str)
    bin_str = "{0:04b}".format(int(digits[-1:])) + bin_str
    return int(bin_str, 2)

####################################################
# SIGNED
####################################################
# Sign Absolute value
# Deux représentations de 0 :
#     bit_len * "0"
#     "1" + (bit_len-1) * "0"
def SA(value:int, bit_len:int):
    if value < -(2**(bit_len-1)-1) or value > 2**(bit_len-1)-1:
        raise ValueError()
    if value > 0:
        return value
    if value == 0:
        return [0, 1 << (bit_len - 1)]
    return abs(value) | 1 << (bit_len - 1)


# Deux représentations de 0 :
#     bit_len * "0"
#     "1" + (bit_len-1) * "0"
def CPL1(value:int, bit_len:int):
    if value < -(2**(bit_len-1)-1) or value > 2**(bit_len-1)-1:
        raise ValueError()
    if value < 0:
        return ~abs(value) & int("1"*bit_len, 2)
    if value == 0:
        return [0, 1 << (bit_len - 1)]
    return value


def CPL2(value:int, bit_len:int):
    if value < -2**(bit_len-1) or value > 2**(bit_len-1)-1:
        raise ValueError()
    if value < 0:
        return (~abs(value) + 1) & int("1"*bit_len, 2)
    return value

####################################################
# DECIMAL
####################################################
# Renvoie la partie fractionnaire en inverse(multiples de 2) au format "01..."
#     Si depth est initialisé à 1, on compte le nombre de bits dès le premier bit à 1 pour la taille
def decimal_bin(decimal:float, bit_len:int, n:int = 1, depth:int = 0):
    if decimal >= 1.0 or decimal < 0.0:
        raise ValueError()
    if depth-1 == bit_len or depth == 0 and n > bit_len:
        return ""
    elif decimal == 0.0:
        if depth == 0:
            return "0"*(bit_len-n+1)
        else:
            return "0"*(bit_len-depth+1)
    if decimal >= 1/2**n:
        if depth > 0:
            depth += 1
        return "1"+decimal_bin(decimal-1/(2**n), bit_len, n+1, depth)
    if depth > 1:
        depth += 1
    return "0"+decimal_bin(decimal, bit_len, n+1, depth)

# Fixed Point number
# signe (1 bit) ; partie entière (n bits) ; partie fractionnelle (p bits)
# Deux représentations de 0 :
#     bit_len * "0"
#     "1" + (bit_len-1) * "0"
def FixedP(value:float, n:int, p:int):
    if value == 0:
        return [0, 1 << (n+p)]
    if value < 0:
        sign = "1"
    else:
        sign = "0"
    int_value = int(abs(value))

    if int_value > 2**n-1:
        raise ValueError()
    decimal_bits = decimal_bin(abs(value) - int_value, p)
    return int( (sign+"{0:0"+str(n)+"b}{1:0"+str(p)+"b}").format(int_value, int(decimal_bits, 2)), 2)


# Floating Point number
# signe (1 bit) ; exposant (p bits) ; mantisse (k bits)
# Deux représentations de 0 : "1"+"0"*(p+k) et "0"*(1+p+k)
# Les valeurs NaN et infini ne sont pas implémentées (spécifique IEEE 754)
# Les nombre dénormalisés sont à tester (voisinage de 0)
# Les arrondis aussi sont à implémenter
# Deux représentations de 0 :
#     bit_len * "0"
#     "1" + (bit_len-1) * "0"
def FloatingP(value:float, p:int, k:int, pseudo_mantis:bool = True, bias:bool = False):
    if value == 0.0:
        return [0, 1<<(p+k)]
    exposant = 0
    int_value = abs(int(value))
    mantis_bits = ""

    if value < 0:
        sign = "1"
    else:
        sign = "0"

    if int_value > 0:
        mantis_bits = bin(int_value)[2:]
        exposant += len(bin(int_value)[2:])
    if abs(value) - int_value > 0.0:
        mantis_bits += decimal_bin(abs(value) - int_value, k, depth=1)

    if "1" in mantis_bits:
        while mantis_bits[0] == "0":
            mantis_bits = mantis_bits[1:]
            exposant -= 1
        if pseudo_mantis:
            mantis_bits = mantis_bits[1:]
            exposant -= 1

    if len(mantis_bits) > k:
        mantis_bits = mantis_bits[:k]
    else:
        mantis_bits = mantis_bits.ljust(k, "0")

    if not bias:
        exposant = CPL2(exposant, p)
    else:
        exposant = exposant + 2**(p-1)-1
    if len(bin(exposant)[2:]) > p:
        raise ValueError()
    return int( (sign+"{0:0"+str(p)+"b}{1:0"+str(k)+"b}").format(exposant, int(mantis_bits, 2)), 2)


"""
#########################################################################
# TESTS
#########################################################################
if decimal_bin(0.123456, 10)          != "0001111110":    print("Erreur 1")
if decimal_bin(0.123456, 10, depth=1) != "0001111110011": print("Erreur 2")
if decimal_bin(0.0,      10)          != "0000000000":    print("Erreur 3")
if decimal_bin(0.0,      10, depth=1) != "0000000000":    print("Erreur 4")
if f"{GREY(0, 8):08b}"     != "00000000":         print("Erreur 5")
if f"{GREY(546, 12):016b}" != "0000001100110011": print("Erreur 6")
if f"{BCD(0, 8):08b}"      != "00000000":         print("Erreur 7")
if f"{BCD(9876543210, 40):040b}" != "1001100001110110010101000011001000010000": print("Erreur 8")
if f"{SA(0, 8)[0]:08b}"    != "00000000": print("Erreur 9.1")
if f"{SA(0, 8)[1]:08b}"    != "10000000": print("Erreur 9.2")
if f"{SA(127, 8):08b}"     != "01111111": print("Erreur 10")
if f"{SA(-127, 8):08b}"    != "11111111": print("Erreur 11")
try: SA(-128, 8); print("Erreur 12");
except: pass
try: SA(128, 8);  print("Erreur 13");
except: pass
if f"{CPL1(0, 8)[0]:08b}"  != "00000000": print("Erreur 14.1")
if f"{CPL1(0, 8)[1]:08b}"  != "10000000": print("Erreur 14.2")
if f"{CPL1(127,  8):08b}"  != "01111111": print("Erreur 15")
if f"{CPL1(-127, 8):08b}"  != "10000000": print("Erreur 16")
try: CPL1(-128, 8); print("Erreur 17");
except: pass
try: CPL1(128, 8);  print("Erreur 18");
except: pass
if f"{CPL2(0,    8):08b}"  != "00000000": print("Erreur 19")
if f"{CPL2(-128, 8):08b}"  != "10000000": print("Erreur 20")
if f"{CPL2(127,  8):08b}"  != "01111111": print("Erreur 21")
try: CPL2(-129, 8); print("Erreur 22");
except: pass
try: CPL2(128, 8);  print("Erreur 23");
except: pass
if f"{FixedP(0.0,    5, 5)[0]:011b}" != "00000000000": print("Erreur 24.1")
if f"{FixedP(0.0,    5, 5)[1]:011b}" != "10000000000": print("Erreur 24.2")
if f"{FixedP(31.96875,  5, 5):011b}" != "01111111111": print("Erreur 25")
if f"{FixedP(-31.96875, 5, 5):011b}" != "11111111111": print("Erreur 26")
#try: FixedP(31.96876,  5, 5); print("Erreur 27");
#except: pass
try: FixedP(32.96875,   5, 5);  print("Erreur 27");
except: pass
try: FixedP(-32.96875,  5, 5);  print("Erreur 28");
except: pass
if f"{FloatingP(0.0,    5, 5)[0]:011b}" != "00000000000": print("Erreur 29.1")
if f"{FloatingP(0.0,    5, 5)[1]:011b}" != "10000000000": print("Erreur 29.2")
if f"{FloatingP(31.96875,  5, 5):011b}" != "00010011111": print("Erreur 30") # exposant = 4; mantis = 11111
if f"{FloatingP(-31.96875, 5, 5):011b}" != "10010011111": print("Erreur 31")
if f"{FloatingP(31.96875,  5, 10):016b}"!= "0001001111111110": print("Erreur 32")
if f"{FloatingP(-31.96875, 5, 15):021b}"!= "100100111111111000000": print("Erreur 33")
#try: FloatingP(32.96875,   5, 5);  print("Erreur 34");
#except: pass
#try: FloatingP(-32.96875,  5, 5);  print("Erreur 35");
#except: pass
if f"{FloatingP(-31.96875, 5, 15):021b}"!= "100100111111111000000": print("Erreur 33")
# https://perso.liris.cnrs.fr/hamid.ladjal/LIFASR3/Supports/CM4.pdf#page=51
#if f"{FloatingP(0.025,  4, 8, pseudo_mantis=False):013b}" != "0101111010000": print("Erreur 34") # Erreur arrondi ?
if f"{FloatingP(-13.01, 4, 8, pseudo_mantis=False):013b}" != "1010011010000": print("Erreur 35")
#if f"{FloatingP(0.025,  4, 8, bias=True, pseudo_mantis=False):013b}" != "0101111010000": print("Erreur 36") # Erreur arrondi ?
#if f"{FloatingP(-13.01, 4, 11, bias=True, pseudo_mantis=False):016b}" != "0110011010000010": print("Erreur 37") # idem <- erreur = 0.0022 et sur le pdf erreur = 0.0056
# http://n.grassa.free.fr/sysrezo/CorrectionRepInfoTD2.pdf
# IEEE 754
if f"{FloatingP(8.625,       8, 23, bias=True):032b}" != "01000001000010100000000000000000": print("Erreur 38")
if f"{FloatingP(873731.0625, 8, 23, bias=True):08x}"  != "49555031": print("Erreur 39")
if f"{FloatingP(0.4375,      8, 23, bias=True):032b}" != "00111110111000000000000000000000": print("Erreur 40")
if f"{FloatingP(0.0625,      8, 23, bias=True):032b}" != "00111101100000000000000000000000": print("Erreur 41")
if f"{FloatingP(0.5,         8, 23, bias=True):08x}"  != "3f000000": print("Erreur 42")
if f"{FloatingP(-262144,     8, 23, bias=True):08x}"  != "c8800000": print("Erreur 43")
if f"{FloatingP(-131072,     8, 23, bias=True):08x}"  != "c8000000": print("Erreur 44")
if f"{FloatingP(-(1*(2**18)+1*2**17), 8, 23, bias=True):08x}"  != "c8c00000": print("Erreur 45")
if f"{FloatingP(128,         8, 23, bias=True):032b}" != "01000011000000000000000000000000": print("Erreur 46")
if f"{FloatingP(-32.75,      8, 23, bias=True):032b}" != "11000010000000110000000000000000": print("Erreur 47")
if f"{FloatingP(18.125,      8, 23, bias=True):032b}" != "01000001100100010000000000000000": print("Erreur 48")
if f"{FloatingP(-0.046875,   8, 23, bias=True):032b}" != "10111101010000000000000000000000": print("Erreur 49")
#if f"{FloatingP(1.539*10**13,8, 23, bias=True):032b}" != "01010101011000000000000000000000": print("Erreur 50") # Erreur d'arrondi ! -(1.0 * 2**18 + 1.0 * 2**17)
if f"{FloatingP(-30.0,       8, 23, bias=True):032b}" != "11000001111100000000000000000000": print("Erreur 51")
if f"{FloatingP(45.125,      4, 6,  bias=True):011b}" != "01100011010": print("Erreur 52")
if f"{FloatingP(-12.0625,    4, 6,  bias=True):011b}" != "11010100000": print("Erreur 53")
"""
