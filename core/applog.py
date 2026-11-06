# -*- coding: utf-8 -*-
"""程序运行日志：从启动那一刻开始，把主流程事件、界面操作、子进程输出写进**单独**的日志文件。

位置（按 core.paths 的规则）：
    打包版  %LOCALAPPDATA%\\XuexitongShuake\\logs\\程序日志.log
    源码版  项目 task/logs/程序日志.log

约定：
- 追加写；单文件超过 8MB 自动轮转成 `程序日志.log.1`（只保留一份历史）；
- 每行格式 `YYYY-MM-DD HH:MM:SS.mmm [LEVEL] 内容`，方便和 error.log、
  `run/<账号>/运行日志.log` 对照；
- 线程安全；写盘失败一律静默，绝不影响主流程。
"""
from __future__ import annotations

import os
import platform
import sys
import threading
import time
import traceback

from core import paths

LOG_DIR = 'logs'
LOG_NAME = '程序日志.log'
MAX_BYTES = 8 * 1024 * 1024

_lock = threading.Lock()
_ready = False
_path = None


def log_path() -> str:
    global _path
    if _path is None:
        _path = paths.data(LOG_DIR, LOG_NAME)
    return _path


def _rotate(path: str) -> None:
    try:
        if os.path.exists(path) and os.path.getsize(path) > MAX_BYTES:
            os.replace(path, path + '.1')
    except OSError:
        pass


def _write(line: str) -> None:
    path = log_path()
    try:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with _lock:
            # 运行中也可能涨到上限（启动后长时间跑），所以每写一行都顺手检查一次
            try:
                if os.path.exists(path) and os.path.getsize(path) > MAX_BYTES:
                    os.replace(path, path + '.1')
            except OSError:
                pass
            with open(path, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
    except (OSError, ValueError):
        pass


def _stamp() -> str:
    now = time.time()
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now)) + '.%03d' % int(now % 1 * 1000)


def _log(level: str, message: str) -> None:
    if not _ready:
        setup()
    for line in (message or '').splitlines() or ['']:
        _write('%s [%-5s] %s' % (_stamp(), level, line))


def setup(extra: str = '') -> str:
    """写一个启动分隔块，返回日志文件路径。重复调用只追加，不会清空历史。"""
    global _ready
    path = log_path()
    _rotate(path)
    version = ''
    try:
        with open(paths.asset('tool', 'version_info'), 'r', encoding='utf-8') as f:
            version = f.read().strip()
    except OSError:
        version = '未知'
    data_root = os.path.dirname(os.path.dirname(path))
    head = [
        '',
        '=' * 78,
        '启动 %s   版本 %s%s' % (time.strftime('%Y-%m-%d %H:%M:%S'), version,
                                ('   ' + extra) if extra else ''),
        'pid=%s  python=%s  frozen=%s' % (os.getpid(), platform.python_version(),
                                          bool(getattr(sys, 'frozen', False))),
        'platform=%s' % platform.platform(),
        'app_root=%s' % paths.app_root(),
        'data_root=%s' % data_root,
        '=' * 78,
    ]
    for line in head:
        _write(line)
    _ready = True
    return path


def info(message: str) -> None:
    _log('INFO', message)


def warn(message: str) -> None:
    _log('WARN', message)


def error(message: str) -> None:
    _log('ERROR', message)


def exception(prefix: str = '', exc_info=None) -> None:
    """记录异常：优先用传入的 exc_info，否则用当前正在处理的异常。"""
    if exc_info is None:
        detail = traceback.format_exc()
    else:
        detail = ''.join(traceback.format_exception(*exc_info))
    _log('ERROR', (prefix + '\n' if prefix else '') + detail.rstrip())


def child(account_id: str, text: str) -> None:
    """把子进程的一行输出记到主日志，前缀账号，便于串起整条时间线。"""
    for line in (text or '').splitlines():
        if line.strip():
            _log('CHILD', '%s | %s' % (account_id, line.rstrip()))


def ui(action: str) -> None:
    """界面操作（点按钮、切页面等）。"""
    _log('UI', action)
