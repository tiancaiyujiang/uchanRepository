# -*- mode: python ; coding: utf-8 -*-
import os

# 以 .spec 文件所在目录为基准，便于在其他机器上打包
spec_dir = os.path.abspath(SPECPATH)

a = Analysis(
    [os.path.join(spec_dir, 'main.py')],
    pathex=[spec_dir],
    binaries=[],
    datas=[(os.path.join(spec_dir, 'templates'), 'templates')],
    hiddenimports=[],
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
    name='CobolGenerater',
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
    icon='NONE',
)
