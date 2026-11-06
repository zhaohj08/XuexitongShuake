# -*- coding: utf-8 -*-
"""章节测验「取答案」链路的回归测试（纯桩，不联网、不启动浏览器）。

覆盖 2026-10-30 第 1 批修复：
  1. `_as_answer_list()`：只做字面量解析（ast.literal_eval），畸形/恶意返回不执行任何代码；
  2. `_split_batch_answer()`：批量答案必须与题目数一致，末尾多余的 '/' 才容忍；
  3. `use_deepseek()`：段数对不上时**逐题提问**，不再按 '/' 的位置硬回填（旧实现少一段越界、
     多一段静默错位）；
  4. 缓存策略（用户选定 b）：只缓存题库/接口命中的答案，AI 兜底答案不写缓存。

用法：C:/Python315/python.exe tests/test_quiz_answer_backfill.py
"""
import asyncio
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

os.environ['XXT_HOME'] = tempfile.mkdtemp(prefix='xxt_test_home_')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from task.tool import ai_wen_da
from task.tool.ai_wen_da import AnswerResult, AutoAnswer, Question
import task.quiz_ai as quiz_ai

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


def make_answer(no_answer, types, titles, options):
    """构造一个只用于调用 use_deepseek 的 Answer 实例（不碰浏览器）。"""
    answer = object.__new__(quiz_ai.Answer)
    answer.API_KEY = 'sk-test'
    answer.no_answer_dit = no_answer
    answer.num_answer_dit = {}
    answer.questionType_list = types
    answer.only_title_text = titles
    answer.num_option_dit = options
    return answer


