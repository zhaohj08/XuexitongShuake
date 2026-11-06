# -*- coding: utf-8 -*-
"""签到监控频率/退出机制的回归测试（纯桩，不联网、不开浏览器）。

背景：2026-11-05 用户账号被封，技术部门称「连续刷了 20 万次」。
根因是 constants.CHECK_INTERVAL 被写成 2 秒（注释却写 7 秒），
monitor() 每轮对 24 门课各发一次 ACTIVE_LIST 请求且没有退出/降频机制。
"""
import os
import sys
import tempfile
import threading
import time as real_time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from task.xxt import constants, monitor, storage  # noqa: E402
from gui import sign_window  # noqa: E402

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


class Clock:
    """假的 time 模块：sleep 只推进假时钟，测试不用真等。"""

    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def run_monitor(rounds, *, max_runtime=0, stop_event=None):
    """跑 monitor() 若干轮，返回 (日志, 假时钟, 扫描次数)。"""
    clock = Clock()
    logs = []
    state = {'scans': 0}
    if stop_event is None:
        stop_event = threading.Event()

    def fake_scan(*args, **kwargs):
        state['scans'] += 1
        if state['scans'] >= rounds:
            stop_event.set()
        return []

    saved = {
        'time': monitor.time,
        'get_courses': monitor.courses.get_courses,
        'scan': monitor.scan_and_sign_once,
        'log': monitor.storage.log,
        'max_runtime': constants.MAX_RUNTIME,
    }
    try:
        monitor.time = clock
        monitor.courses.get_courses = lambda client: [object()] * 24
        monitor.scan_and_sign_once = fake_scan
        monitor.storage.log = lambda message, **kwargs: logs.append(message)
        constants.MAX_RUNTIME = max_runtime
        monitor.monitor(object(), interval=constants.CHECK_INTERVAL,
                        workers=5, stop_event=stop_event)
    finally:
        monitor.time = saved['time']
        monitor.courses.get_courses = saved['get_courses']
        monitor.scan_and_sign_once = saved['scan']
        monitor.storage.log = saved['log']
        constants.MAX_RUNTIME = saved['max_runtime']
    return logs, clock, state['scans']


def main():
    # ---------- 1) 频率参数 ----------
    check('基础间隔不再是被封号时的 2 秒',
          constants.CHECK_INTERVAL >= 30, constants.CHECK_INTERVAL)
    check('空闲退避上限大于基础间隔',
          constants.MAX_CHECK_INTERVAL > constants.CHECK_INTERVAL,
          (constants.CHECK_INTERVAL, constants.MAX_CHECK_INTERVAL))
    check('最长运行时间上限存在（防止过夜挂机）',
          constants.MAX_RUNTIME == 4 * 3600, constants.MAX_RUNTIME)
    check('连续多少轮空闲后开始降频',
          constants.IDLE_BACKOFF_AFTER >= 1, constants.IDLE_BACKOFF_AFTER)

    # ---------- 2) 子进程 --sign 不再被 argparse 拒绝 ----------
    try:
        args, unknown = sign_window._build_parser().parse_known_args(['--sign'])
        check('parse_known_args 能吃下 --sign', '--sign' in unknown, unknown)
        check('--sign 时默认间隔取 constants',
              args.interval == constants.CHECK_INTERVAL and args.once is False, args.interval)
    except SystemExit as e:
        check('parse_known_args 能吃下 --sign', False, 'SystemExit %s' % e.code)

    # ---------- 3) 日志带时间戳 ----------
    folder = tempfile.mkdtemp(prefix='xxt_sign_log_')
    saved_path = storage._path
    try:
        storage._path = lambda name: os.path.join(folder, name)
        storage.log('课程列表: 24 门')
        with open(os.path.join(folder, storage.LOG_FILE), encoding='utf-8') as f:
            line = f.read().strip()
        check('sign.log 每行带 YYYY-MM-DD HH:MM:SS 时间戳',
              line.startswith('[20') and '] ' in line and '课程列表: 24 门' in line, line)
    finally:
        storage._path = saved_path

    # ---------- 4) 空闲退避 ----------
    logs, clock, scans = run_monitor(25)
    check('25 轮空转后自动停下', scans == 25, scans)
    check('前几轮按基础间隔', clock.sleeps[0] == constants.CHECK_INTERVAL,
          clock.sleeps[:3])
    check('连续空闲后间隔会变长', clock.sleeps[-1] > clock.sleeps[0],
          (clock.sleeps[0], clock.sleeps[9], clock.sleeps[-1]))
    check('退避不会超过上限', max(clock.sleeps) <= constants.MAX_CHECK_INTERVAL,
          max(clock.sleeps))
    check('启动日志写明了间隔与最长运行时长',
          any('每 %d 秒' % constants.CHECK_INTERVAL in x and '最长' in x for x in logs),
          logs[:1])

    # ---------- 5) 最长运行时长 ----------
    logs, clock, scans = run_monitor(99, max_runtime=100)
    check('到最长运行时间会自动停止',
          any('自动停止' in x for x in logs) and scans < 99, (scans, logs[-1:]))

    # ---------- 6) stop_event ----------
    stopped = threading.Event()
    stopped.set()
    logs, clock, scans = run_monitor(99, stop_event=stopped)
    check('stop_event 已置位时立刻退出且不发请求',
          scans == 0 and any('已停止' in x for x in logs), (scans, logs))

    # ---------- 7) 父进程监视的兼容性 ----------
    real_getppid = sign_window.os.getppid
    try:
        sign_window.os.getppid = lambda: (_ for _ in ()).throw(OSError('no ppid'))
        sign_window._watch_parent_exit(threading.Event())
        ok = True
    except Exception:
        ok = False
    finally:
        sign_window.os.getppid = real_getppid
    check('不支持 os.getppid 的平台上父进程监视安全跳过', ok)

    print('---')
    if FAILS:
        print('FAILED: %d' % len(FAILS), FAILS)
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
