"""
binaries hook for pygame seems to be required for pygame 2.0 Windows.
Otherwise some essential DLLs will not be transferred to the exe.

And also put hooks for datas, resources that pygame uses, to work
correctly with pyinstaller
"""

import os
import platform

from pygame import __file__ as pygame_main_file

# Get pygame's folder
pygame_folder = os.path.dirname(os.path.abspath(pygame_main_file))

# datas is the variable that pyinstaller looks for while processing hooks
datas = []


# A helper to append the relative path of a resource to hook variable - datas
def _append_to_datas(file_path):
    res_path = os.path.join(pygame_folder, file_path)
    if os.path.exists(res_path):
        datas.append((res_path, "pygame"))


# First append the font file, then based on the OS, append pygame icon file
_append_to_datas("freesansbold.ttf")
if platform.system() == "Darwin":
    _append_to_datas("pygame_icon_mac.bmp")
else:
    _append_to_datas("pygame_icon.bmp")

if platform.system() == "Windows":
    from PyInstaller.utils.hooks import collect_dynamic_libs

    pre_binaries = collect_dynamic_libs("pygame")
    binaries = []

    for b in pre_binaries:
        binary, location = b
        # settles all the DLLs into the top level folder, which prevents duplication
        # with the DLLs already being put there.
        binaries.append((binary, "."))
