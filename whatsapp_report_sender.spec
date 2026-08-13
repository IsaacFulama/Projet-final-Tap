# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Collecte automatique et robuste de tous les sous-modules de votre package local 'tap'
# Cela évite d'avoir à l'écrire manuellement à chaque ajout de fichier dans tap/
hiddenimports = collect_submodules("tap") + ["mysql.connector"]

# Gestion des fichiers de données requis par les bibliothèques tierces (si nécessaire)
datas = []

# ATTENTION : Si config.json doit être modifiable par l'utilisateur à côté de l'EXE,
# NE l'incluez PAS dans datas. Laissez-le simplement dans le même dossier que l'EXE généré.
# Si c'est un fichier de config interne immuable, décommentez la ligne ci-dessous :
# datas += [("config.json", ".")]

a = Analysis(
    ["whatsapp_report_sender.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",       # Exclure CustomTkinter/Tkinter si ce script CLI n'utilise pas l'IHM
        "unittest",      # Évite d'embarquer les modules de tests unitaires
        "django",
        "mysql.ai",
        "mysql.connector.aio",
        "mysql.connector.django",
    ],
    noarchive=False,
    optimize=1,          # Passage à 1 pour retirer les assertions et optimiser légèrement le bytecode
)

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
    upx=True,            # Compression UPX activée (assurez-vous d'avoir upx.exe dans votre PATH)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,        # Indispensable pour voir les logs du Planificateur de tâches Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
