from pathlib import Path


with Path("generated_symbol_map.py").open("w") as res_file:
    res_file.write("import idaapi\nimport idc\n\n")
    for path in Path("20220710_gnt4").glob("**/*"):
        if path.is_dir(): continue

        lines = [line for line in path.read_text().splitlines() if len(line) > 0 and line[0] != "."]

        for i, line in enumerate(lines):
            if line[:3] != "/* " and line[:4] != "lbl_":
                if line[-1] != ":":
                    raise Exception(f"Invalid label found - {line}")
                if lines[i+1][:3] != "/* ":
                    raise Exception(f"Invalid next line format found - {line}")

                symb_name = line[:-1]
                symb_addr = lines[i+1][3:11]
                res_file.write("MakeNameEx(0x"+symb_addr+", \"GNT4-"+symb_name+"\", SN_PUBLIC | SN_CHECK)\nMakeFunction(0x"+symb_addr+")\n")