def main():
    # ---------- 1) 答案解析：只认字面量，绝不执行代码 ----------
    check('列表原样返回', quiz_ai._as_answer_list(['A', 'B']) == ['A', 'B'])
    check('解析字面量列表', quiz_ai._as_answer_list("['A','B']") == ['A', 'B'])
    check('裸答案当单个答案', quiz_ai._as_answer_list('A') == ['A'])
    check('空串视为无答案', quiz_ai._as_answer_list('') == [])
    check('None 视为无答案', quiz_ai._as_answer_list(None) == [])
    check('畸形列表不抛异常', isinstance(quiz_ai._as_answer_list("['A','B'"), list))

    marker = os.path.join(tempfile.mkdtemp(prefix='xxt_eval_'), 'executed.txt')
    payload = "__import__('builtins').open(%r, 'w').write('x')" % marker
    result = quiz_ai._as_answer_list(payload)
    check('恶意字符串不会被执行', not os.path.exists(marker))
    check('恶意字符串被当成普通文本', isinstance(result, list), result)

    # ---------- 2) 批量答案分段校验 ----------
    split = quiz_ai.Answer._split_batch_answer
    check('段数正确', split('C/ABCD', 2) == ['C', 'ABCD'])
    check('容忍末尾多余的 /', split('C/ABCD/', 2) == ['C', 'ABCD'])
    check('段数偏少 -> 不猜位置', split('C', 2) is None)
    check('段数偏多 -> 不猜位置', split('C/ABCD/B', 2) is None)
    check('空返回 -> 降级', split('', 2) is None)
    check('整体被方括号包住也能拆', split('[C/ABCD]', 2) == ['C', 'ABCD'])

    # ---------- 3) use_deepseek：段数正确时按顺序回填 ----------
    calls = []
    batch_answer = ['C/ABCD']          # 改这个值就能模拟 AI 少给/多给段数

    def fake_deepseek(api, title, typ):
        calls.append(typ)
        if typ == 'all':
            return batch_answer[0]
        return "['B']"

    original = quiz_ai.DeepSeekAsk
    quiz_ai.DeepSeekAsk = fake_deepseek
    try:
        a = make_answer({0: '第一题', 1: '第二题'}, ['单选题', '多选题'],
                        ['1+1=?', '选全部'], [['A.1', 'B.2'], ['A.甲', 'B.乙']])
        a.use_deepseek()
        check('段数正确：第 1 题 = [C]', a.num_answer_dit[0] == ['C'], a.num_answer_dit[0])
        check('段数正确：第 2 题 = [ABCD]', a.num_answer_dit[1] == ['ABCD'], a.num_answer_dit[1])
        check('段数正确时不额外逐题问', calls == ['all'], calls)

        # ---------- 4) 段数不符：逐题兜底，不越界、不错位 ----------
        calls.clear()
        batch_answer[0] = 'C'          # 两题只给一段：旧实现会 IndexError
        a = make_answer({0: '第一题', 1: '第二题'}, ['单选题', '多选题'],
                        ['1+1=?', '选全部'], [['A.1', 'B.2'], ['A.甲', 'B.乙']])
        try:
            a.use_deepseek()
            ok = True
            err = ''
        except Exception as e:          # noqa: BLE001 - 旧实现这里会 IndexError
            ok = False
            err = repr(e)
        check('段数偏少不会越界', ok, err)
        check('段数偏少改走逐题', calls == ['all', '单选题', '多选题'], calls)
        check('逐题兜底答案已回填', a.num_answer_dit == {0: ['B'], 1: ['B']}, a.num_answer_dit)

        # 多给一段（非空）：同样不许按位置硬回填
        calls.clear()
        batch_answer[0] = 'C/ABCD/B'
        a = make_answer({0: '第一题', 1: '第二题'}, ['单选题', '多选题'],
                        ['1+1=?', '选全部'], [['A.1', 'B.2'], ['A.甲', 'B.乙']])
        a.use_deepseek()
        check('段数偏多也改走逐题', calls == ['all', '单选题', '多选题'], calls)
        check('段数偏多没有错位', a.num_answer_dit == {0: ['B'], 1: ['B']}, a.num_answer_dit)
        # 单题时整段就是答案（不再重复提问一次）
        calls.clear()
        batch_answer[0] = 'A,B'
        a = make_answer({0: '唯一一题'}, ['多选题'], ['选全部'], [['A.甲', 'B.乙']])
        a.use_deepseek()
        check('单题时整段即答案，不重复提问', calls == ['all'], calls)
        check('单题多选答案按逗号拆分', a.num_answer_dit[0] == ['A', 'B'], a.num_answer_dit[0])
        batch_answer[0] = 'C/ABCD'
    finally:
        quiz_ai.DeepSeekAsk = original

    # ---------- 5) 缓存策略：题库结果缓存、AI 结果不缓存 ----------
    cached = []
    original_cache = ai_wen_da.AnswerAPI.cache_answer
    ai_wen_da.AnswerAPI.cache_answer = lambda self, question, answer: cached.append(answer)
    try:
        async def no_cache(question):
            return AnswerResult(form='本地缓存', answer=[], msg='未找到')

        async def bank_result(question):
            return [AnswerResult(form='一之题库', answer=['A'])]

        async def empty(question):
            return []

        def matcher(results, question):
            valid = [r for r in results if r.answer]
            if not valid:
                return {'res': results, 'haveAnswer': False}
            return {'res': results, 'haveAnswer': True, 'form': valid[0],
                    'answer': valid[0].answer, 'answerType': 'text'}

        api = AutoAnswer()
        # 直接挂到实例上（不走描述符绑定），签名与真实方法保持一致
        api.api.get_cache_answer = no_cache
        api.api.get_answers_free = bank_result
        api.api.get_free_answers = empty
        api.matcher.api_answer_match = matcher
        api.api.cache_answer = lambda question, answer: cached.append(answer)

        question = Question(type='0', question='1+1=?', options=['A.1', 'B.2'], API='sk-test')
        cached.clear()
        asyncio.run(api.auto_answer_question(question))
        check('题库命中的答案会写缓存', cached == [['A']], cached)

        # 题库全空 -> 走 AI 兜底 -> 不应写缓存
        api.api.get_answers_free = empty
        api.use_deepseek = lambda question, api_key: [
            AnswerResult(form='Deepseek', answer=['B'], cacheable=False)]
        cached.clear()
        asyncio.run(api.auto_answer_question(question))
        check('AI 兜底答案不写缓存', cached == [], cached)
    finally:
        ai_wen_da.AnswerAPI.cache_answer = original_cache

    print('---')
    if FAILS:
        print('FAILED: %d' % len(FAILS), FAILS)
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
