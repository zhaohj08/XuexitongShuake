# -*- coding: utf-8 -*-
"""课程列表入口的回归测试（纯桩，无浏览器）。

背景（2026-10-31 两次修复）：
  1. 原实现写死 `class='course-tab'` 且要求文字**完全等于**「我学的课」，
     换个版本/皮肤就点不到标签，后面一个课程卡片都找不到；
  2. 只在一个固定 iframe（`frame_content`）里找标签和卡片，而新版把菜单放在顶层文档，
     于是标签 0 个、卡片 0 个 → 打印「未找到课程」。

现在：跨帧（top / frame_content / iframe）按关键字点标签，跨帧按多套选择器找课程卡片，
找不到时输出页面结构诊断。

用法：C:/Python315/python.exe tests/test_course_entry.py
"""
import io
import os
import sys
import tempfile
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ['XXT_HOME'] = tempfile.mkdtemp(prefix='xxt_course_')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from selenium.common.exceptions import ElementClickInterceptedException, NoSuchElementException
from selenium.webdriver.common.by import By

import main as core

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


class El:
    def __init__(self, text='', title='', visible=True, click_exc=None, cls=''):
        self.text = text
        self.title = title
        self.visible = visible
        self.click_exc = click_exc
        self.cls = cls
        self.clicks = 0

    def is_displayed(self):
        return self.visible

    def get_attribute(self, name):
        if name == 'title':
            return self.title
        if name == 'class':
            return self.cls
        if name == 'src':
            return ''
        return ''

    def click(self):
        if self.click_exc:
            raise self.click_exc
        self.clicks += 1

    def find_elements(self, by, value):
        return []


class Switch:
    def frame(self, arg):
        pass

    def default_content(self):
        pass

    def window(self, handle):
        pass


class Driver:
    """tabs 按关键字索引需要返回的标签元素；courses 是课程卡片元素。"""

    def __init__(self, tabs=None, courses=None, frame_raises=False):
        self.tabs = tabs or {}
        self.courses = courses or []
        self.frame_raises = frame_raises
        self.switch_to = Switch()
        self.js_clicks = []
        self.js_text_clicks = []

    def find_element(self, by, value):
        raise NoSuchElementException(value)

    def find_elements(self, by, value):
        if by == By.XPATH:
            # 关键字点击走 XPath contains
            for keyword, nodes in self.tabs.items():
                if keyword in value:
                    return list(nodes)
            return []
        if by == By.CSS_SELECTOR:
            if 'course' in value.lower() or 'cour' in value:
                return list(self.courses)
            if 'iframe' in value:
                return []
            return []
        if by == By.TAG_NAME:
            return []
        return []

    def execute_script(self, script, *args):
        if 'click' in script and args:
            self.js_clicks.append(args[0])
        return ''


