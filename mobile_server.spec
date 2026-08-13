# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules


a = Analysis(
    ['mobile_server.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=collect_submodules('tap.mobile') + [
        'mysql.connector',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Le serveur mobile est une application console/web : il ne doit pas
    # embarquer Tkinter ni son runtime Tcl/Tk. Sinon PyInstaller ajoute
    # pyi_rth__tkinter.py et l'EXE échoue si le dossier Tcl n'existe pas.
    excludes=[
        'customtkinter',
        'matplotlib',
        'tkinter',
        '_tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'tkinter.simpledialog',
        'tkinter.font',
        'tkinter.constants',
    ],
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
    name='TAP_Mobile_Server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
