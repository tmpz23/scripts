#!/usr/bin/env python3
from pathlib import Path
import shutil

"""
photos_path = Path()
root_file_path = Path()
root_folders_path = Path()
"""
###############################################################
# Remove .db .ini empty folders and files with len < x
###############################################################
"""
photos_path = Path()
for path in photos_path.glob("**/*.ini"):
    path.unlink()
for path in photos_path.glob("**/*.db"):
    path.unlink()
for path in photos_path.glob("**/*"):
    if path.is_file():
        if path.stat().st_size < 11038:
            path.unlink()
"""
"""
empty_folders = [path for path in photos_path.glob("**/*") if path.is_dir() and len([p for p in path.glob("**/*")]) == 0]
for p in empty_folders:
    p.rmdir()
    print(p)
"""
###############################################################
# Move folders to root folder
###############################################################
"""
allfolders = [path for path in photos_path.glob("**/*") if path.is_dir()]

for folder_path in allfolders:
    if folder_path.parent != photos_path:
        new_folder = photos_path / Path(" ---- ".join(folder_path.parts[1:]))
        if not new_folder.is_dir():
            shutil.move(folder_path, new_folder)
"""
###############################################################
# Remove duplicated
###############################################################
"""
# Remove duplicated files with a name ending by a copy str like " (2)" or "__01"
all_files = list(photos_path.glob("*"))
while len(all_files) > 0:
    #print(len(all_files))
    path = all_files.pop(0)
    for path_copy in photos_path.glob(f"{path.stem}?*"):
        if path_copy.name != path.name:
            if path_copy.read_bytes() == path.read_bytes():
                path_copy.unlink()
                print(path_copy)
                if path_copy in all_files:
                    all_files.remove(path_copy)
"""

