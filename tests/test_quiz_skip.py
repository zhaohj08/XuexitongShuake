# -*- coding: utf-8 -*-
"""「遇见章节测验直接跳过」的回归测试（纯桩，无浏览器）。

覆盖 2026-10-31 这批修复：
  1. `check_audio_finished()` 改为包含匹配（class 顺序/多空格也能识别），取父元素失败不抛异常；
  2. `Common.main()` 在模块**没有前置兄弟 div** 时不再抛异常
     （以前会让整场测验被 `safe('测验', ...)` 吞掉，看起来就是「跳过」）；
  3. `Answer._quiz_finished_by_status()` 只认测验自己的状态，
     **不再因为相邻任务点的 aria-label 含「已完成」就整场跳过**；
  4. 测验 iframe 选择器放宽成 `src*=`，平台把 src 写成绝对 URL 也能命中。

用法：C:/Python315/python.exe tests/test_quiz_skip.py
"""
import io
import os
import sys
import tempfile
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

os.environ['XXT_HOME'] = tempfile.mkdtemp(prefix='xxt_test_home_')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from selenium.common.exceptions import NoSuchElementException

import task.quiz_ai as quiz_ai
import task.tool.common as common_mod

# 记录文件跟本用例无关，直接桩掉，避免写盘
common_mod.save_record = lambda *args, **kwargs: None

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


class Node:
    def __init__(self, cls='', text=''):
        self._cls = cls
        self.text = text

    def get_attribute(self, name):
        return self._cls if name == 'class' else ''

    def is_displayed(self):
        return True


class IframeStub:
    """模拟章节页里的模块 iframe。"""

    def __init__(self, parent_class='ans-attach-ct', has_prev_div=True, siblings=()):
        self.parent_class = parent_class
        self.has_prev_div = has_prev_div
        self.siblings = list(siblings)

    def find_element(self, by, value):
        if value == '..':
            return Node(self.parent_class)
        if 'preceding-sibling' in value:
            if not self.has_prev_div:
                raise NoSuchElementException('没有前置兄弟 div')
            return Node()
        raise NoSuchElementException(value)

    def find_elements(self, by, value):
        return self.siblings


class SwitchStub:
    def default_content(self):
        pass

    def frame(self, arg):
        pass


class DriverStub:
    def __init__(self, iframes):
        self.switch_to = SwitchStub()
        self.iframes = iframes
        self.scripts = []

    def find_elements(self, by, value):
        return list(self.iframes)

    def execute_script(self, script, *args):
        self.scripts.append(script)


class ProbeCommon(common_mod.Common):
    """绕开 __init__ 的 DOM 探测，直接塞入 iframe 列表。"""

    def __init__(self, driver, iframes, require_mission=True, boom=False):
        self.course_name = '测试课'
        self.type = '测验'
        self.driver = driver
        self.require_mission = require_mission
        self.iframes = iframes
        self.started = 0
        self.boom = boom

    def start(self):
        self.started += 1
        if self.boom:
            raise RuntimeError('模拟作答失败')


class AnswerDriver:
    def __init__(self, status=None):
        self.status = status

    def find_element(self, by, value):
        if self.status is None:
            raise NoSuchElementException('没有状态元素')
        return Node(text=self.status)


class FrameStub:
    def __init__(self, cls='ans-attach-ct'):
        self.cls = cls

    def find_element(self, by, value):
        if value == '..':
            return Node(self.cls)
        raise NoSuchElementException(value)


def make_answer(status=None, parent_class='ans-attach-ct'):
    answer = object.__new__(quiz_ai.Answer)
    answer.frame = FrameStub(parent_class)
    answer.driver = AnswerDriver(status)
    answer._enter_context = lambda: True     # 不真正切帧
    return answer


def run_common(probe):
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            probe.main()
    finally:
        pass
    return buf.getvalue()