def main():
    # ---------- 1) 关键字点击 ----------
    tab = El('我学的课')
    check('文字完全相等时能点到',
          core._click_text_keyword(Driver({'我学的课': [tab]}), ('我学的课',), timeout=1) is True)
    check('点到的就是那个标签', tab.clicks == 1, tab.clicks)

    tab = El('我学的课(12)')
    check('文字带角标也能点到',
          core._click_text_keyword(Driver({'我学的课': [tab]}), ('我学的课',), timeout=1) is True)

    tab = El('我的课程')
    check('「我的课程」也能命中',
          core._click_text_keyword(Driver({'我的课程': [tab]}), core.COURSE_TAB_KEYWORDS,
                                   timeout=1) is True and tab.clicks == 1)

    big = El('我学的课 课程 作业 考试 讨论 章节 资料 更多 设置 帮助 退出 登录 首页 消息 通知')
    small = El('我学的课')
    core._click_text_keyword(Driver({'我学的课': [big, small]}), ('我学的课',), timeout=1)
    check('跳过包住整页的大容器', big.clicks == 0 and small.clicks == 1,
          (big.clicks, small.clicks))

    blocked = El('我学的课', click_exc=ElementClickInterceptedException('遮罩'))
    drv = Driver({'我学的课': [blocked]})
    check('普通点击失败时退回 JS 点击',
          core._click_text_keyword(drv, ('我学的课',), timeout=1) is True
          and blocked in drv.js_clicks, drv.js_clicks)

    check('找不到关键字返回 False',
          core._click_text_keyword(Driver(), ('我学的课',), timeout=0.6) is False)

    # ---------- 2) 课程卡片收集：多套选择器 + title/text ----------
    class CardDriver:
        def __init__(self, nodes):
            self.nodes = nodes

        def find_elements(self, by, value):
            return self.nodes if by == By.CSS_SELECTOR else []

    cards = core._collect_course_cards(CardDriver([
        El(text='高等数学', title='高等数学', cls='course-name'),
        El(text='形势与政策', title='', cls='courseName'),
        El(text='', title='', cls='courseName'),
        El(text='很长' * 40, cls='course-card'),      # 80 字，明显是容器而不是课程名
    ]))
    check('按 title 取课程名', '高等数学' in cards, list(cards))
    check('没有 title 时取文字', '形势与政策' in cards, list(cards))
    check('空名字/超长容器被过滤', len(cards) == 2, list(cards))

    # ---------- 3) 课程定位 ----------
    card = El(text='高等数学', title='高等数学', cls='course-name')
    drv = Driver(courses=[card])
    found, names = core._locate_course(drv, '高等数学', timeout=2)
    check('能定位到课程卡片', found is True and '高等数学' in names, names)
    check('定位后用 JS 点击卡片', card in drv.js_clicks, drv.js_clicks)

    found, names = core._locate_course(Driver(courses=[El(title='大学英语')]), '高等数学', timeout=0.6)
    check('找不到时返回 False 并带回看到的课程',
          found is False and names == ['大学英语'], names)

    # ---------- 4) 整条选课流程 ----------
    tab = El('我学的课')
    card = El(text='高等数学', title='高等数学', cls='course-name')
    drv = Driver({'我学的课': [tab]}, [card])

    saved = {}
    core._save_course_names = lambda names, phone: saved.setdefault('names', list(names))
    core.set_speed = lambda *a, **k: None

    buf = io.StringIO()
    with redirect_stdout(buf):
        core.choice_course(drv, '高等数学', '1', '章节', '13800000000')
    log = buf.getvalue()

    check('流程里点到了「我学的课」', tab.clicks == 1, tab.clicks)
    check('打印已进入课程列表', '已进入「我学的课」列表' in log, log.strip()[-80:])
    check('打印了已选择课程', '您已选择《高等数学》' in log, log.strip()[-80:])
    check('课程列表被保存', saved.get('names') == ['高等数学'], saved)

    # ---------- 5) 点完必须验证：列表没出现就不算成功 ----------
    class NoEffectDriver(Driver):
        """点了但页面没反应（模拟点击 div 不触发菜单跳转）。"""

        def find_elements(self, by, value):
            if by == By.XPATH:
                for keyword, nodes in self.tabs.items():
                    if keyword in value:
                        return list(nodes)
                return []
            return []

    no_effect = NoEffectDriver({'我学的课': [El('我学的课')]})
    check('点了没反应时 _click_course_tab 返回 False',
          core._click_course_tab(no_effect, timeout=1) is False)

    class JumpDriver(Driver):
        """点了之后课程卡片出现（模拟真的跳进了「我学的课」）。"""

        def find_elements(self, by, value):
            if by == By.XPATH:
                for keyword, nodes in self.tabs.items():
                    if keyword in value:
                        return list(nodes)
                return []
            if by == By.CSS_SELECTOR:
                return list(self.courses)
            return []

    tab = El('我学的课')
    jump = JumpDriver({'我学的课': [tab]}, [El(title='高等数学', cls='course-name')])
    check('列表出现后才算成功', core._click_course_tab(jump, timeout=4) is True)
    check('成功路径只点一次', tab.clicks == 1, tab.clicks)

    # ---------- 6) 诊断信息 ----------
    desc = core.describe_course_page(Driver())
    check('诊断字符串含 url/title/frames',
          all(k in desc for k in ('url=', 'title=', 'frames=')), desc[:120])

    print('---')
    if FAILS:
        print('FAILED: %d' % len(FAILS), FAILS)
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
