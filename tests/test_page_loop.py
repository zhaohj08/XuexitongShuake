# -*- coding: utf-8 -*-
"""翻页/卡页逻辑的回归测试（纯桩，无浏览器）。

背景：用户反馈「跳转下一页」之后一直报「没有前进」，两次就结束整门课，后面的测验根本轮不到。
根因是 4.10 用「#iframe 元素是否失效 / URL 是否变化」判断翻页，而平台切下一节时
**不会重建 iframe 元素**，于是被误判成没前进。

现在改成按「页面内容指纹」判断进展：
  · 指纹 = 章节标题 + 已完成任务点数 + 任务点总数 + 模块 iframe 的 src
  · 连续 STUCK_LIMIT 次内容完全一致才结束本课程
  · `click_next_page()` 只负责点击 / 判断课程是否到底，不再猜有没有换页

另外锁住「子进程输出落盘」：以后排查不用再靠人贴日志。

用法：C:/Python315/python.exe tests/test_page_loop.py
"""
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from selenium.common.exceptions import ElementNotInteractableException, NoSuchElementException
from selenium.webdriver.common.by import By

import main as core
from core import runner as runner_mod

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


class Node:
    def __init__(self, text='', attrs=None):
        self.text = text
        self.attrs = attrs or {}

    def get_attribute(self, name):
        return self.attrs.get(name, '')

    def click(self):
        pass


class SwitchStub:
    def default_content(self):
        pass

    def frame(self, arg):
        pass


class SigDriver:
    """只够 _content_signature 用的假 driver。"""

    def __init__(self, title='第一章', finished=2, icons=5, srcs=('a.html', 'b.html')):
        self.title = title
        self.finished = finished
        self.icons = icons
        self.srcs = srcs
        self.switch_to = SwitchStub()

    def find_element(self, by, value):
        if value == 'prev_title':
            return Node(attrs={'title': self.title})
        raise NoSuchElementException(value)

    def find_elements(self, by, value):
        if by == By.CSS_SELECTOR and 'ans-job-finished' in value:
            return [Node() for _ in range(self.finished)]
        if by == By.CLASS_NAME and value == 'ans-job-icon-clear':
            return [Node() for _ in range(self.icons)]
        if by == By.TAG_NAME and value == 'iframe':
            return [Node(attrs={'src': src}) for src in self.srcs]
        return []


class ClickableNode(Node):
    def __init__(self, exc=None):
        super().__init__()
        self.exc = exc
        self._size = {'width': 48, 'height': 20}
        self._visible = True

    @property
    def size(self):
        return self._size

    def is_displayed(self):
        return self._visible

    def click(self):
        if self.exc:
            raise self.exc


class ClickDriver:
    """模拟「下一页」按钮：`nodes_by_xpath` 指定哪个 XPath 能命中。"""

    def __init__(self, click_exc=None, hit_xpath=None):
        self.click_exc = click_exc
        self.hit_xpath = hit_xpath or core.NEXT_PAGE_XPATH
        self.switch_to = SwitchStub()
        self.refreshes = 0
        self.clicked = 0

    def find_element(self, by, value):
        return ClickableNode(self.click_exc)

    def find_elements(self, by, value):
        if by == By.XPATH and value == self.hit_xpath:
            node = ClickableNode(self.click_exc)
            node.click = (lambda n=node: self._count(n)) if not self.click_exc else node.click
            return [node]
        return []

    def _count(self, node):
        self.clicked += 1

    def execute_script(self, *args):
        return None

    def implicitly_wait(self, seconds):
        pass

    def refresh(self):
        self.refreshes += 1


