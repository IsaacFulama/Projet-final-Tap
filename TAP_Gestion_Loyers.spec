# -*- mode: python ; coding: utf-8 -*-


from pathlib import Path

python_root = Path(r"C:\Users\Ir FLM\AppData\Local\Programs\Python\Python313")
tcl_data = [
    (str(python_root / "tcl" / "tcl8.6"), "tcl"),
    (str(python_root / "tcl" / "tk8.6"), "tcl"),
]
tcl_binaries = [
    (str(python_root / "DLLs" / "tcl86t.dll"), "."),
    (str(python_root / "DLLs" / "tk86t.dll"), "."),
    # Python 3.13 peut être détecté comme une installation Tk incomplète par
    # le hook PyInstaller. Inclure explicitement l'extension standard évite
    # l'erreur « No module named tkinter » au démarrage du livrable.
    (str(python_root / "DLLs" / "_tkinter.pyd"), "."),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=tcl_binaries,
    datas=tcl_data,
    hiddenimports=[
        "_tkinter",
        "tkinter",
        "tkinter.constants",
        "tkinter.font",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.simpledialog",
        "tkinter.ttk",
    ],
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