def main():
    # ---------- 1) 没有前置兄弟 div 时不能崩（真实原因之一） ----------
    iframe = IframeStub(has_prev_div=False)
    probe = ProbeCommon(DriverStub([iframe]), [iframe], require_mission=False)
    try:
        run_common(probe)
        ok, err = True, ''
    except Exception as e:                      # noqa: BLE001 - 旧实现这里必崩
        ok, err = False, repr(e)
    check('模块没有前置 div 时不抛异常', ok, err)
    check('这种情况下仍然会作答', probe.started == 1, probe.started)

    # ---------- 2) 任务点开关 ----------
    iframe = IframeStub(siblings=[])
    probe = ProbeCommon(DriverStub([iframe]), [iframe], require_mission=True)
    log = run_common(probe)
    check('require_mission=True 且无任务点 -> 不作答', probe.started == 0, probe.started)
    check('跳过时打印原因', '没有任务点标记' in log, log.strip()[:60])

    probe = ProbeCommon(DriverStub([IframeStub()]), [IframeStub()], require_mission=False)
    run_common(probe)
    check('require_mission=False 无任务点也作答', probe.started == 1, probe.started)

    # ---------- 3) 已完成判定：包含匹配 ----------
    for cls, expect in (
        ('ans-attach-ct ans-job-finished', 0),
        ('ans-job-finished ans-attach-ct', 0),          # class 顺序不同
        ('ans-attach-ct  ans-job-finished ', 0),        # 多余空格
        ('ans-attach-ct', 1),                           # 未完成
    ):
        iframe = IframeStub(parent_class=cls)
        probe = ProbeCommon(DriverStub([iframe]), [iframe], require_mission=False)
        run_common(probe)
        check('父容器 %r -> 作答次数 %d' % (cls, expect), probe.started == expect, probe.started)

    # ---------- 4) 单场出错不影响下一场 ----------
    first, second = IframeStub(has_prev_div=False), IframeStub(has_prev_div=False)
    probe = ProbeCommon(DriverStub([first, second]), [first, second],
                        require_mission=False, boom=True)
    log = run_common(probe)
    check('单场抛异常时继续处理下一场', probe.started == 2, probe.started)
    check('抛异常时打印跳过原因', '处理出错，跳过' in log, log.strip()[:80])

    # ---------- 5) 测验完成判定只看自己 ----------
    check('状态=已完成 -> 跳过',
          make_answer('已完成')._quiz_finished_by_status()[0] is True)
    check('状态=待批阅 -> 视为已完成',
          make_answer('待批阅')._quiz_finished_by_status()[0] is True)
    finished, reason = make_answer('未交')._quiz_finished_by_status()
    check('状态=未交 -> 不跳过', finished is False, reason)
    check('没有状态元素 + 父容器已完成 -> 跳过',
          make_answer(None, 'ans-attach-ct ans-job-finished')._quiz_finished_by_status()[0] is True)
    check('没有状态元素 + 父容器含标记 -> 跳过',
          make_answer(None, 'ans-job-finished extra')._quiz_finished_by_status()[0] is True)
    check('没有状态元素 + 普通父容器 -> 不跳过',
          make_answer(None, 'ans-attach-ct')._quiz_finished_by_status()[0] is False)

    # ---------- 6) 选择器放宽 ----------
    check('Quiz.IFRAME_SELECTOR 用 src 包含匹配',
          'src*=' in quiz_ai.Quiz.IFRAME_SELECTOR, quiz_ai.Quiz.IFRAME_SELECTOR)
    with open(os.path.join(ROOT, 'main.py'), 'r', encoding='utf-8') as f:
        main_src = f.read()
    check('main.py 的测验识别同样用 src 包含匹配',
          'iframe[src*="/ananas/modules/work/index.html"]' in main_src)
    check('main.py 已无前缀匹配写法',
          'src^="/ananas/modules/work/index.html"' not in main_src)

    print('---')
    if FAILS:
        print('FAILED: %d' % len(FAILS), FAILS)
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
