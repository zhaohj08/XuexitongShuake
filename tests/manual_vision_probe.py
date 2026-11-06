# -*- coding: utf-8 -*-
"""手工验证脚本：确认 deepseek-v4-flash 的图片输入链路可用（不属于自动测试）。

用法（需要真实 key）：
    C:/Python315/python.exe tests/manual_vision_probe.py

流程：用 PIL 现场画一道「1+1=? A.1 B.2 C.3 D.4」的题（不是用户的真题），
按工程里的多模态格式发一次请求，打印模型返回的原文。
key 从 %LOCALAPPDATA%\\XuexitongShuake\\tool\\accounts.json 的 global.API 读取，
也可用环境变量 XXT_API 覆盖；脚本**不打印 key 本身**。
"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from PIL import Image, ImageDraw, ImageFont

from task.tool.DeepSeekAsk import DeepSeekAskImage, MODEL
from task.quiz_ai import _IMAGE_QUESTION_PROMPT


def load_api_key():
    key = os.environ.get('XXT_API', '').strip()
    if key:
        return key
    path = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'XuexitongShuake', 'tool', 'accounts.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return (json.load(f).get('global', {}) or {}).get('API', '')
    except Exception:
        return ''


def make_question_image(directory, filename='probe_question.png', title='【单选题】1 + 1 = ?',
                        options=('A. 1', 'B. 2', 'C. 3', 'D. 4')):
    image = Image.new('RGB', (900, 420), 'white')
    draw = ImageDraw.Draw(image)
    font = None
    for name in ('msyh.ttc', 'simhei.ttf', 'simsun.ttc'):
        candidate = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', name)
        if os.path.isfile(candidate):
            font = ImageFont.truetype(candidate, 34)
            break
    if font is None:
        font = ImageFont.load_default()
    draw.text((40, 40), title, fill='black', font=font)
    for index, text in enumerate(options):
        draw.text((70, 130 + index * 60), text, fill='black', font=font)
    path = os.path.join(directory, filename)
    image.save(path)
    return path


def main():
    key = load_api_key()
    if not key or 'sk-' not in key:
        print('未找到可用的 API Key，跳过验证')
        return 2
    print('模型: %s' % MODEL)
    print('API Key: 已读取（不打印）')
    directory = tempfile.mkdtemp(prefix='xxt_vision_probe_')

    cases = [
        ('单选题', 'probe_single.png', '【单选题】1 + 1 = ?',
         ('A. 1', 'B. 2', 'C. 3', 'D. 4'), 'B 或 2'),
        ('多选题', 'probe_multi.png', '【多选题】下列哪些是偶数？',
         ('A. 1', 'B. 2', 'C. 3', 'D. 4'), 'BD 或 2,4'),
    ]
    ok = True
    for label, name, title, options, expect in cases:
        path = make_question_image(directory, name, title, options)
        answer = DeepSeekAskImage(key, _IMAGE_QUESTION_PROMPT, [path], timeout=90)
        print('%s：模型返回 %r（期望 %s）' % (label, answer, expect))
        if not answer:
            ok = False
    print('RESULT=%s' % ('PASS（图片输入可用）' if ok else 'FAIL（返回为空，图片输入不可用或请求被拒）'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
