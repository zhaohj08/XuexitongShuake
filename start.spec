# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（单文件、自带全部依赖）

用法：
    python -m PyInstaller start.spec --clean --noconfirm

产物是 dist/start.exe 一个文件：
- Python 解释器、selenium/customtkinter/openai/pycryptodome/numpy 等依赖、
  task/ 下的图片/crx/字体字典/帮助/版本文件全部打进 exe；
- 运行时的可写数据（账号、Cookie、学习记录、日志）放到
  %LOCALAPPDATA%\\XuexitongShuake，exe 旁边不会生成任何文件，
  所以 exe 可以放在只读目录、桌面、U 盘里直接双击运行。

关键点：
1. datas 必须带 task/ 资源，否则启动时 Image.open("task/img/menu.png") 直接崩，
   且 --noconsole 下看不到任何报错。
2. hiddenimports 显式带上 main —— 它只在 __main__ 的 --core 分支里被 import，
   漏了会导致点“开始学习”拉起子进程时报 No module named main。
3. customtkinter 自带主题 json，必须 collect_all 收全，否则界面控件样式会丢。
4. 打包后可用 `start.exe --selftest` 自检，结果写到数据目录的 selftest.log。
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = [], [], []

for pkg in ('customtkinter',):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# selenium.webdriver 用 __getattr__ 动态 import 各浏览器驱动模块，
# PyInstaller 静态分析抓不到，漏了就会在 start_browser() 里报
# ModuleNotFoundError: No module named 'selenium.webdriver.edge.webdriver'
hiddenimports += collect_submodules('selenium')

datas += [
    ('task/img', 'task/img'),
    ('task/tool/Help.txt', 'task/tool'),
    ('task/tool/font_dict.txt', 'task/tool'),
    ('task/tool/version_info', 'task/tool'),
    ('task/tool/face_url.json', 'task/tool'),
    ('task/tool/chrome-extension.crx', 'task/tool'),
    ('task/tool/speed.crx', 'task/tool'),
    ('task/tool/zyb-227372.crx', 'task/tool'),
]
hiddenimports += ['main']

a = Analysis(
    ['start.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'matplotlib', 'pandas', 'scipy', 'IPython'],
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
    name='start',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='task/img/xuexitong1 .ico',
    version='start_version.txt',
)
