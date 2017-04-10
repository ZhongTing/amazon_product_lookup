import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {
	"silent": False,
	"packages": ["os", 'lxml', 'gzip'],
	"excludes": ["tkinter"]
}

# GUI applications require a different base on Windows (the default is for a
# console application).
base = None
# if sys.platform == "win32":
    # base = "Win32GUI"

setup(  name = "amazon product lookuper",
        version = "0.1",
        description = "amazon product lookup",
        options = {"build_exe": build_exe_options},
        executables = [Executable("amazon.py", base=base)])