def main():
    # ---------- 1) 内容指纹 ----------
    driver = SigDriver(title='第一章', finished=2, icons=5, srcs=('a.html', 'b.html'))
    sig = core._content_signature(driver)
    check('指纹包含标题/完成数/任务点数/src',
          sig == '第一章|2|5|a.html;b.html', sig)

    same = core._content_signature(SigDriver(title='第一章', finished=2, icons=5,
                                             srcs=('a.html', 'b.html')))
    check('内容一样 -> 指纹一样（可判「没进展」）', sig == same, same)

    check('换个知识点（src 变）-> 指纹变',
          core._content_signature(SigDriver(srcs=('c.html',))) != sig)
    check('完成数变化 -> 指纹变',
          core._content_signature(SigDriver(finished=3)) != sig)
    check('章节标题变化 -> 指纹变',
          core._content_signature(SigDriver(title='第二章')) != sig)

    class DeadDriver:
        class switch_to:
            @staticmethod
            def default_content():
                raise NoSuchElementException('dead')

            @staticmethod
            def frame(arg):
                raise NoSuchElementException('dead')

        def find_element(self, *args):
            raise NoSuchElementException('dead')

        def find_elements(self, *args):
            raise NoSuchElementException('dead')

    check('页面结构异常时指纹不抛异常', isinstance(core._content_signature(DeadDriver()), str))

    # ---------- 2) 点击下一页：只区分「到底了」和「点过了」 ----------
    core.error_num = 0
    check('课程到底（按钮不可点）-> False',
          core.click_next_page(ClickDriver(ElementNotInteractableException('done')), 0) is False)
    check('正常点击 -> True', core.click_next_page(ClickDriver(), 0) is True)

    # ---------- 3) 阈值 ----------
    check('未知页面允许刷新 3 次', core.UNKNOWN_REFRESH_LIMIT == 3, core.UNKNOWN_REFRESH_LIMIT)
    check('连续 3 次没进展才停', core.STUCK_LIMIT == 3, core.STUCK_LIMIT)

    # ---------- 4) 报错摘要 ----------
    tb = ('Traceback (most recent call last):\n'
          '  File "main.py", line 300, in find_mission\n'
          "selenium.common.exceptions.NoSuchElementException: Message: no such element: abc\n"
          'Stacktrace:\n\t(No symbol) [0x7ff6be8f09f5]\n')
    brief = core._error_brief(tb)
    check('异常摘要取异常行',
          brief.startswith('selenium.common.exceptions.NoSuchElementException'), brief)

    # ---------- 5) 等元素 ----------
    class FinderDriver:
        def __init__(self, found):
            self.found = found

        def find_elements(self, by, value):
            return [Node()] if self.found else []

        def find_element(self, by, value):
            if self.found:
                return Node()
            raise NoSuchElementException('nope')

    check('等元素命中即返回',
          len(core._wait_elements(FinderDriver(True), By.CLASS_NAME, 'x', timeout=2)) == 1)
    began = time.time()
    check('等元素超时返回空',
          core._wait_elements(FinderDriver(False), By.CLASS_NAME, 'x', timeout=0.5) == [])
    check('超时不会无限等待', time.time() - began < 3, round(time.time() - began, 2))

    # ---------- 6) 会话失效 / 单窗口保护 ----------
    class DeadWindowDriver:
        @property
        def window_handles(self):
            return None

    check('window_handles 为 None 时 turn_page 返回 False',
          core.turn_page(DeadWindowDriver(), 'x', timeout=0.6) is False)

    class OneWindowDriver:
        closed = 0

        @property
        def window_handles(self):
            return ['h1']

        def close(self):
            OneWindowDriver.closed += 1

    core._close_course_tab(OneWindowDriver())
    check('只剩一个窗口时不关闭', OneWindowDriver.closed == 0, OneWindowDriver.closed)

    # ---------- 7) 新窗口切换（学习页开在新标签页时） ----------
    class WindowDriver:
        def __init__(self, handles, titles):
            self._handles = list(handles)
            self.titles = titles
            self.current = handles[0] if handles else None
            self.switch_to = self
            self.added = False

        @property
        def window_handles(self):
            if self.added and 'h2' not in self._handles:
                self._handles.append('h2')
            return list(self._handles)

        @property
        def current_window_handle(self):
            return self.current

        @property
        def title(self):
            return self.titles.get(self.current, '')

        def window(self, handle):
            self.current = handle

    drv = WindowDriver(['h1'], {'h1': '目录页'})
    check('没有新窗口时返回 False',
          core._switch_to_newest_window(drv, ['h1'], timeout=0.6) is False)

    drv = WindowDriver(['h1'], {'h1': '目录页', 'h2': '高等数学'})
    drv.added = True
    check('出现新窗口时能切过去',
          core._switch_to_newest_window(drv, ['h1'], timeout=2) is True)
    check('切到的就是新窗口', drv.current == 'h2', drv.current)

    drv = WindowDriver(['h1', 'h2'], {'h1': '目录页', 'h2': '学习页'})
    titles = core._window_titles(drv)
    check('窗口标题诊断带当前窗口标记',
          '目录页' in titles and '学习页' in titles and '*' in titles, titles)

    # ---------- 9) 被打回的空壳页 / 首页识别 ----------
    class UrlDriver:
        def __init__(self, url='', title='', has_iframe=False, hit_xpath=None):
            self.current_url = url
            self.title = title
            self.has_iframe = has_iframe
            self.hit_xpath = hit_xpath
            self.switch_to = SwitchStub()

        def find_elements(self, by, value):
            if by == By.ID and value == 'iframe':
                return [Node()] if self.has_iframe else []
            if by == By.XPATH and value == self.hit_xpath:
                return [ClickableNode()]
            return []

    study_url = 'https://mooc1-2.chaoxing.com/visit/courses/study?s=2791b59d11f4038ca079173454cb4'
    check('空壳学习页（没有 #iframe）-> 判定为课程首页',
          core._looks_like_course_home(UrlDriver(study_url)) is True)
    check('学习页有 #iframe -> 不算空壳',
          core._looks_like_course_home(UrlDriver(study_url, has_iframe=True)) is False)
    check('别的课程页 -> 不算空壳',
          core._looks_like_course_home(UrlDriver('https://mooc1.chaoxing.com/mycourse/x')) is False)

    check('个人空间首页能识别', core._looks_like_home_page(
        UrlDriver('https://i.chaoxing.com/base?ws=1')) is True)
    check('登录页能识别', core._looks_like_home_page(
        UrlDriver('https://passport2.chaoxing.com/login')) is True)
    check('课程页不算首页', core._looks_like_home_page(UrlDriver(study_url)) is False)

    # ---------- 10) 下一页按钮的备选找法 ----------
    text_xpath = '//*[self::a or self::button][normalize-space(.)="下一页"]'
    btn = core._find_next_button(UrlDriver(hit_xpath=text_xpath))
    check('找不到 id 时按文字「下一页」兜底', btn is not None)
    check('完全找不到时返回 None',
          core._find_next_button(UrlDriver()) is None)

    # ---------- 11) 诊断截图 ----------
    class ShotDriver:
        def __init__(self, raise_error=False):
            self.raise_error = raise_error
            self.path = None

        def save_screenshot(self, path):
            if self.raise_error:
                raise RuntimeError('截图失败')
            self.path = path
            with open(path, 'wb') as f:
                f.write(b'\x89PNG\r\n')

    shot = ShotDriver()
    saved_path = core.save_diagnostic_screenshot(shot, '未识别页面')
    check('诊断截图会真的写文件',
          bool(saved_path) and os.path.exists(saved_path), saved_path)
    check('截图文件名带标签前缀',
          os.path.basename(saved_path).startswith('未识别页面_'), os.path.basename(saved_path))
    check('截图落在 record/诊断截图 下',
          os.path.join('record', '诊断截图') in saved_path, saved_path)

    bad = core.save_diagnostic_screenshot(ShotDriver(raise_error=True), '出错')
    check('截图失败时返回空串不抛异常', bad == '', bad)
    check('driver 为 None 时返回空串', core.save_diagnostic_screenshot(None, 'x') == '')

    # ---------- 10) 子进程输出落盘 ----------
    folder = tempfile.mkdtemp(prefix='xxt_runner_log_')
    log_path = os.path.join(folder, 'acc_x', '运行日志.log')
    runner_mod.append_output_log(log_path, '第一行\n第二行\n', stamp='12:00:00')
    lines = open(log_path, encoding='utf-8').read().splitlines()
    check('日志按行写入并带时间戳',
          lines[:2] == ['12:00:00 第一行', '12:00:00 第二行'], lines)

    original_limit = runner_mod.OUTPUT_LOG_LIMIT
    runner_mod.OUTPUT_LOG_LIMIT = 10
    try:
        runner_mod.append_output_log(log_path, 'x' * 200, stamp='12:00:01')
    finally:
        runner_mod.OUTPUT_LOG_LIMIT = original_limit
    check('超过上限会轮转成 .old', os.path.exists(log_path + '.old'))

    # ---------- 12) 页面身份 / 卡住判定（2026-11-05 修复「课程被误结束」） ----------
    class IdentityDriver:
        def __init__(self, url='', srcs=()):
            self.current_url = url
            self.srcs = srcs
            self.switch_to = SwitchStub()

        def find_elements(self, by, value):
            if by == By.TAG_NAME and value == 'iframe':
                return [Node(attrs={'src': s}) for s in self.srcs]
            return []

    id1 = core._page_identity(IdentityDriver(
        'https://mooc1.chaoxing.com/mycourse/studentstudy?chapterId=1249726699&courseId=2',
        ('https://mooc1.chaoxing.com/ananas/modules/video/index.html?v=2026-1030-1154&objectId=abc',)))
    check('页面身份能提取 chapterId / objectId / courseId',
          'chapterid=1249726699' in id1 and 'objectid=abc' in id1 and 'courseid=2' in id1, id1)
    id2 = core._page_identity(IdentityDriver(
        'https://mooc1.chaoxing.com/mycourse/studentstudy?chapterId=1249726719&courseId=2',
        ('https://mooc1.chaoxing.com/ananas/modules/video/index.html?v=2026-1030-1154&objectId=abc',)))
    check('模块 src 相同但章节不同 -> 页面身份不同', id1 != id2, (id1, id2))
    noisy = core._page_identity(IdentityDriver(
        'https://x/visit/courses/study?s=aaa&chapterId=1&ktoken=bbb'))
    check('随机 s/ktoken 不参与身份（刷新不会假装有进展）',
          'chapterid=1' in noisy and 'aaa' not in noisy and 'bbb' not in noisy, noisy)
    check('取不到稳定参数时返回空串（退回旧指纹）',
          core._page_identity(IdentityDriver('https://x/y', ('a.html',))) == '')
    id_a = core._page_identity(IdentityDriver('', (
        'https://x/studentstudy?chapterId=1249726699&courseId=2',
        'https://x/knowledge/cards?clazzid=155218192',)))
    id_b = core._page_identity(IdentityDriver('', (
        'https://x/knowledge/cards?clazzid=155218192',
        'https://x/studentstudy?chapterId=1249726699&courseId=2',)))
    check('iframe 顺序抖动不改变页面身份（排序后拼接）',
          id_a == id_b and id_a != '', (id_a, id_b))

    def run_case(pages, max_clicks, refresh_changes=False, refresh_identity_empty=False):
        """纯桩跑 run()：pages = [(page_message, identity, signature), ...]。"""
        class RunDriver:
            def __init__(self):
                self.current_url = ''
                self.switch_to = SwitchStub()
                self.refreshes = 0
                self.shots = []

            def find_elements(self, by, value):
                return []

            def refresh(self):
                self.refreshes += 1

        class FakeTime:
            def __init__(self, real):
                self._real = real

            def sleep(self, seconds):
                pass

            def __getattr__(self, name):
                return getattr(self._real, name)

        d = RunDriver()
        state = {'i': 0, 'clicks': 0, 'refreshed': False}

        def cur():
            return pages[min(state['i'], len(pages) - 1)]

        def fake_click(drv, pf):
            state['clicks'] += 1
            state['i'] = min(state['i'] + 1, len(pages) - 1)
            return state['clicks'] < max_clicks

        def fake_identity(drv):
            if state['refreshed']:
                if refresh_identity_empty:
                    return ''
                if refresh_changes:
                    return 'chapterid=after_refresh'
            return cur()[1]

        def refresh_with_flag():
            state['refreshed'] = True
            RunDriver.refresh(d)

        d.refresh = refresh_with_flag
        patched = ('delete_face_popup', 'image_viewer_is_open', 'check_chapter_active',
                   'wait_page_message', '_content_signature', '_page_identity',
                   'describe_page', 'save_diagnostic_screenshot', 'dispatch_page',
                   'click_next_page', 'delete_record', '_looks_like_home_page',
                   '_looks_like_course_home')
        saved = {name: getattr(core, name) for name in patched}
        saved_time = core.time
        try:
            core.delete_face_popup = lambda *a, **k: None
            core.image_viewer_is_open = lambda *a: False
            core.check_chapter_active = lambda *a: True
            core.wait_page_message = lambda drv: cur()[0]
            core._content_signature = lambda drv: cur()[2]
            core._page_identity = fake_identity
            core.describe_page = lambda drv: '诊断'
            core.save_diagnostic_screenshot = lambda drv, tag: d.shots.append(tag) or ''
            core.dispatch_page = lambda *a, **k: None
            core.click_next_page = fake_click
            core.delete_record = lambda: None
            core._looks_like_home_page = lambda drv: False
            core._looks_like_course_home = lambda drv: False
            core.time = FakeTime(time)
            result = core.run(d, '答题', '课程', '', False, False, '', '跳过讨论',
                              '', False, 1, False)
        finally:
            for name, fn in saved.items():
                setattr(core, name, fn)
            core.time = saved_time
        return result, state, d

    video_sig = '|0|1|https://mooc1.chaoxing.com/ananas/modules/video/index.html?v=2026'
    moving = [({'视频': 'x'}, 'chapterid=%d' % n, video_sig) for n in (1, 2, 3, 4)]
    result, state, d = run_case(moving, max_clicks=4)
    check('不同章节的同类视频页不会累积成「卡住」',
          result == 'done' and state['clicks'] == 4 and d.refreshes == 0,
          (result, state['clicks'], d.refreshes))

    stuck = [({'视频': 'x'}, 'chapterid=1', video_sig)] * 4
    result, state, d = run_case(stuck, max_clicks=99)
    check('真卡住时先刷新、仍卡住返回 lost（不再 return done 结束课程）',
          result == 'lost' and d.refreshes == 1 and '页面卡住' in d.shots,
          (result, d.refreshes, d.shots))

    result, state, d = run_case(stuck * 2, max_clicks=5, refresh_changes=True)
    check('刷新后页面变了就继续学习，不结束课程',
          result == 'done' and d.refreshes == 1, (result, d.refreshes))

    result, state, d = run_case(stuck, max_clicks=99, refresh_identity_empty=True)
    check('刷新后参数还没加载完（identity 为空）不误判换页，仍返回 lost',
          result == 'lost' and d.refreshes == 1, (result, d.refreshes))

    mixed = [({'视频': 'x'}, 'chapterid=1', video_sig),
             ({'视频': 'x'}, 'chapterid=1', video_sig),
             ({}, '', ''),
             ({'视频': 'x'}, 'chapterid=1', video_sig),
             ({'视频': 'x'}, 'chapterid=1', video_sig),
             ({'视频': 'x'}, 'chapterid=1', video_sig)]
    result, state, d = run_case(mixed, max_clicks=5)
    check('未识别页会重置卡住计数，不再跨页累积到 3 次',
          result == 'done' and state['clicks'] == 5 and d.refreshes == 0,
          (result, state['clicks'], d.refreshes))

    print('---')
    if FAILS:
        print('FAILED: %d' % len(FAILS), FAILS)
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
