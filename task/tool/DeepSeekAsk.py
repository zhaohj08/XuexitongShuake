import base64
import os
import re

from task.tool import color
from task.tool import quota
from openai import OpenAI

# 固定使用的模型（不再随机选择）
MODEL = 'deepseek-v4-flash'


def _image_mime(path):
    return 'image/jpeg' if str(path).lower().endswith(('.jpg', '.jpeg')) else 'image/png'


def DeepSeekAskImage(API_KEY, prompt, image_paths, timeout=90):
    """多模态：把题目截图（题干+选项）交给 v4-flash，返回模型原文。

    图片以 base64 data URL 内联发送（OpenAI 兼容格式），不依赖公网可访问的图床。
    失败（无 key / 读文件失败 / 接口报错）时返回空串，由调用方决定跳过还是随机。
    """
    if 'sk-' not in (API_KEY or '') or API_KEY == 'sk-open_deepseek':
        return ''
    # 额度闸门：图片题每题只问 1~2 次，超了就跳过，避免同一道题反复消耗。
    # 指纹要带上图片路径，否则所有图片题共用同一个 prompt 会被当成"同一道题"。
    if not quota.acquire(quota.question_key(prompt + '|' + '|'.join(map(str, image_paths))),
                       'deepseek-image'):
        return ''

    content = [{"type": "text", "text": prompt}]
    for path in image_paths:
        try:
            with open(path, 'rb') as f:
                blob = f.read()
        except OSError as e:
            print(color.red(f'读取题目截图失败: {e}'), flush=True)
            continue
        encoded = base64.b64encode(blob).decode('ascii')
        content.append({
            "type": "image_url",
            "image_url": {"url": 'data:%s;base64,%s' % (_image_mime(path), encoded)},
        })
    if len(content) == 1:
        return ''

    try:
        client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": content}],
            temperature=0.2,
            timeout=timeout,
            stream=False,
        )
        answer = (response.choices[0].message.content or '').strip()
    except Exception as e:
        print(color.red(f'图片题识别请求失败: {e}'), flush=True)
        return ''
    print(color.yellow(f'图片题模型返回: {answer!r}'), flush=True)
    return answer


def DeepSeekAsk(API_KEY, title ,_type):

    if _type in ['单选题','判断题']:
        prompt=('不要其他话语，我仅需要这些题目的选择答案，返回的答案必须是列表格式，列表中的每个元素都是字符串,'
                '答案必须从给你的选项中选择，并且只能是其中一个答案，不能自己编造答案,'
                '最终你给出的答案格式应当类似于下面这样：["答案"]\n')
    elif _type=='多选题':
        prompt=('不要其他话语，我仅仅需要这些题目的选择答案哟，返回的答案必须是列表格式，列表中的每个元素都是字符串,'
                '答案必须从给你的选项中选择，可以选择多个答案，不能自己编造答案,'
                '最终你给出的答案格式应当类似于下面这样：["答案1","答案2",...]\n')
    elif _type in ['简答题','论述题']:
        prompt=('不要其他话语，我仅仅需要这些题目的选择答案哟，返回的答案必须是列表格式，列表中的每个元素都是字符串,'
                '只需给出文字答案即可,不要有多余的内容,答案要都在列表内，不要在列表后再加什么内容,'
                '最终你给出的答案格式应当类似于下面这样：["答案"]\n')
    elif _type=='填空题':
        prompt=('不要其他话语，我仅仅需要这些题目的选择答案哟，返回的答案必须是列表格式，列表中的每个元素都是字符串,'
                '只需给出文字答案即可,不要有多余的内容,答案要都在列表内，不要在列表后再加什么内容,有多少个空，列表中就要有多少个元素,'
                '最终你给出的答案格式应当类似于下面这样：["答案"]或["答案1","答案2",...]\n')
    else:
        prompt = '''请根据以下题目要求回答问题：
                                                  1.不要其他话语，我仅仅需要这些题目的选择答案哟

                            2.所有题目的答案必须从选项 A、B、C、D 中选择。多选题必须选多个答案，其答案紧挨着即可不用用'/'隔开

                            3.对于判断题，答案只能是 A 或 B，分别对应题目中的 A（对） 和 B（错）。

                            4.简答题只需给出文字答案即可,不要有多余的内容,论述题同样，论述题的答案字数在五十字左右,不要出现字母或题号数字

                            5.填空题的每个答案用“,”隔开

                            6.如果题目重复出现，只需回答一次，不要重复回答。

                            7.请严格按照题目编号顺序给出答案,1,2,3,4这样的题目序号顺序给出选择的答案。
                            每个题目的答案用“/”隔开,答案中不要题号，只需要答案，不用重复问题,不要给多了答案，有多少道题就给多少答案，
                            /的数量是能保持比题目数量少一个，不能多也不能少,不要有换行符

                            8.最终你给出的答案格式应当类似于下面这样：A/B,C,D/C/论述题答案/D/填空题答案1,填空题答案2,...

                            9.请你注意每道题目开头的【】里面内容判断这道题目是什么类型的题目
                                                    \n'''
    prompt += title

    if 'sk-' in API_KEY:
        # 额度闸门：超了直接返回空列表，由调用方按"没答案"处理
        if not quota.acquire(quota.question_key(title), 'deepseek'):
            return '[]'
        message = {"role": "user", "content": prompt}
        client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model=MODEL,
            messages=[message],
            temperature=1.3,
            stream=False
        )
        answer = response.choices[0].message.content
    else:
        print(color.red('请输入正确的deepseek API_KEY'), flush=True)
        return '[]'
    match = re.search(r'\[(.*?)\]', answer)
    if match:
        answer = match.group(0)
    print(answer, flush=True)
    return answer
