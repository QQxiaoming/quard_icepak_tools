from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(__file__).resolve().parent
tool_packages = [
    child.name
    for child in project_root.iterdir()
    if child.is_dir() and child.name.endswith("_tool") and (child / "manifest.py").exists()
]

datas = []
hiddenimports = []

for package_name in tool_packages:
    hiddenimports.extend(collect_submodules(package_name))
    datas.extend((str(path), package_name) for path in (project_root / package_name).glob("*.tcl"))


a = Analysis(
    ['quard_icepak_tools.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='quard_icepak_tools',
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