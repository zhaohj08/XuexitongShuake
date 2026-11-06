# -*- coding: utf-8 -*-
"""程序日志 + 窗口缩放 的回归测试。

覆盖：
  · `core.applog.setup()` 写出启动块（版本/pid/平台/路径）；
  · info/warn/error/exception/child/ui 六级都有时间戳与等级标记；
  · 超过上限轮转成 `.1`；
  · 多线程同时写不丢行；
  · 主窗口可缩放（`resizable(True, True)`）且有最小尺寸；
  · GUI 启动后主日志里能看到"窗口初始化完成"。

用法：C:/Python315/python.exe tests/test_applog.py
"""
import os
import re
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ['XXT_HOME'] = tempfile.mkdtemp(prefix='xxt_applog_')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from core import applog

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def main():
    # ---------- 1) 启动块 ----------
    path = applog.setup('unit-test')
    check('日志文件名正确', path.endswith(os.path.join('logs', '程序日志.log')), path)
    check('日志在 XXT_HOME 下', path.startswith(os.environ['XXT_HOME']), path)
    head = read(path)
    check('启动块含版本', '版本' in head)
    check('启动块含 pid/平台/路径',
          all(k in head for k in ('pid=', 'platform=', 'app_root=', 'data_root=')), head[:200])

    # ---------- 2) 各等级 ----------
    applog.info('普通信息')
    applog.warn('警告信息')
    applog.error('错误信息')
    applog.child('acc1', '第一行\n第二行')
    applog.ui('点击按钮')
    applog.exception('测试异常', exc_info=(ValueError, ValueError('boom'), None))
    lines = read(path).splitlines()
    body = '\n'.join(lines[-12:])
    for token in ('[INFO ]', '[WARN ]', '[ERROR]', '[CHILD]', '[UI   ]'):
        check('有等级标记 %s' % token, token in body, token)
    check('子进程多行都落盘', 'acc1 | 第一行' in body and 'acc1 | 第二行' in body)
    check('异常带堆栈', 'ValueError: boom' in body)
    check('行首是毫秒时间戳',
          re.match(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} ', lines[-1]) is not None,
          lines[-1][:40])

    # ---------- 3) 轮转 ----------
    original = applog.MAX_BYTES
    applog.MAX_BYTES = 10
    try:
        applog.info('x' * 200)
    finally:
        applog.MAX_BYTES = original
    check('超过上限轮转成 .1', os.path.exists(path + '.1'))

    # ---------- 4) 并发写不丢行 ----------
    marker = 'THREADMARK'
    def worker(n):
        for i in range(10):
            applog.info('%s-%d-%d' % (marker, n, i))

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    got = read(path).count(marker)
    check('8 线程 × 10 行都写进去了', got == 80, got)

    # ---------- 5) 窗口可缩放 ----------
    import start as gui

    app = gui.Start()
    try:
        flags = app.root.resizable()
        check('窗口允许缩放', tuple(int(x) for x in flags) == (1, 1), flags)

        app.root.update_idletasks()
        before_w = app.root.winfo_width()
        app.root.geometry('1180x780')
        app.root.update()
        app.root.update_idletasks()
        after_w = app.root.winfo_width()
        check('放大后窗口真的变宽', after_w > before_w, (before_w, after_w))

        min_w, min_h = app.root.wm_minsize()
        # CTk 会按 DPI 缩放，所以不能写死像素值：下限存在、且不超过当前窗口即可
        check('有最小尺寸且不超过当前窗口',
              0 < min_w <= after_w and 0 < min_h <= app.root.winfo_height(),
              (min_w, min_h, after_w))

        log_text = read(path)
        check('主日志记录了窗口初始化', '窗口初始化完成' in log_text)
    finally:
        try:
            app.root.destroy()
        except Exception:
            pass

    print('---')
    if FAILS:
        print('FAILED: %d' % len(FAILS), FAILS)
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
