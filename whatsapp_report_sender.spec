# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Collecte automatique et robuste de tous les sous-modules de votre package local 'tap'
# Cela évite d'avoir à l'écrire manuellement à chaque ajout de fichier dans tap/
hiddenimports = (
    collect_submodules("tap")
    + ["mysql.connector", "mysql.connector.locales.eng"]
    + collect_submodules("mysql.connector.locales")
)

# Gestion des fichiers de données requis par les bibliothèques tierces (si nécessaire)
python_root = Path(sys.base_prefix)
if not (python_root / "Lib" / "tkinter").is_dir():
    python_root = Path(sys.prefix)

tcl_data = [
    (str(python_root / "tcl" / "tcl8.6"), "_tcl_data"),
    (str(python_root / "tcl" / "tk8.6"), "_tk_data"),
]
tcl_binaries = [
    (str(python_root / "DLLs" / "tcl86t.dll"), "."),
    (str(python_root / "DLLs" / "tk86t.dll"), "."),
    (str(python_root / "DLLs" / "_tkinter.pyd"), "."),
]
tkinter_root = python_root / "Lib" / "tkinter"
tkinter_data = [
    (
        str(module_path),
        str(Path("tkinter") / module_path.relative_to(tkinter_root).parent),
    )
    for module_path in tkinter_root.rglob("*.py")
]

datas = tcl_data + tkinter_data

# ATTENTION : Si config.json doit être modifiable par l'utilisateur à côté de l'EXE,
# NE l'incluez PAS dans datas. Laissez-le simplement dans le même dossier que l'EXE généré.
# Si c'est un fichier de config interne immuable, décommentez la ligne ci-dessous :
# datas += [("config.json", ".")]

a = Analysis(
    ["whatsapp_report_sender.py"],
    pathex=["."],
    binaries=tcl_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "django",
        "mysql.ai",
        "mysql.connector.aio",
        "mysql.connector.django",
    ],
    noarchive=False,
    optimize=1,          # Passage à 1 pour retirer les assertions et optimiser légèrement le bytecode
)

_icon_path = Path.cwd() / "tap.ico"
if not _icon_path.is_file():
    _icon_path = Path.cwd() / ".." / "tap.ico"

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="whatsapp_report_sender",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    icon=str(_icon_path) if _icon_path.is_file() else None,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
