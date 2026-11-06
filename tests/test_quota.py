# -*- coding: utf-8 -*-
"""API 额度闸门 + 「无法作答的题型直接跳过」的回归测试。

背景（2026-10-31 用户实测）：一场 10 题全是**简答题**的章末测试，程序对每道题
反复「题库 → DeepSeek → 未找到答案」，10 道题循环刷了很多次请求，白白消耗 API 额度。
用户要求：这类题直接跳过；任何时候都不允许把额度刷爆。

覆盖：
1. `task.tool.quota` 的三道闸门（总数 / 每分钟 / 同题重试次数）与 `reset`；
2. `DeepSeekAsk` 在额度用尽时**不联网**，直接返回空；
3. `Answer.use_ai_wen_da()` 跳过简答/论述/填空/名词解释/未知题型，不去题库；
4. `Answer.use_deepseek()` 单次最多批量问 15 道。

用法：C:/Python315/python.exe tests/test_quota.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ['XXT_HOME'] = tempfile.mkdtemp(prefix='xxt_quota_')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

import task.quiz_ai as quiz_ai
import task.tool.DeepSeekAsk as ds
from task.tool import quota

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


def main():
    # ---------- 1) 题目指纹 ----------
    a = quota.question_key('求不定积分 ∫x dx')
    b = quota.question_key('求不定积分 ∫x dx')
    c = quota.question_key('另一道题')
    check('同一道题指纹相同', a == b and len(a) == 16, a)
    check('不同题指纹不同', a != c)
    check('空文本指纹为空', quota.question_key('') == '')

    # ---------- 2) 默认不设总量上限（按频率限流） ----------
    check('默认不设总量上限', quota.MAX_TOTAL is None, quota.MAX_TOTAL)
    q = quota.ApiQuota(max_total=None, max_per_minute=10000, max_per_question=10000)
    results = [q.allow('', '题库') for _ in range(200)]
    check('没有总量上限：200 次都放行', all(results), sum(1 for r in results if r))
    check('统计累计次数', q.stats()['total'] == 200, q.stats()['total'])

    # 仍然支持"显式设置总量上限"（留给以后的极端兜底）
    q = quota.ApiQuota(max_total=3, max_per_minute=100, max_per_question=100)
    results = [q.allow('', '题库') for _ in range(4)]
    check('显式设置上限后仍会拒绝', results == [True, True, True, False], results)

    # ---------- 3) 每分钟上限 + 窗口恢复 ----------
    q = quota.ApiQuota(max_total=None, max_per_minute=2, max_per_question=100)
    first = [q.allow('', '题库') for _ in range(3)]
    check('每分钟上限生效', first == [True, True, False], first)
    check('被拒原因是 minute', q.last_reason == 'minute', q.last_reason)
    q.window_start -= 61          # 模拟过了 1 分钟
    check('过了 1 分钟自动恢复', q.allow('', '题库') is True)

    # ---------- 4) acquire：超频时等待窗口而不是丢题 ----------
    import time as _time
    q = quota.ApiQuota(max_total=None, max_per_minute=1, max_per_question=100)
    check('acquire 第一次放行', q.acquire('', '题库') is True)
    began = _time.time()
    check('wait=False 时立刻拒绝', q.acquire('', '题库', wait=False) is False)
    q.window_start -= 59.6        # 距离窗口重置只剩 0.4 秒
    ok = q.acquire('', '题库', wait=True, max_wait=5)
    spent = _time.time() - began
    check('acquire 会等到下一个窗口再放行', ok is True and spent >= 0.3, round(spent, 2))

    # 同题超限不等待，直接拒绝
    q = quota.ApiQuota(max_total=None, max_per_minute=100, max_per_question=2)
    key = quota.question_key('同一道题')
    q.acquire(key, 'deepseek')
    q.acquire(key, 'deepseek')
    check('同题超限时 acquire 直接拒绝且不等待',
          q.acquire(key, 'deepseek', wait=True, max_wait=2) is False)

    # ---------- 5) 同题重试上限 ----------
    q = quota.ApiQuota(max_total=None, max_per_minute=100, max_per_question=2)
    key = quota.question_key('同一道题')
    got = [q.allow(key, 'deepseek') for _ in range(3)]
    check('同一道题最多问 2 次', got == [True, True, False], got)
    check('别的题不受影响', q.allow(quota.question_key('另一道'), 'deepseek') is True)

    # ---------- 6) reset ----------
    quota.reset()
    check('reset 后计数清零', quota.stats()['total'] == 0, quota.stats()['total'])

    # ---------- 7) 频率被限死时 DeepSeekAsk 不联网 ----------
    saved_rate = quota._QUOTA.max_per_minute
    saved_count = quota._QUOTA.window_count
    saved_question = quota._QUOTA.max_per_question
    quota._QUOTA.max_per_minute = 0      # 任何请求都被限流
    quota._QUOTA.window_count = 0
    quota._QUOTA.max_per_question = 0
    try:
        answer = ds.DeepSeekAsk('sk-test-key', '【单选题】题目A B C D', '单选题')
    finally:
        quota._QUOTA.max_per_minute = saved_rate
        quota._QUOTA.window_count = saved_count
        quota._QUOTA.max_per_question = saved_question
    check('被限流时直接返回空列表（不发请求）', answer == '[]', answer)

    # ---------- 7) 无法作答的题型不查题库 ----------
    check('跳过类型覆盖简答/论述/填空/名词解释/未知',
          all(t in quiz_ai.Answer.UNANSWERABLE_TYPES
              for t in ('简答题', '论述题', '填空题', '名词解释', '未知')),
          quiz_ai.Answer.UNANSWERABLE_TYPES)

    ans = object.__new__(quiz_ai.Answer)
    ans.all_title_dit = {0: '简答题题干', 1: '选择题题干'}
    ans.image_questions = set()
    ans.skipped_questions = set()
    ans.questionType_list = ['简答题', '单选题']
    ans.num_answer_dit = {}
    ans.times = 0
    ans.work_choice = 'DeepSeek AI'
    called = []
    ans._search_bank = lambda index: called.append(index) or []
    ans.use_ai_wen_da()
    check('简答题根本不查题库', called == [1], called)
    check('简答题答案置空', ans.num_answer_dit.get(0) == [], ans.num_answer_dit.get(0))

    # ---------- 8) 批量问 AI 的数量上限 ----------
    ans = object.__new__(quiz_ai.Answer)
    ans.no_answer_dit = {i: '题干%d' % i for i in range(20)}
    ans.questionType_list = ['单选题'] * 20
    ans.num_option_dit = {i: ['A.甲', 'B.乙'] for i in range(20)}
    ans.only_title_text = ['t'] * 20
    ans.num_answer_dit = {}
    ans.API_KEY = 'sk-test-key'
    asked = []
    saved_ask = quiz_ai.DeepSeekAsk
    quiz_ai.DeepSeekAsk = lambda *a, **k: ''      # 模拟 AI 没返回，触发逐题提问
    ans._ask_one = lambda key: asked.append(key) or []
    try:
        ans.use_deepseek()
    finally:
        quiz_ai.DeepSeekAsk = saved_ask
    check('单次最多批量问 15 道', len(asked) == quiz_ai.Answer.MAX_AI_BATCH, len(asked))

    # ---------- 9) 特殊题型（计算题等）：跳过、不调 AI ----------
    check('计算题被归为 unknown',
          quiz_ai.Answer.question_kind('计算题') == 'unknown')
    check('单选题仍是 choice', quiz_ai.Answer.question_kind('单选题') == 'choice')
    check('简答题归为 essay', quiz_ai.Answer.question_kind('简答题') == 'essay')
    check('UNANSWERABLE_TYPES 覆盖计算题',
          '计算题' in quiz_ai.Answer.UNANSWERABLE_TYPES, quiz_ai.Answer.UNANSWERABLE_TYPES)

    ans = object.__new__(quiz_ai.Answer)
    ans.skipped_questions = {0}
    ans.questionType_list = ['计算题']
    ans.image_questions = set()
    ans.driver = None
    check('跳过的题不会进入答题/图片流程', ans.finish_title(0) is False)

    ans = object.__new__(quiz_ai.Answer)
    ans.all_title_dit = {0: '计算题题干', 1: '选择题题干'}
    ans.image_questions = set()
    ans.skipped_questions = {0}
    ans.questionType_list = ['计算题', '单选题']
    ans.num_answer_dit = {}
    ans.times = 0
    ans.work_choice = 'DeepSeek AI'
    called = []
    ans._search_bank = lambda index: called.append(index) or []
    ans.use_ai_wen_da()
    check('跳过的题不查题库', called == [1], called)

    # ---------- 10) 「能不能靠选项作答」的三重判据 ----------
    class JsEl:
        """execute_script 依次返回预设值（模拟页面里有没有编辑器/几个真选项）。"""

        def __init__(self, values):
            self.values = list(values)
            self.parent = self

        def execute_script(self, *args):
            return self.values.pop(0) if self.values else None

    check('有富文本作答框 -> 不能靠选项作答',
          quiz_ai.Answer._has_rich_editor(JsEl([True])) is True)
    check('没有作答框 -> False',
          quiz_ai.Answer._has_rich_editor(JsEl([False])) is False)
    check('统计真实选项数量', quiz_ai.Answer._count_real_options(JsEl([4])) == 4)
    check('编辑器里没有选项时计数为 0',
          quiz_ai.Answer._count_real_options(JsEl([0])) == 0)

    ans = object.__new__(quiz_ai.Answer)
    check('有编辑器 -> _can_answer_by_options 为 False',
          ans._can_answer_by_options(JsEl([True, 5])) is False)
    check('无编辑器且 4 个选项 -> True',
          ans._can_answer_by_options(JsEl([False, 4])) is True)
    check('无编辑器但选项不足 2 个 -> False',
          ans._can_answer_by_options(JsEl([False, 1])) is False)

    print('---')
    if FAILS:
        print('FAILED: %d' % len(FAILS), FAILS)
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
