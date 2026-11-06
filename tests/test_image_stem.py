# -*- coding: utf-8 -*-
"""图片题识别（题干含图片）与「重做测验」崩溃的回归测试。

背景（2026-10-31 用户实测）：
  1. 某场测验题干是「文字 + 公式图片」，程序只取到文字（例如「函数的间断点为()」），
     于是走纯文字搜题 → 答案全错，**没有调用图像 API**；
  2. 第一次提交没及格，程序自动重做时崩溃：
     `TypeError: expected string or bytes-like object, got 'float'`
     —— `Answer.__init__` 对已经转成 float 的 `after_finish_question` 再跑了一次 `re.search`。

用法：C:/Python315/python.exe tests/test_image_stem.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ['XXT_HOME'] = tempfile.mkdtemp(prefix='xxt_stem_')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from task import quiz_ai

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


class Size:
    def __init__(self, width, height):
        self.width = width
        self.height = height


class Img:
    def __init__(self, width, height):
        self.size = {'width': width, 'height': height}


class El:
    def __init__(self, images=(), js_result=None, js_raises=False):
        self.images = [Img(*size) for size in images]
        self.js_result = js_result
        self.js_raises = js_raises
        self.parent = self

    def find_elements(self, by, value):
        return list(self.images)

    def execute_script(self, *args):
        if self.js_raises:
            raise RuntimeError('js failed')
        return self.js_result


def main():
    # ---------- 1) 重做时的比例解析 ----------
    check('解析「搜到90%的题自动提交」', quiz_ai._parse_finish_ratio('搜到90%的题自动提交') == 0.9,
          quiz_ai._parse_finish_ratio('搜到90%的题自动提交'))
    check('已经是 float 时原样使用', quiz_ai._parse_finish_ratio(0.9) == 0.9)
    check('已经是 int 时转成 float', quiz_ai._parse_finish_ratio(1) == 1.0)
    check('非百分比文字原样返回', quiz_ai._parse_finish_ratio('仅自动保存') == '仅自动保存')

    try:
        quiz_ai.Answer(None, None, '测试课', '', None, 0.9)
        crashed = ''
    except Exception as e:      # noqa: BLE001 - 旧实现这里必崩
        crashed = repr(e)
    check('重做时传 float 不再崩溃', crashed == '', crashed)

    # ---------- 2) 题干里的图片 ----------
    check('题干有 120×40 的公式图 -> 认为是图片题',
          quiz_ai.Answer._element_has_meaningful_image(El([(120, 40)])) is True)
    check('题干只有 16×16 小图标 -> 不算图片题',
          quiz_ai.Answer._element_has_meaningful_image(El([(16, 16)])) is False)
    check('题干没有图片 -> 不算',
          quiz_ai.Answer._element_has_meaningful_image(El()) is False)
    check('元素为空时不抛异常',
          quiz_ai.Answer._element_has_meaningful_image(None) is False)

    # ---------- 3) 整题元素里的「题干图片」（排除选项 li） ----------
    check('JS 判定题干有图 -> True',
          quiz_ai.Answer._question_has_stem_image(El(js_result=True)) is True)
    check('JS 判定题干无图 -> False',
          quiz_ai.Answer._question_has_stem_image(El(js_result=False)) is False)
    check('JS 出错时不抛异常',
          quiz_ai.Answer._question_has_stem_image(El(js_raises=True)) is False)

    print('---')
    if FAILS:
        print('FAILED: %d' % len(FAILS), FAILS)
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
