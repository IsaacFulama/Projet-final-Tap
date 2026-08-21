# -*- mode: python ; coding: utf-8 -*-


from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_submodules
import flask

# tkinter est installé dans le Python de base utilisé par le venv, pas dans
# `.venv\Lib`. Sans ce chemin PyInstaller peut analyser customtkinter mais
# oublier le paquet standard tkinter.
python_root = Path(sys.base_prefix)
if not (python_root / "Lib" / "tkinter").is_dir():
    python_root = Path(sys.prefix)
site_packages = Path(flask.__file__).resolve().parent.parent
tcl_data = [
    # Le hook PyInstaller pyi_rth__tkinter.py recherche précisément ces
    # deux noms dans sys._MEIPASS. Les placer dans `tcl/` provoque l'erreur
    # « Tcl data directory ... not found » au lancement de l'EXE.
    (str(python_root / "tcl" / "tcl8.6"), "_tcl_data"),
    (str(python_root / "tcl" / "tk8.6"), "_tk_data"),
]
tcl_binaries = [
    (str(python_root / "DLLs" / "tcl86t.dll"), "."),
    (str(python_root / "DLLs" / "tk86t.dll"), "."),
    # Python 3.13 peut être détecté comme une installation Tk incomplète par
    # le hook PyInstaller. Inclure explicitement l'extension standard évite
    # l'erreur « No module named tkinter » au démarrage du livrable.
    (str(python_root / "DLLs" / "_tkinter.pyd"), "."),
]
# PyInstaller 6 peut désactiver le hook tkinter quand la distribution Python
# locale ne parvient pas à initialiser Tcl. Les modules tkinter sont pourtant
# des fichiers Python purs ; les déposer dans le bundle garantit que
# customtkinter peut les importer sur le poste client.
tkinter_root = python_root / "Lib" / "tkinter"
tkinter_data = [
    (
        str(module_path),
        str(Path("tkinter") / module_path.relative_to(tkinter_root).parent),
    )
    for module_path in tkinter_root.rglob("*.py")
]

a = Analysis(
    ['main.py'],
    pathex=[str(python_root / "Lib"), str(python_root), str(site_packages)],
    binaries=tcl_binaries,
    datas=tcl_data + tkinter_data,
    hiddenimports=[
        "_tkinter",
        "tkinter",
        "tkinter.constants",
        "tkinter.font",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.simpledialog",
        "tkinter.ttk",
        # Flask est importé par la signature locale depuis une vue chargée au
        # démarrage ; PyInstaller peut le classer comme dépendance optionnelle.
        "flask",
        "werkzeug",
        "jinja2",
        "markupsafe",
        "itsdangerous",
        "click",
        # MySQL charge ses messages d'erreur par import dynamique.
        "mysql.connector.locales.eng",
        "qrcode",
        "PIL",
    ] + collect_submodules("flask") + collect_submodules("werkzeug") + collect_submodules("mysql.connector.locales"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TAP_Gestion_Loyers',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
