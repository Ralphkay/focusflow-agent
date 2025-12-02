# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets/*.ico', 'assets'),
        ('templates/*.html', 'templates'),
        ('static/*.css', 'static'),
        ('static/*.js', 'static'),
        ('.env', '.'),
    ],
    hiddenimports=[
        'sqlalchemy.sql.default_comparator',
        'sqlalchemy.ext.baked',
        'duckdb_engine',
        'pystray._win32',
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'webview.platforms.winforms',
        'clr_loader',
        'pythonnet',
        'win32gui',
        'win32process',
        'win32api',
        'win32con',
        'psutil',
        'cryptography.hazmat.backends.openssl',
        'cryptography.hazmat.primitives.kdf.scrypt',
        'openai',
        'tiktoken',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'tkinter',
        'test',
        'unittest',
        'pydoc',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FocusFlow',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\running.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FocusFlow',
)