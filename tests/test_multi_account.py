# -*- coding: utf-8 -*-
"""多账号相关的回归测试：并发状态、签到多账号、签到数据隔离。

背景（2026-10-31 用户反馈）：
  1. 自动签到只进一个账号，而且没有选账号的地方；
  2. 并发数调完之后，不知道到底哪几个账号在跑、哪几个在排队。

改动：
  · `Runner` 记录 running/pending，GUI 每秒显示「并发 N/M ｜ 运行中：… ｜ 排队：…」；
  · 自动签到窗口改成勾选多个账号，每个账号一个子进程（`start.py --sign`），
    签到数据目录改为跟随 `XXT_HOME`（`paths.data`），账号之间不再互相覆盖 cookie。

用法：C:/Python315/python.exe tests/test_multi_account.py
"""
import io
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ['XXT_HOME'] = tempfile.mkdtemp(prefix='xxt_multi_')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from core import paths
from core import runner as runner_mod
from core.runner import Runner
from task.xxt import storage

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


class FakeConfig:
    def __init__(self, home):
        self.home = home

    def write_account_runtime(self, account_id):
        return self.home

    def get_account_by_id(self, account_id):
        return {'id': account_id, 'alias': '账号' + str(account_id)}


class FakeProc:
    def __init__(self, *args, **kwargs):
        self.pid = 4242
        self.stdout = io.BytesIO('签到成功\n'.encode('utf-8'))
        self.killed = False

    def wait(self, timeout=None):
        return 0


def main():
    home = os.environ['XXT_HOME']

    # ---------- 1) 签到数据跟随 XXT_HOME（多账号互不覆盖） ----------
    check('签到数据目录跟随 HOME',
          os.path.abspath(storage.DATA_DIR) == os.path.abspath(paths.data('data')),
          storage.DATA_DIR)
    check('签到数据目录在本次 HOME 下',
          os.path.abspath(storage.DATA_DIR).startswith(os.path.abspath(home)),
          storage.DATA_DIR)

    # ---------- 2) Runner 的 running / pending ----------
    outputs = []
    finished = []
    r = Runner(FakeConfig(home), lambda aid, text, tag: outputs.append((aid, text)),
               lambda aid, code: finished.append((aid, code)), max_concurrency=1)
    original_popen = runner_mod.subprocess.Popen
    runner_mod.subprocess.Popen = FakeProc
    try:
        started = r.start(['a1', 'a2'])
        for thread in list(r._threads):
            thread.join(timeout=10)
    finally:
        runner_mod.subprocess.Popen = original_popen

    check('两个账号都被提交', started == 2, started)
    check('全部跑完后 running 为空', r.running_ids() == [], r.running_ids())
    check('全部跑完后 pending 为空', r.pending_ids() == [], r.pending_ids())
    check('输出回调带上账号 id', {'a1', 'a2'} == {aid for aid, _ in outputs},
          [aid for aid, _ in outputs])
    check('结束回调带上账号 id', {'a1', 'a2'} == {aid for aid, _ in finished}, finished)

    # 排队状态：手动放两个进 pending，一个进 procs
    r2 = Runner(FakeConfig(home), lambda *a: None, lambda *a: None, max_concurrency=1)
    with r2._lock:
        r2._pending = ['x1', 'x2']
        r2._procs['x1'] = runner_mod.AccountProcess('x1', '账号x1', FakeProc())
    check('运行中只包含已起进程的', r2.running_ids() == ['x1'], r2.running_ids())
    check('排队里不会重复算运行中的', r2.pending_ids() == ['x2'], r2.pending_ids())
    r2._discard_pending('x2')
    check('取消排队生效', r2.pending_ids() == [], r2.pending_ids())

    # ---------- 3) 并发状态文案 ----------
    import start as gui

    class Dummy:
        _alias_map = {'a1': '账号2', 'a2': '账号3', 'a3': '账号4'}

    text = gui.Start._format_runtime_status(Dummy(), ['a1'], ['a2', 'a3'], 2)
    check('文案显示并发上限', '并发 1/2' in text, text)
    check('文案显示运行中的账号名', '运行中：账号2' in text, text)
    check('文案显示排队的账号名', '排队：账号3、账号4' in text, text)

    full = gui.Start._format_runtime_status(Dummy(), ['a1', 'a2'], ['a3'], 2)
    check('跑满并发时提示等待', '并发 2/2' in full and '已达并发上限' in full, full)

    idle = gui.Start._format_runtime_status(Dummy(), [], [], 3)
    check('空闲时显示空闲', '空闲' in idle, idle)

    # ---------- 4) 签到子进程入口 ----------
    import gui.sign_window as sw

    tool_dir = paths.data('tool')
    os.makedirs(tool_dir, exist_ok=True)
    info_path = os.path.join(tool_dir, 'account_info.json')
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump({'phone_number': '13800000000', 'password': 'pw', 'alias': '账号2'}, f)

    calls = []
    original_main = sw.main
    sw.main = lambda phone=None, password=None, stop_event=None: calls.append((phone, password)) or 0
    try:
        code = sw.sign_once()
    finally:
        sw.main = original_main
    check('sign_once 读到手机号', calls == [('13800000000', 'pw')], calls)
    check('sign_once 返回 0', code == 0, code)

    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump({'alias': '没有手机号'}, f)
    check('没有手机号时返回 1', sw.sign_once() == 1)

    print('---')
    if FAILS:
        print('FAILED: %d' % len(FAILS), FAILS)
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
