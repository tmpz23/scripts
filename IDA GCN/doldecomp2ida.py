from pathlib import Path


res_path = Path("new.py")
asm_folder = Path("20220720 - sms-master")
PREFIX = "SMS"


with res_path.open("w") as res_file:
    res_file.write("import idaapi\nimport idc\n\n")
    for path in asm_folder.glob("**/*"):
        if path.is_dir(): continue

        lines = [line for line in path.read_text().splitlines() if len(line) > 0 and \
            line != " " and line[:5] != "func_" \
            and line[:3] != "zz_"]

        for i, line in enumerate(lines):
            if line[:14]  == ".section .data" or \
                line[:14] == ".section .sbss" or \
                line[:13] == ".section .bss" or \
                line[:16] == ".section .rodata" or \
                line[:15] == ".section .ctors" or \
                line[:15] == ".section .dtors" or \
                line[:15] == ".section extab_" or \
                line[:15] == ".section .sdata":
                break
            if line[0] == ".":
                continue

            if line[:3] != "/* " and line[:4] != "lbl_":
                if line[-1] != ":":
                    raise Exception(f"Invalid label found - '{line}' {path}")
                if lines[i+1][:3] != "/* ":
                    raise Exception(f"Invalid next line format found - '{line}' {path}")

                symb_name = line[:-1]
                symb_addr = lines[i+1][3:11]
                res_file.write("MakeNameEx(0x"+symb_addr+f", \"{PREFIX}-"+symb_name+"\", SN_PUBLIC | SN_CHECK)\nMakeFunction(0x"+symb_addr+")\n")

