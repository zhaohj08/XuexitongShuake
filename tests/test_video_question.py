# -*- coding: utf-8 -*-
"""视频内弹题「固定随机作答」的回归测试（纯桩，无浏览器）。

背景：视频中弹出的题目平台没有错题校验——选错只提示，继续选下一个就能一路试到正确，
所以固定走「逐个选项提交」的穷举，不调用 AI。早期的 AI 分支在提交后仍会继续跑随机分支，
反而把答案覆盖掉，已删除。

断言：
  1) watch_vido 不再引入 DeepSeekAsk，也没有 get_answer / finish_video_question；
  2) check_video_question 只接收 driver（不再吃 API / video_title_choice）；
  3) 单选题 / 判断题：每个选项点一次、每次点完提交一次；
  4) 多选题：按组合穷举提交，选项按对称差集切换；
  5) 每次提交后有留白时间（让平台先弹出「答错」提示）；
  6) 页面没有弹题时不抛异常、不误点。

用法：C:/Python315/python.exe tests/test_video_question.py
"""
import inspect
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

# 数据目录指到临时目录，避免污染工程里的 task/record
os.environ['XXT_HOME'] = tempfile.mkdtemp(prefix='xxt_test_home_')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

import task.watch_vido as vido

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


class Node:
    """最小元素桩：按 (By, value) 路由 find_element / find_elements。"""

    def __init__(self, text='', routes=None):
        self.text = text
        self.clicks = 0
        self._routes = routes or {}

    def click(self):
        self.clicks += 1

    def find_element(self, by, value):
        if (by, value) in self._routes:
            return self._routes[(by, value)]
        raise NoSuchElementException('no such element: %s=%s' % (by, value))

    def find_elements(self, by, value):
        item = self._routes.get((by, value))
        if item is None:
            return []
        return item if isinstance(item, list) else [item]


class FakeTime:
    """替换模块里的 time，记录 sleep 次数，其余接口透传。"""

    def __init__(self):
        self.sleeps = 0

    def sleep(self, _seconds):
        self.sleeps += 1

    def __getattr__(self, name):
        import time as real_time
        return getattr(real_time, name)


def build_topic(question_type, option_count):
    options = [Node(text='选项%d' % i) for i in range(option_count)]
    ul = Node(routes={(By.TAG_NAME, 'li'): options})
    submit = Node()
    continue_btn = Node()
    topic = Node(routes={
        (By.CLASS_NAME, 'tkTopic_type'): Node(text=question_type),
        (By.CLASS_NAME, 'tkItem_ul'): ul,
        (By.ID, 'videoquiz-submit'): submit,
        (By.ID, 'videoquiz-continue'): continue_btn,
    })
    driver = Node(routes={(By.CLASS_NAME, 'tkTopic'): topic})
    return driver, options, submit, continue_btn


def run_case(question_type, option_count):
    driver, options, submit, continue_btn = build_topic(question_type, option_count)
    fake = FakeTime()
    original = vido.time
    vido.time = fake
    try:
        vido.check_video_question(driver)
    finally:
        vido.time = original
    return {
        'option_clicks': [o.clicks for o in options],
        'submits': submit.clicks,
        'continue': continue_btn.clicks,
        'sleeps': fake.sleeps,
    }


def main():
    # 1) AI 分支必须彻底消失
    check('模块不再导入 DeepSeekAsk', not hasattr(vido, 'DeepSeekAsk'))
    check('get_answer 已删除', not hasattr(vido, 'get_answer'))
    check('finish_video_question 已删除', not hasattr(vido, 'finish_video_question'))

    # 2) 签名收敛：视频题不再需要 API 与答题策略
    params = list(inspect.signature(vido.check_video_question).parameters)
    check('check_video_question(driver)', params == ['driver'], params)
    page_params = list(inspect.signature(vido.study_page).parameters)
    check('study_page 不再接收 API / video_title_choice',
          page_params == ['driver', 'course_name', 'lock_screen',
                          'pass_vido', 'speed', 'pass_face'], page_params)
    finish_params = list(inspect.signature(vido.check_vido_finish).parameters)
    check('check_vido_finish 不再接收 API / video_title_choice',
          finish_params == ['driver', 'i', 'time_start', 'total_time',
                            'vido_iframe', 'lock_screen', 'speed', 'pass_face'],
          finish_params)

    # 3) 单选题：3 个选项逐一点击并提交
    r = run_case('单选题', 3)
    check('单选: 每个选项都被点了一次', r['option_clicks'] == [1, 1, 1], r['option_clicks'])
    check('单选: 提交 3 次（穷举到答对）', r['submits'] == 3, r['submits'])
    check('单选: 每次提交后有留白', r['sleeps'] >= 3, r['sleeps'])
    check('单选: 结束后点了继续学习', r['continue'] == 1, r['continue'])

    # 4) 判断题：同样逐项提交
    r = run_case('判断题', 2)
    check('判断: 2 个选项各点一次', r['option_clicks'] == [1, 1], r['option_clicks'])
    check('判断: 提交 2 次', r['submits'] == 2, r['submits'])

    # 5) 多选题：3 个选项 → 全选 + 3 组两两组合 = 4 次提交，
    #    每次只点击与上一次的对称差集（3 + 1 + 2 + 2 = 8 次点击）
    r = run_case('多选题', 3)
    check('多选: 提交 4 次（全选 + 3 组两两）', r['submits'] == 4, r['submits'])
    check('多选: 选项点击总数 = 8（按对称差集切换）', sum(r['option_clicks']) == 8, r['option_clicks'])
    check('多选: 每个选项都至少被点过 2 次', min(r['option_clicks']) >= 2, r['option_clicks'])
    check('多选: 每次提交后有留白', r['sleeps'] >= 4, r['sleeps'])

    # 6) 页面没有弹题：不抛异常、不点击
    driver = Node()          # find_element 直接抛 NoSuchElementException
    fake = FakeTime()
    original = vido.time
    vido.time = fake
    try:
        vido.check_video_question(driver)
        ok = True
        err = ''
    except Exception as e:      # noqa: BLE001 - 这里就是要证明不会抛
        ok = False
        err = repr(e)
    finally:
        vido.time = original
    check('无弹题时不抛异常', ok, err)
    check('无弹题时不产生提交', fake.sleeps == 0, fake.sleeps)

    print('---')
    if FAILS:
        print('FAILED: %d' % len(FAILS), FAILS)
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