###############################################################
# Rename (2) or _02
###############################################################
"""
# Rename files, adapt [0-9] to match others lengths (12) ...
all_files = list(photos_path.glob("**/* ([0-9]).???"))
while len(all_files) > 0:
    path = all_files.pop()
    new_file = photos_path / Path(path.parent) / Path(path.stem[:-4]).with_suffix(path.suffix)

    if not new_file.is_file():
        path.rename( new_file )
        print(path)
"""
###############################################################
# compare all files and print duplicated files in a file
###############################################################
"""
files_path = [(path, path.stat().st_size) for path in Path().glob("**/*") if path.is_file()]

results = []
count = 1

while len(files_path) > 0:
    print(f"file {count}/{len(files_path)}")
    tested_tuple = files_path.pop()
    tested_len = tested_tuple[1]
    sames_list = []
    for file_tuple in files_path:
        if tested_len == file_tuple[1]:
            if tested_tuple[0].read_bytes() == file_tuple[0].read_bytes():
                sames_list.append(file_tuple)

    # Append paths in results if len > 0:
    if len(sames_list) > 0:
        for same_tuple in sames_list:
            files_path.remove(same_tuple)
        sames_list.insert(0, tested_tuple)
        results.append( tuple(sames_list) )
    count += 1

result_txt = ""
for sames_tuple in results:
    result_txt += "[\n"
    for same_tuple in sames_tuple:
        result_txt += f"    {same_tuple[0]}\n"
    result_txt += "]"

Path("duplicated_files.txt").write_text(result_txt)
print("Fini !")
"""
###############################################################
# compare files and print same files when they are in two different folders
###############################################################
"""
files_path = [(path, path.stat().st_size) for path in Path().glob("**/*") if path.is_file()]

results = []
count = 1

while len(files_path) > 0:
    print(f"file {count}/{len(files_path)}")
    tested_tuple = files_path.pop()
    tested_len = tested_tuple[1]
    sames_list = []
    for file_tuple in files_path:
        if tested_len == file_tuple[1]:
            if tested_tuple[0].parent != file_tuple[0].parent:
                if tested_tuple[0].read_bytes() == file_tuple[0].read_bytes():
                    sames_list.append(file_tuple)

    # Append paths in results if len > 0:
    if len(sames_list) > 0:
        for same_tuple in sames_list:
            files_path.remove(same_tuple)
        sames_list.insert(0, tested_tuple)
        results.append( tuple(sames_list) )
    count += 1

result_txt = ""
for sames_tuple in results:
    result_txt += "[\n"
    for same_tuple in sames_tuple:
        result_txt += f"    {same_tuple[0]}\n"
    result_txt += "]"

Path("duplicated_files.txt").write_text(result_txt)
print("Fini !")
"""
###############################################################
# compare 2 folders and print duplicated folders in file
###############################################################
"""
def folder_compare(folder1:Path, folder2:Path):
    files1_tuples = [(path, path.stat().st_size) for path in folder1.glob("**/*") if path.is_file()]
    files2_tuples = [(path, path.stat().st_size) for path in folder2.glob("**/*") if path.is_file()]

    while len(files1_tuples) > 0:
        tested_tuple = files1_tuples.pop()
        tested_len = tested_tuple[1]
        sames_list = []
        for file_tuple in files2_tuples:
            if tested_len == file_tuple[1]:
                if tested_tuple[0].read_bytes() == file_tuple[0].read_bytes():
                    sames_list.append(file_tuple)
        if len(sames_list) > 0:
            for same_tuple in sames_list:
                files2_tuples.remove(same_tuple)
    if len(files2_tuples) > 0:
        return False
    return True

folders_tuples = [(path, len([p for p in path.glob("**/*") if p.is_file()])) for path in folder_path.glob("**/*") if path.is_dir()]
results = []
count = 1

while len(folders_tuples) > 0:
    print(f"folders {count}/{len(folders_tuples)}")
    tested_tuple = folders_tuples.pop()
    tested_len = tested_tuple[1]
    sames_list = []
    for folder_tuple in folders_tuples:
        if tested_len == folder_tuple[1]:
            if folder_compare(tested_tuple[0], folder_tuple[0]) and folder_compare(folder_tuple[0], tested_tuple[0]):
                sames_list.append(folder_tuple)

    # Append paths in results if len > 0:
    if len(sames_list) > 0:
        for same_tuple in sames_list:
            folders_tuples.remove(same_tuple)
        sames_list.insert(0, tested_tuple)
        results.append( tuple(sames_list) )
    count += 1

result_txt = ""
for sames_tuple in results:
    result_txt += "[\n"
    for same_tuple in sames_tuple:
        result_txt += f"    {same_tuple[0]}\n"
    result_txt += "]"
Path("duplicated_folders.txt").write_text(result_txt)
print("Fini !")
"""
###############################################################
# Delete file present in second folder if already in first
###############################################################
"""
original_path = Path()
dropbox_path = Path()


original_file_tuples =  [(path, path.stat().st_size) for path in original_path.glob("**/*") if path.is_file()]
dropbox_file_tuples =  [(path, path.stat().st_size) for path in dropbox_path.glob("**/*") if path.is_file()]

count = 1

while len(original_file_tuples) > 0:
    print(f"file {count}/{len(original_file_tuples)}")
    tested_tuple = original_file_tuples.pop()
    tested_len = tested_tuple[1]
    sames_list = []
    for dropbox_file_tuple in dropbox_file_tuples:
        if tested_len == dropbox_file_tuple[1]:
            if tested_tuple[0].read_bytes() == dropbox_file_tuple[0].read_bytes():
                sames_list.append(dropbox_file_tuple)
                dropbox_file_tuple[0].unlink()
                print(f"Removing {dropbox_file_tuple[0]}")
    # Append paths in results if len > 0:
    if len(sames_list) > 0:
        for same_tuple in sames_list:
            dropbox_file_tuples.remove(same_tuple)
    count += 1

print("Fini !")
"""
###############################################################
# List empty folders
###############################################################
"""
paths = [path for path in folder_path.glob("**/*") if path.is_dir() and len([p for p in path.glob("**/*")]) == 0]

for path in paths:
    print(path)
"""

###############################################################
# Create folders and move files
###############################################################

#path.rename( new_file )

"""
files_tomove_paths = [(path, path.stat().st_size) for path in Path().glob("**/*") if path.is_file()]
files_toanalyse_paths = [(path, path.stat().st_size) for path in Path().glob("**/*") if path.is_file()]

dest_path = Path()
count = 1

while len(files_tomove_paths) > 0:
    print(f"file {count}/{len(files_tomove_paths)}")
    move_tuple = files_tomove_paths.pop()
    move_len = move_tuple[1]
    for analyse_tuple in files_toanalyse_paths:
        if move_len == analyse_tuple[1]:
            if move_tuple[0].read_bytes() == analyse_tuple[0].read_bytes():
                dest_folder = dest_path / analyse_tuple[0].parent
                dest_folder.mkdir(parents=True, exist_ok=True)
                move_tuple[0].rename(dest_folder / move_tuple[0].name)
                break
    count += 1

print("Fini !")
"""
