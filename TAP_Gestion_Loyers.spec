# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import tcl_tk

block_cipher = None

tcl_root = f"{sys.base_prefix}\\tcl"
os.environ.setdefault("TCL_LIBRARY", f"{tcl_root}\\tcl8.6")
os.environ.setdefault("TK_LIBRARY", f"{tcl_root}\\tk8.6")
tcl_tk.tcltk_info.available = True
tcl_tk.tcltk_info.data_files = []

hiddenimports = [
    'tap',
    'tap.config',
    'tap.config.theme',
    'tap.config.settings',
    'tap.core',
    'tap.core.utils',
    'tap.infrastructure',
    'tap.infrastructure.database',
    'tap.presentation',
    'tap.presentation.bootstrap',
    'tap.presentation.components.widgets',
    'tap.presentation.dialogs.login',
    'tap.presentation.dialogs.formulaire',
    'tap.presentation.dialogs.export_pdf',
    'tap.presentation.views.main_window',
    'customtkinter',
    'mysql.connector',
    'fpdf',
    'matplotlib',
    'matplotlib.backends.backend_tkagg',
    'PIL',
    'PIL._tkinter_finder',
    'tkinter',
    'tkinter.constants',
    'tkinter.filedialog',
    'tkinter.font',
    'tkinter.messagebox',
    'tkinter.simpledialog',
    'tkinter.ttk',
    '_tkinter',
] + collect_submodules('customtkinter')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('config.json', '.'),
        (f'{tcl_root}\\tcl8.6', '_tcl_data'),
        (f'{tcl_root}\\tk8.6', '_tk_data'),
        (f'{tcl_root}\\tcl8', 'tcl8'),
        (f'{tcl_root}\\reg1.3', 'reg1.3'),
        (f'{tcl_root}\\dde1.4', 'dde1.4'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
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
    icon=None,
)
