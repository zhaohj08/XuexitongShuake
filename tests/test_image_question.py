# -*- coding: utf-8 -*-
"""图片题「多模态作答」的逻辑回归（纯桩，不联网、不启浏览器）。

覆盖 2026-10-30 第 2 批：
  1. `_parse_choice_letters()`：只认字母 / 多选多字母 / 序号兜底 / 越界丢弃；
  2. `_finish_image_title()`：AI 给字母就点对应选项；给不出时按「随机答题」或「跳过」；
  3. 未配置 API Key（含 `sk-open_deepseek` 哨兵）时**不发起任何请求**。

用法：C:/Python315/python.exe tests/test_image_question.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

os.environ['XXT_HOME'] = tempfile.mkdtemp(prefix='xxt_test_home_')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

import task.quiz_ai as quiz_ai

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


class DriverStub:
    def execute_script(self, *args, **kwargs):
        return None


class QuestionStub:
    def screenshot(self, path):
        with open(path, 'wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n')


def make_answer(work_choice='自动答题', api_key='sk-test', indices=None, relocate=True):
    answer = object.__new__(quiz_ai.Answer)
    answer.API_KEY = api_key
    answer.work_choice = work_choice
    answer.driver = DriverStub()
    answer.image_questions = {1}
    answer.image_unanswered = set()
    answer.num_option_dit = {1: ['', '', '']}
    answer.all_optionWebElementList = [None, [object(), object(), object()]]
    answer._relocate = (lambda n: QuestionStub()) if relocate else (lambda n: None)
    if indices is None:
        answer._ask_image_question = lambda n, q: []
    else:
        answer._ask_image_question = lambda n, q: list(indices)
    answer.clicked = []
    answer._click_option = lambda n, idx: (answer.clicked.append(idx), True)[1]
    return answer


def main():
    parse = quiz_ai.Answer._parse_choice_letters

    # ---------- 1) 字母解析 ----------
    check('单个字母', parse('B', 4) == [1])
    check('带标点', parse('B.', 4) == [1])
    check('中文前缀', parse('答案：B。', 4) == [1])
    check('多选连写', parse('ACD', 4) == [0, 2, 3])
    check('多选带逗号', parse('A,C', 4) == [0, 2])
    check('选项多于 4 个', parse('E', 5) == [4])
    check('越界字母被丢弃', parse('E', 4) == [])
    check('序号兜底', parse('2', 4) == [1])
    check('空串', parse('', 4) == [])
    check('None', parse(None, 4) == [])
    check('重复字母去重', parse('AAB', 4) == [0, 1])
    check('英文句子不误判（answer 里的 e/a）', parse('the answer is C', 4) == [2],
          parse('the answer is C', 4))

    # ---------- 2) AI 给出字母 -> 点对应选项 ----------
    answer = make_answer(indices=[2])
    ok = answer._finish_image_title(1)
    check('AI 给 C 时点第 3 个选项', ok is True and answer.clicked == [2], answer.clicked)
    check('答出来不计入未作答', answer.image_unanswered == set(), answer.image_unanswered)

    # ---------- 3) AI 给不出 + 非随机模式 -> 跳过 ----------
    answer = make_answer(indices=[])
    ok = answer._finish_image_title(1)
    check('AI 无答案时跳过', ok is False and answer.clicked == [], answer.clicked)
    check('跳过的题被记录', answer.image_unanswered == {1}, answer.image_unanswered)

    # ---------- 4) AI 给不出 + 随机答题 -> 随机点一个 ----------
    answer = make_answer(work_choice='随机答题', indices=[])
    ok = answer._finish_image_title(1)
    check('随机答题模式下随机点一个', ok is True and len(answer.clicked) == 1, answer.clicked)
    check('随机点到的是合法下标',
          answer.clicked and 0 <= answer.clicked[0] < 3, answer.clicked)

    # ---------- 5) 定位失败 -> 跳过 ----------
    answer = make_answer(indices=[1], relocate=False)
    ok = answer._finish_image_title(1)
    check('定位失败时不点、记未作答',
          ok is False and answer.clicked == [] and answer.image_unanswered == {1},
          (answer.clicked, answer.image_unanswered))

    # ---------- 6) 哨兵 / 空 key 不发起请求 ----------
    called = []

    def forbidden(*args, **kwargs):
        called.append(True)
        raise AssertionError('未配置 key 时不应该发起多模态请求')

    original_image = quiz_ai.DeepSeekAskImage
    quiz_ai.DeepSeekAskImage = forbidden
    try:
        for key in ('sk-open_deepseek', '', None):
            answer = make_answer(api_key=key)
            answer._save_image_question = lambda n, q: 'dummy.png'
            # make_answer 会把 _ask_image_question 换成桩，这里要走回真实方法
            answer.__dict__.pop('_ask_image_question', None)
            indices = answer._ask_image_question(1, QuestionStub())
            check('哨兵 key 不请求: %r' % (key,), indices == [], indices)
        check('确实没有发起请求', called == [], called)
    finally:
        quiz_ai.DeepSeekAskImage = original_image

    # ---------- 7) 正常 key 会把截图交给多模态并解析 ----------
    seen = {}

    def fake_image(api_key, prompt, paths):
        seen['api'] = api_key
        seen['prompt'] = prompt
        seen['paths'] = paths
        return 'B'

    quiz_ai.DeepSeekAskImage = fake_image
    try:
        answer = make_answer()
        answer._save_image_question = lambda n, q: 'shot.png'
        answer.__dict__.pop('_ask_image_question', None)   # 走真实方法
        indices = answer._ask_image_question(1, QuestionStub())
        check('正常 key 返回下标', indices == [1], indices)
        check('提示词要求只返回字母',
              '只返回正确选项的字母' in seen.get('prompt', ''), seen.get('prompt', '')[:20])
    finally:
        quiz_ai.DeepSeekAskImage = original_image

    print('---')
    if FAILS:
        print('FAILED: %d' % len(FAILS), FAILS)
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
