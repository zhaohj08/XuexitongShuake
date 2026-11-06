"""统一路径解析：只读资源 / 可写数据 / 用户数据目录。

打包成单文件 exe 后：
- ASSETS   ：PyInstaller 解压出来的只读资源（_MEIPASS/task），进程退出即删除；
- DATA_ROOT：%LOCALAPPDATA%\\XuexitongShuake，配置、Cookie、记录、日志都放这里。

因此 exe 不会在自身目录旁边写任何东西：放在只读目录、桌面、甚至 U 盘里都能直接运行。

源码运行（未打包）时两者都落在项目 task/ 下，保持原有习惯。

多账号并发时每个账号还有自己的 HOME（由子进程环境变量 XXT_HOME 指定），
账号之间互不干扰。
"""
from __future__ import annotations

import os
import shutil
import sys


APP_NAME = 'XuexitongShuake'
RECORD_DIR = 'record'
TOOL_DIR = 'tool'
RUN_DIR = 'run'

# 老版本（数据放在 exe 同目录 task/ 下）搬过来时需要带走的内容
_MIGRATE_SUBS = (TOOL_DIR, RECORD_DIR, RUN_DIR, 'data')
_MIGRATE_FILES = ('输出记录.log', 'error.log')


def is_frozen() -> bool:
    """是不是 PyInstaller 打包后的单文件程序。"""
    return bool(getattr(sys, 'frozen', False))


def app_root() -> str:
    """程序根目录：打包后是 exe 所在目录，源码运行时是项目根目录。"""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _assets_root() -> str:
    if is_frozen():
        # 单文件模式下资源在临时解压目录里，只读且随进程退出消失
        return os.path.join(getattr(sys, '_MEIPASS', app_root()), 'task')
    return os.path.join(app_root(), 'task')


def _data_root() -> str:
    # 部署到服务器时用 XXT_DATA 把数据/日志指到 /var/lib/xxt 这类目录
    override = os.environ.get('XXT_DATA')
    if override:
        return override
    if not is_frozen():
        # 源码运行保持原样：数据还在项目 task/ 下
        return os.path.join(app_root(), 'task')
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    return os.path.join(base, APP_NAME)


ASSETS = _assets_root()
DATA_ROOT = _data_root()
HOME = os.environ.get('XXT_HOME') or DATA_ROOT


def asset(*parts: str) -> str:
    """只读资源路径，如 asset('img', 'menu.png')。"""
    return os.path.join(ASSETS, *parts)


def data(*parts: str) -> str:
    """可写数据路径（当前 HOME），如 data('tool', 'account_info.json')。"""
    return os.path.join(HOME, *parts)


def record(*parts: str) -> str:
    """学习/成绩记录路径，如 record('《课程》的学习记录.txt')。"""
    return os.path.join(HOME, RECORD_DIR, *parts)


def root_data(*parts: str) -> str:
    """数据根目录下的文件，如 root_data('error.log')。"""
    return os.path.join(DATA_ROOT, *parts)


def data_or_asset(*parts: str) -> str:
    """优先用数据目录里的副本，没有就用打包进来的只读资源。"""
    path = data(*parts)
    return path if os.path.exists(path) else asset(*parts)


def ensure_data_dirs() -> None:
    """确保可写目录存在，避免首跑时 open() 失败。"""
    for base in (HOME, DATA_ROOT):
        try:
            os.makedirs(base, exist_ok=True)
        except OSError:
            pass
    for sub in (TOOL_DIR, RECORD_DIR, RUN_DIR):
        try:
            os.makedirs(os.path.join(HOME, sub), exist_ok=True)
        except OSError:
            pass


def account_home(account_id: str) -> str:
    """某个账号的工作目录（由主进程计算，子进程通过 XXT_HOME 拿到）。"""
    safe = ''.join(ch for ch in str(account_id) if ch.isalnum() or ch in '-_') or 'default'
    return os.path.join(DATA_ROOT, RUN_DIR, safe)


def _copy_tree_if_missing(src: str, dst: str) -> None:
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target = dst if rel == '.' else os.path.join(dst, rel)
        try:
            os.makedirs(target, exist_ok=True)
        except OSError:
            continue
        for name in files:
            source = os.path.join(root, name)
            dest = os.path.join(target, name)
            if os.path.exists(dest):
                continue
            try:
                shutil.copy2(source, dest)
            except OSError:
                pass


def migrate_portable_install() -> bool:
    """把旧版「exe 旁边的 task/ 数据」搬到新的用户数据目录。

    只在打包版首次运行时做一次（用 .migrated 标记），子进程（--core）不参与，
    避免多个进程同时搬运。
    """
    if not is_frozen() or '--core' in sys.argv:
        return False
    legacy = os.path.join(app_root(), 'task')
    if not os.path.isdir(legacy) or os.path.abspath(legacy) == os.path.abspath(DATA_ROOT):
        return False
    marker = os.path.join(DATA_ROOT, '.migrated')
    if os.path.exists(marker):
        return False
    try:
        os.makedirs(DATA_ROOT, exist_ok=True)
    except OSError:
        return False
    for sub in _MIGRATE_SUBS:
        src = os.path.join(legacy, sub)
        if os.path.isdir(src):
            _copy_tree_if_missing(src, os.path.join(DATA_ROOT, sub))
    for name in _MIGRATE_FILES:
        src = os.path.join(app_root(), name)
        dest = os.path.join(DATA_ROOT, name)
        if os.path.isfile(src) and not os.path.exists(dest):
            try:
                shutil.copy2(src, dest)
            except OSError:
                pass
    try:
        with open(marker, 'w', encoding='utf-8') as f:
            f.write('migrated from %s\n' % legacy)
    except OSError:
        pass
    return True


# 旧版本用过的记录名/标记（转义写法，保持兼容）
_LEGACY_RECORD = '\u5237\u8bfe\u8bb0\u5f55'      # 旧记录文件名里的词
_LEGACY_MARKER = '\u6b63\u5728\u5237'            # 旧章节标记前缀


def _record_dirs():
    dirs = [os.path.join(DATA_ROOT, RECORD_DIR)]
    run_root = os.path.join(DATA_ROOT, RUN_DIR)
    try:
        names = os.listdir(run_root)
    except OSError:
        names = []
    for name in names:
        dirs.append(os.path.join(run_root, name, RECORD_DIR))
    return [d for d in dirs if os.path.isdir(d)]


def migrate_legacy_names() -> None:
    """把旧版留下的文件名/标记改成新措辞（幂等）。"""
    for folder in _record_dirs():
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            if _LEGACY_RECORD in name:
                target = os.path.join(folder, name.replace(_LEGACY_RECORD, '学习记录'))
                try:
                    if not os.path.exists(target):
                        os.replace(os.path.join(folder, name), target)
                except OSError:
                    pass
        marker_file = os.path.join(folder, 'studying_record.txt')
        try:
            with open(marker_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except OSError:
            continue
        if _LEGACY_MARKER in content:
            try:
                with open(marker_file, 'w', encoding='utf-8') as f:
                    f.write(content.replace(_LEGACY_MARKER, '正在学习'))
            except OSError:
                pass


def prepare() -> None:
    """启动时调用：迁移旧数据并建好目录（幂等，主进程/子进程都可调）。"""
    try:
        migrate_portable_install()
    except Exception:
        pass
    ensure_data_dirs()
    try:
        migrate_legacy_names()
    except Exception:
        pass
