# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules


python_root = Path(sys.base_prefix)
if not (python_root / "tcl" / "tcl8.6").is_dir():
    python_root = Path(sys.prefix)

tcl_data = []
for runtime_name in ("tcl8.6", "tk8.6"):
    runtime_root = python_root / "tcl" / runtime_name
    destination_root = "_tcl_data" if runtime_name.startswith("tcl") else "_tk_data"
    for runtime_file in runtime_root.rglob("*"):
        if runtime_file.is_file():
            relative = runtime_file.relative_to(runtime_root).as_posix()
            tcl_data.append((str(runtime_file), f"{destination_root}/{relative}"))

tcl_binaries = [
    (str(python_root / "DLLs" / "tcl86t.dll"), "."),
    (str(python_root / "DLLs" / "tk86t.dll"), "."),
    (str(python_root / "DLLs" / "_tkinter.pyd"), "."),
]

a = Analysis(
    ["../main.py"],
    pathex=[".."],
    binaries=tcl_binaries,
    datas=tcl_data,
    hiddenimports=[
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        "tkinter.filedialog",
        "tkinter.simpledialog",
        "tkinter.font",
        "tkinter.constants",
        "_tkinter",
        "mysql.connector.locales.eng",
        "mysql.connector.locales",
    ] + collect_submodules("mysql.connector.locales"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["packaging/tk_runtime_hook.py"],
    excludes=[],
    noarchive=False,
    optimize=0,
)

tkinter_root = python_root / "Lib" / "tkinter"
for module_path in tkinter_root.glob("*.py"):
    module_name = "tkinter" if module_path.name == "__init__.py" else f"tkinter.{module_path.stem}"
    a.pure.append((module_name, str(module_path), "PYMODULE"))

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TAP_Gestion_Loyers",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="TAP_Gestion_Loyers",
)
