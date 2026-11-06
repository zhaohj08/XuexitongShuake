"""多账号并发调度。

每个账号一个独立子进程，通过环境变量 XXT_HOME 指向自己的工作目录，
从而隔离 Cookie、学习记录、课程进度；主进程只负责拉起、读输出、限流、终止。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time

from core import paths
from core import applog

# colorama 的 Fore 码 -> tkinter 颜色名
ANSI_COLORS = {
    '\x1b[31m': 'red', '\x1b[33m': 'yellow', '\x1b[34m': 'blue',
    '\x1b[32m': 'green', '\x1b[35m': 'magenta', '\x1b[36m': 'cyan',
}
ANSI_RESET = '\x1b[0m'

# 子进程输出落盘（界面日志框关掉就没了，排查问题时全靠这个文件）
OUTPUT_LOG_NAME = '运行日志.log'
OUTPUT_LOG_LIMIT = 3 * 1024 * 1024     # 超过 3MB 轮转成 .old


def output_log_path(account_id) -> str:
    return os.path.join(paths.account_home(account_id), OUTPUT_LOG_NAME)


def append_output_log(path: str, text: str, stamp: str = None) -> None:
    """把子进程输出按时间戳追加到日志文件；失败静默（不能因为写日志影响主流程）。"""
    stamp = stamp or time.strftime('%H:%M:%S')
    try:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path) > OUTPUT_LOG_LIMIT:
            try:
                os.replace(path, path + '.old')
            except OSError:
                pass
        with open(path, 'a', encoding='utf-8') as f:
            for line in (text or '').splitlines():
                if line.strip():
                    f.write(f'{stamp} {line}\n')
    except OSError:
        pass

MAX_CONCURRENCY = 5


class AccountProcess:
    """一个账号对应的一条子进程。"""

    def __init__(self, account_id, alias, popen):
        self.account_id = account_id
        self.alias = alias
        self.popen = popen


class Runner:
    """按并发上限逐个拉起账号，输出通过回调送回 UI。"""

    def __init__(self, config, on_output, on_finish, max_concurrency=2,
                 entry_args=('--core',)):
        self.config = config
        self.on_output = on_output          # (account_id, text, color_tag) -> None
        self.on_finish = on_finish          # (account_id, exit_code) -> None
        self.entry_args = tuple(entry_args or ('--core',))
        self.max_concurrency = max(1, min(MAX_CONCURRENCY, int(max_concurrency or 1)))
        self._sem = threading.Semaphore(self.max_concurrency)
        self._lock = threading.Lock()
        self._procs = {}
        self._pending = []
        self._stop = threading.Event()
        self._threads = []

    # ------------------------------------------------------------ 生命周期
    def set_concurrency(self, n):
        """运行前调整并发上限（1~5）。"""
        self.max_concurrency = max(1, min(MAX_CONCURRENCY, int(n or 1)))
        self._sem = threading.Semaphore(self.max_concurrency)

    def active_count(self):
        with self._lock:
            return len(self._procs)

    def running_ids(self):
        """当前真正在跑的账号 id（已经起了子进程的）。"""
        with self._lock:
            return list(self._procs.keys())

    def pending_ids(self):
        """还在排队的账号 id（已提交但还没轮到）。"""
        with self._lock:
            return [aid for aid in self._pending if aid not in self._procs]

    @property
    def running(self):
        with self._lock:
            return dict(self._procs)

    def start(self, account_ids):
        self._stop.clear()
        self._threads = []
        with self._lock:
            self._pending = list(account_ids)
        for aid in account_ids:
            t = threading.Thread(target=self._run_one, args=(aid,), daemon=True)
            t.start()
            self._threads.append(t)
        return len(self._threads)

    def _discard_pending(self, account_id):
        with self._lock:
            if account_id in self._pending:
                self._pending.remove(account_id)

    def stop_all(self):
        self._stop.set()
        with self._lock:
            self._pending = []
            procs = list(self._procs.values())
        for item in procs:
            self._terminate(item.popen)

    def _terminate(self, process):
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)],
                               capture_output=True)
            else:
                process.terminate()
        except Exception:
            pass

    # ------------------------------------------------------------ 单账号执行
    def _command(self):
        if getattr(sys, 'frozen', False):
            return [sys.executable, *self.entry_args]
        if self.entry_args == ('--core',):
            return [sys.executable, os.path.join(paths.app_root(), 'main.py')]
        return [sys.executable, os.path.join(paths.app_root(), 'start.py'), *self.entry_args]

    def _run_one(self, account_id):
        self._sem.acquire()
        try:
            if self._stop.is_set():
                self._discard_pending(account_id)
                return
            home = self.config.write_account_runtime(account_id)
            if not home:
                self.on_output(account_id, f'[调度] 账号 {account_id} 配置无效，跳过\n', 'red')
                applog.warn('账号 %s 配置无效，未启动子进程' % account_id)
                self._discard_pending(account_id)
                return

            env = os.environ.copy()
            env['XXT_HOME'] = home
            env['PYTHONIOENCODING'] = 'utf-8'

            try:
                process = subprocess.Popen(
                    self._command(),
                    cwd=paths.app_root(),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
            except Exception as e:
                self.on_output(account_id, f'[调度] 启动失败: {e}\n', 'red')
                applog.exception('账号 %s 子进程启动失败' % account_id)
                self._discard_pending(account_id)
                return

            alias = self.config.get_account_by_id(account_id).get('alias', account_id)
            applog.info('子进程启动：账号 %s(%s) pid=%s' % (alias, account_id, process.pid))
            with self._lock:
                self._procs[account_id] = AccountProcess(account_id, alias, process)
                if account_id in self._pending:
                    self._pending.remove(account_id)

            self._pump(process, account_id)

            try:
                code = process.wait(timeout=10)
            except Exception:
                code = -1
            with self._lock:
                self._procs.pop(account_id, None)
                if account_id in self._pending:
                    self._pending.remove(account_id)
            applog.info('子进程退出：账号 %s(%s) code=%s' % (alias, account_id, code))
            self.on_finish(account_id, code)
        finally:
            self._sem.release()

    def _pump(self, process, account_id):
        """逐行读子进程输出，解析 ANSI 颜色后回调，并同时落盘到 运行日志.log。"""
        tag = None
        log_path = output_log_path(account_id)
        append_output_log(log_path, f'=== 子进程启动 pid={process.pid} ===')
        while True:
            try:
                raw = process.stdout.readline()
            except Exception:
                break
            if not raw:
                break
            text = self._decode(raw)
            text, tag = self._apply_color(text, tag)
            if text:
                append_output_log(log_path, text)
                self.on_output(account_id, text, tag)
        append_output_log(log_path, '=== 子进程输出结束 ===')
        try:
            process.stdout.close()
        except Exception:
            pass

    @staticmethod
    def _decode(raw: bytes) -> str:
        for enc in ('utf-8', 'gbk'):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode('utf-8', errors='ignore')

    @staticmethod
    def _apply_color(text, tag):
        for code, name in ANSI_COLORS.items():
            if code in text:
                tag = name
                text = text.replace(code, '')
        if ANSI_RESET in text:
            text = text.replace(ANSI_RESET, '')
            tag = None
        # 兜底：清掉残余的 CSI 序列
        text = re.sub(r'\x1b\[[0-9;]*m', '', text)
        text = text.replace('\x1b', '')
        return text, tag

    def wait_all(self, timeout=None):
        for t in list(self._threads):
            t.join(timeout)
