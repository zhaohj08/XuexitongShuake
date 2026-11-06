# -*- coding: utf-8 -*-
"""统一运行所有纯桩测试套件（不联网、不开浏览器）。

用法：
    python tests/run_stub_tests.py

默认跳过 3 个需要真实 Edge + 匹配驱动的套件；
在无 GUI 会话的 CI 里设置 XXT_SKIP_GUI_TESTS=1 可再跳过窗口相关套件。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 需要真实浏览器会话，本机驱动版本不匹配时会报 unhandled request
SKIP_ALWAYS = {
    'test_image_answer.py',
    'test_quiz_image.py',
    'test_quiz_selector.py',
}
# 需要能创建 Tk 窗口（GUI 冒烟）
SKIP_NO_GUI = {'test_applog.py'}


def main() -> int:
    skip = set(SKIP_ALWAYS)
    if os.environ.get('XXT_SKIP_GUI_TESTS'):
        skip |= SKIP_NO_GUI
    files = sorted(
        name for name in os.listdir(HERE)
        if name.startswith('test_') and name.endswith('.py') and name not in skip
    )
    # 源码模式下 DATA_ROOT 默认是项目 task/，测试会往里写日志/截图/账号目录。
    # 用 XXT_DATA 指到临时目录，跑完即删，保证工作树干净。
    data_tmp = tempfile.mkdtemp(prefix='xxt_stub_data_')
    env = dict(os.environ)
    env.setdefault('PYTHONIOENCODING', 'utf-8')
    env['XXT_DATA'] = data_tmp
    failed = []
    try:
        print('ROOT=%s' % ROOT)
        print('DATA=%s (临时)' % data_tmp)
        print('SUITES=%d  SKIPPED=%s' % (len(files), ', '.join(sorted(skip)) or 'none'))
        print('-' * 70)
        for name in files:
            proc = subprocess.run(
                [sys.executable, os.path.join(HERE, name)],
                cwd=ROOT, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            out = proc.stdout.decode('utf-8', errors='replace')
            tail = [ln for ln in out.splitlines() if ln.strip()][-1:] or ['(no output)']
            ok = proc.returncode == 0
            print('%-4s %-38s %s' % ('PASS' if ok else 'FAIL', name, tail[0][:90]))
            if not ok:
                failed.append(name)
                for ln in out.splitlines()[-12:]:
                    print('       ' + ln)
    finally:
        shutil.rmtree(data_tmp, ignore_errors=True)
    print('-' * 70)
    print('RESULT=%s  (%d/%d passed)' % ('ALL PASS' if not failed else 'FAILED',
                                        len(files) - len(failed), len(files)))
    if failed:
        print('FAILED: ' + ', '.join(failed))
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
