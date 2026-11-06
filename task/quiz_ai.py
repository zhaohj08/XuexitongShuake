# AI生成
# Copyright (c) 2025 Mortal004
# All rights reserved.
# This software is provided for non-commercial use only.
# For more information, see the LICENSE file in the root directory of this project.
import random
import time
import re
import os
import ast
import asyncio
import traceback

from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By

from task.tool.common import turn_page, Common, save_diagnostic_screenshot
from task.tool.no_secret import DecodeSecret
from task.tool import color
import sys
import io
from task.tool.ai_wen_da import main
from task.tool.DeepSeekAsk import DeepSeekAsk, DeepSeekAskImage
from task.tool.send_wx import send_error
from task.tool import quota
from core import paths
from core import browser as browser_ext

# 设置默认编码为UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


IMAGE_SUFFIXES = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg')

# 图片题（题干/选项是图片）交给多模态模型时用的提示词。
# 用户要求：只返回字母；多选返回多个字母；选项多于 4 个就按字母顺序继续。
_IMAGE_QUESTION_PROMPT = (
    '下面是一道题目的截图，题干和选项都在图片里。\n'
    '请只返回正确选项的字母，不要解释、不要标点、不要引号、不要换行。\n'
    '- 单选题、判断题：只返回一个字母，例如 B\n'
    '- 多选题：返回多个字母，例如 ACD\n'
    '- 选项超过 4 个：按字母顺序继续使用 E、F、G…\n'
    '如果图片里完全看不到字母，就按选项从上到下的顺序返回序号，例如 2 或 1,3。'
)

# 图片题截图的最长边：太大会让请求体过大、耗时变长，1600px 足够看清题目和选项
_IMAGE_MAX_SIDE = 1600

# 学习平台题目图片点开后的「全屏看图」遮罩：
# 常见实现是 #outerdiv + #innerdiv，另有一些页面用 fixed 浮层铺满屏幕。
# 这层遮罩会把后续所有点击吃掉，看起来就是「图片全屏了，程序卡住不动」。
_VIEWER_SCAN_JS = r"""
return (function () {
  var hits = [];
  function visible(el) {
    try {
      var s = getComputedStyle(el);
      return s.display !== 'none' && s.visibility !== 'hidden' &&
             parseFloat(s.opacity || '1') > 0.2;
    } catch (e) { return false; }
  }
  function fullscreen(el) {
    try {
      if (getComputedStyle(el).position !== 'fixed') return false;
      var r = el.getBoundingClientRect();
      return r.width >= innerWidth * 0.6 && r.height >= innerHeight * 0.6;
    } catch (e) { return false; }
  }
  function mark(el) { return ((el.id || '') + ' ' + (el.className || '')).toLowerCase(); }
  function skip(el) { return /face|popdiv|popok|popcontent|popuplogin/.test(mark(el)); }
  function kill(el) {
    if (!el || !el.parentNode || skip(el)) return;
    el.parentNode.removeChild(el);
    hits.push(el.id || el.className || el.tagName);
  }
  var known = ['#outerdiv', '#imgShow', '.img-view', '.image-view',
               '.imgViewer', '.viewer-mask', '.big-img-box', '.imgBox'];
  for (var i = 0; i < known.length; i++) {
    var nodes = document.querySelectorAll(known[i]);
    for (var j = 0; j < nodes.length; j++) {
      var el = nodes[j];
      if (visible(el) && (el.id === 'outerdiv' || fullscreen(el))) kill(el);
    }
  }
  if (!document.body) return hits;
  var kids = Array.prototype.slice.call(document.body.children);
  for (var k = 0; k < kids.length; k++) {
    var c = kids[k];
    if (!c.tagName || /^(SCRIPT|STYLE|LINK|IFRAME|NOSCRIPT)$/.test(c.tagName)) continue;
    if (skip(c)) continue;
    if (visible(c) && fullscreen(c) && c.querySelector('img')) kill(c);
  }
  return hits;
})()
"""

_VIEWER_OPEN_JS = r"""
return (function () {
  var known = ['#outerdiv', '#imgShow', '.img-view', '.image-view',
               '.imgViewer', '.viewer-mask', '.big-img-box', '.imgBox'];
  function shown(el) {
    try {
      var s = getComputedStyle(el), r = el.getBoundingClientRect();
      return s.display !== 'none' && s.visibility !== 'hidden' &&
             r.width >= innerWidth * 0.6 && r.height >= innerHeight * 0.6;
    } catch (e) { return false; }
  }
  for (var i = 0; i < known.length; i++) {
    var nodes = document.querySelectorAll(known[i]);
    for (var j = 0; j < nodes.length; j++) { if (shown(nodes[j])) return true; }
  }
  if (!document.body) return false;
  var kids = Array.prototype.slice.call(document.body.children);
  for (var k = 0; k < kids.length; k++) {
    var c = kids[k];
    if (!c.tagName || /^(SCRIPT|STYLE|LINK|IFRAME|NOSCRIPT)$/.test(c.tagName)) continue;
    if (shown(c) && c.querySelector('img')) return true;
  }
  return false;
})()
"""


def image_viewer_is_open(driver) -> bool:
    """当前页面是不是盖着一层全屏看图遮罩（只检查，不修改页面）。"""
    try:
        return bool(driver.execute_script(_VIEWER_OPEN_JS))
    except Exception:
        return False


def close_image_viewer(driver, esc=True) -> int:
    """关掉题目图片的全屏预览层，返回清掉的层数。"""
    if esc:
        try:
            browser_ext.press_escape(driver)
        except Exception:
            pass
    try:
        removed = driver.execute_script(_VIEWER_SCAN_JS) or []
    except Exception:
        return 0
    if removed:
        print(color.yellow('已关闭图片全屏预览层: %s' % '、'.join(map(str, removed))), flush=True)
    return len(removed)


def _is_image_url(url: str) -> bool:
    """浏览器是不是被导航到了图片本身（点到 <a href="xxx.jpg"> 的典型症状）。"""
    path = (url or '').split('?')[0].split('#')[0].lower()
    return path.endswith(IMAGE_SUFFIXES)


def _as_answer_list(raw):
    """把题库 / AI 返回的答案解析成纯文本列表。

    题库是第三方 HTTP 接口，返回内容不可信：这里只接收字面量（ast.literal_eval），
    绝不能用 eval —— 畸形返回会抛异常打断整场测验，恶意返回会在本机执行任意代码。
    不是合法字面量时只按分隔符做纯文本切分（切分不会执行任何东西），仍为空就当「无答案」，
    交给下一级兜底。
    """
    if isinstance(raw, (list, tuple)):
        return [str(item).strip() for item in raw if str(item).strip()]
    if not isinstance(raw, str):
        return []
    text = raw.strip()
    if not text:
        return []
    try:
        value = ast.literal_eval(text)
    except (ValueError, SyntaxError, TypeError):
        value = None
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    text = text.strip('[]').strip()
    cleaned = [part.strip().strip('\'"').strip() for part in re.split(r'[,，]', text)]
    return [part for part in cleaned if part]


def _shrink_image(src, dst, max_side=_IMAGE_MAX_SIDE):
    """把截图等比缩到最长边 max_side 以内，返回最终文件路径。

    题目截图动辄 800x4000，base64 后请求体会非常大、容易超时；
    压缩到 1600px 仍然能看清题干和 ABCD，代价也小。
    """
    try:
        from PIL import Image
        with Image.open(src) as image:
            image = image.convert('RGB')
            width, height = image.size
            scale = max_side / float(max(width, height))
            if scale >= 1:
                return src
            image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))),
                                 Image.LANCZOS)
            jpg = os.path.splitext(dst)[0] + '.jpg'
            image.save(jpg, 'JPEG', quality=88)
        try:
            os.remove(src)
        except OSError:
            pass
        return jpg
    except Exception:
        return src


def _parse_finish_ratio(value):
    """把设置项「搜到90%的题自动提交」解析成 0.9；已经是数字就直接用。

    重做一场测验时会把上一次解析出的 float 再传进来（Answer 递归调用自己），
    旧代码对它再跑一次 `re.search`，于是抛
    `TypeError: expected string or bytes-like object, got 'float'`，整场测验直接放弃。
    """
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r'(\d+)%', str(value or ''))
    if match:
        return int(match.group(1)) / 100
    return value


class Answer:
    def __init__(self, driver, test_frame, course_name, api,work_choice,after_finish_question,times=0,
                 frame_selector=None):
        self.driver=driver
        self.frame = test_frame
        self._frame_selector = frame_selector
        self.decodeSecret = None
        self.questionList0 = []
        self.no_answer_dit = {}# 存储无答案的题目
        self.answer_list = []
        self.course_name = course_name
        self.driver=driver
        self.API_KEY=api
        self.work_choice=work_choice
        self.turn_page=turn_page
        self.after_finish_question = _parse_finish_ratio(after_finish_question)

        self.ans_rate =None
        self.all_title_dit={}
        self.num_option_dit = {}
        self.questionType_list = []
        self.all_title = ''
        self.num_answer_dit = {}
        self.only_title_text = []
        self.reword_time = 0
        self.all_optionWebElementList = []
        self.image_questions = set()   # 题干或选项是图片的题号，改用多模态识别
        self.image_unanswered = set()  # 多模态也没答出来的图片题，最后统一提示
        self.skipped_questions = set() # 程序答不了的题型（计算/简答/填空…）：不联网、不点选项
        self.times = times
        if self.work_choice is not None:
            self.main()

    # 这些题型程序既点不了选项、也填不了空：联网搜也是白花额度，直接跳过（用户明确要求）
    UNANSWERABLE_TYPES = ('简答题', '论述题', '填空题', '名词解释',
                          '计算题', '连线题', '其他', '未知')

    # 可点选项的题型 / 主观题型
    CHOICE_TYPES = ('单选题', '多选题', '判断题')
    ESSAY_TYPES = ('简答题', '论述题', '填空题', '名词解释')

    @classmethod
    def question_kind(cls, question_type):
        """把题型分三类：choice=能点选项、essay=主观题、unknown=程序不认识（如计算题）。"""
        if question_type in cls.CHOICE_TYPES:
            return 'choice'
        if question_type in cls.ESSAY_TYPES:
            return 'essay'
        return 'unknown'

    # 一次最多批量问 AI 这么多道题（避免一场大测验把额度刷爆）
    MAX_AI_BATCH = 15

    # 这些状态词出现即认为这场测验已经做完/提交，不要重复submit
    _FINISHED_STATUS_WORDS = ('已完成', '已提交', '已交', '批阅')

    def _quiz_finished_by_status(self):
        """判断这场测验是否已经完成/提交，返回 (是否完成, 依据描述)。

        旧实现读 iframe 前一个兄弟 div 的 aria-label，只要含「已完成」就整场跳过。
        可那个 div 常常是同一章节里**别的任务点**（比如已看完的视频），
        于是没做过的测验也被当成「已完成」——用户看到的就是「遇见章节测验直接跳过」。
        现在只看测验自己的状态元素 `testTit_status`，取不到再退到「本 iframe 的父容器」标记。
        """
        try:
            self._enter_context()
            element = self.driver.find_element(By.CLASS_NAME, 'testTit_status')
            text = (element.text or '').strip()
            if text:
                for word in self._FINISHED_STATUS_WORDS:
                    if word in text:
                        return True, f'测验状态={text}'
                return False, f'测验状态={text}'
        except Exception:
            pass
        if self.frame is not None:
            try:
                parent_class = self.frame.find_element(By.XPATH, '..').get_attribute('class') or ''
                if 'ans-job-finished' in parent_class:
                    return True, '父容器 ans-job-finished'
            except Exception:
                pass
        return False, ''

    def main(self):
        # 滚动到测试
        try:
            self.driver.execute_script("arguments[0].scrollIntoView();", self.frame)
        except Exception:
            pass
        # 只按「测验自己」的状态判断是否已完成（见 _quiz_finished_by_status）
        finished, reason = self._quiz_finished_by_status()
        if image_viewer_is_open(self.driver):
            close_image_viewer(self.driver)
        if finished:
            print(color.green(f'测试已完成（{reason}），跳过'), flush=True)
            return
        else:
            print(color.yellow(f'测验未标记完成（{reason or "没有找到状态标记"}），开始作答'), flush=True)
            self.get_title_option()
            print(color.red('正在搜索中，请耐心等待...'))
            if self.API_KEY=='sk-open_deepseek':
                self.no_answer_dit = {k: v for k, v in self.all_title_dit.items()
                                      if k not in self.image_questions
                                      and k not in self.skipped_questions
                                      and self.questionType_list[k] not in self.UNANSWERABLE_TYPES}
            else:
                self.use_ai_wen_da()
                for i, answer in self.num_answer_dit.items():
                    if (not answer and i not in self.image_questions
                            and i not in self.skipped_questions
                            and self.questionType_list[i] not in self.UNANSWERABLE_TYPES):
                        self.no_answer_dit[i] = self.all_title_dit[i]
            self.use_deepseek()
            # 查答案期间页面可能重渲染/跳转，答题前统一把上下文切回来
            turn_page(self.driver, '学生学习页面')
            if not self._enter_context():
                print(color.red('答题页已不可用，跳过本次测验'), flush=True)
                return
            if len(self.skipped_questions) >= len(self.questionList0) and not self.image_questions:
                # 整场都是计算/简答这类程序答不了的题：不搜题、不点、不提交，避免空转
                print(color.yellow(f'本场 {len(self.skipped_questions)} 道题都无法自动作答，'
                                   f'整场跳过（未消耗 AI 额度）'), flush=True)
                return
            print(color.green('开始答题'), flush=True)
            for title_num in self.num_answer_dit.keys():
                if self.finish_title(title_num):
                    self.reword_time += 1
                time.sleep(1)
            if self.skipped_questions:
                nums = '、'.join(str(i + 1) for i in sorted(self.skipped_questions))
                print(color.yellow(f'跳过 {len(self.skipped_questions)} 道无法自动作答的题'
                                   f'（第 {nums} 题），未消耗 AI 额度'), flush=True)
            if self.image_questions:
                answered = sorted(self.image_questions - self.image_unanswered)
                failed = sorted(self.image_unanswered)
                if answered:
                    nums = '、'.join(str(i + 1) for i in answered)
                    print(color.green(f'图片题：{len(answered)} 道已由多模态模型作答（第 {nums} 题）'),
                          flush=True)
                if failed:
                    nums = '、'.join(str(i + 1) for i in failed)
                    print(color.yellow(f'图片题：{len(failed)} 道未能作答（第 {nums} 题），'
                                       f'截图在 record/图片题/，请自行检查'), flush=True)
            total = len(self.questionList0)
            self.ans_rate = self.reword_time / total if total else 0
            print(self.reword_time, '/', total)
            try:
                info = quota.stats()
                print(color.yellow(
                    f'本轮累计联网 {info["total"]} 次（最近一分钟 {info["per_minute"]}/'
                    f'{info["max_per_minute"]} 次，按频率限流，不设总量上限）'), flush=True)
            except Exception:
                pass
            message = self.submit()
            if not message and self.times<3:
                print(color.green('开始第{}次重新做题'.format(self.times+1)))
                self.driver.switch_to.default_content()
                print(color.green('重新做题'), flush=True)
                Answer(self.driver, self.frame, self.course_name, self.API_KEY, self.work_choice,
                       self.after_finish_question, self.times + 1,
                       frame_selector=self._frame_selector)
            elif self.times>=3:
                print(color.red('测试答题失败，已重试3次'), flush=True)
    def get_title_option(self):
        if not self._enter_context():
            raise RuntimeError('无法进入答题页面（题目列表为空）')
        # 实例化 DecodeSecret 类
        self.decodeSecret = DecodeSecret(1)
        print(color.yellow("启用字体解密"), flush=True)
        self.decodeSecret.getFontFace(self.driver)
        # 获取页面中的所有题目
        self.questionList0 = self.driver.find_elements(By.CSS_SELECTOR, '[class="singleQuesId"]')
        print(color.yellow("当前测试共有{}题".format(len(self.questionList0))), flush=True)

        for i in range(len(self.questionList0)):
            self.title_num = i + 1
            self.option_text_list = []
            self.title_and_option_element = self.questionList0[i]
            self.title_and_option_text = re.sub(r'\s+', '',
                                               self.decodeSecret.decode(self.title_and_option_element.text).strip())
            # 整题是图片时拿不到标题元素，不能让一道题把整场测验打断
            self.title_element = None
            try:
                self.title_element = self.title_and_option_element.find_element(
                    By.CSS_SELECTOR, '[class="clearfix font-cxsecret fontLabel"]')
                self.title = re.sub(r'\s+', '', self.decodeSecret.decode(self.title_element.text).strip())
            except NoSuchElementException:
                self.title = ''
            # 题目类型 / 题目文本（没有【】前缀时整体当作题干）
            if '【' in self.title and '】' in self.title:
                self.questionType = self.title[self.title.find("【") + 1: self.title.find("】")]
                self.title_text = self.title[self.title.find("】") + 1:]
            else:
                self.questionType = ''
                self.title_text = self.title
                # 题干元素里没有【xx题】时，再从整题文本里捞一次（计算题常见）
                leftover = re.search(r'【([^】]{1,8})】', self.title_and_option_text or '')
                if leftover:
                    self.questionType = leftover.group(1)
                    self.title_text = (self.title_text or '').replace(
                        leftover.group(0), '').strip()
                    print(color.yellow(f'第{i+1}题从题目文本补出题型：{self.questionType}'),
                          flush=True)
            self.only_title_text.append(self.title_text)
            self.questionType_list.append(self.questionType or '未知')

            if self.question_kind(self.questionType) == 'choice':
                options = self.title_and_option_element.find_elements(By.TAG_NAME, 'li')
                self.all_optionWebElementList.append(options)
                for option in options:
                    self.option_text_list.append(
                        re.sub(r'\s+', '', self.decodeSecret.decode(option.text).strip()))
                # 图片选项的 .text 可能是空串（也可能只剩 alt/文件名），
                # 只要有一个选项是「图片 + 无文字」，AI 就只能瞎猜，直接跳过。
                image_option = any(
                    not text.strip() and self._element_has_image(option)
                    for option, text in zip(options, self.option_text_list))
                # 题干里有插图/公式图片：文字可能取到一部分（如「函数的间断点为()」），
                # 但关键信息在图片里，纯文字搜题必错，必须走多模态。
                stem_image = self._question_has_stem_image(self.title_and_option_element)
                if len(self.option_text_list) >= 2 and not any(t.strip() for t in self.option_text_list):
                    self._mark_image_question(i, self.title_and_option_element)
                    print(color.yellow(f'第{i+1}题：选项为图片，改由多模态作答'), flush=True)
                elif not self.title_text.strip():
                    self._mark_image_question(i, self.title_and_option_element)
                    print(color.yellow(f'第{i+1}题：题干为图片，改由多模态作答'), flush=True)
                elif stem_image:
                    self._mark_image_question(i, self.title_and_option_element)
                    print(color.yellow(f'第{i+1}题：题干含图片/公式，改由多模态作答'), flush=True)
                elif image_option:
                    self._mark_image_question(i, self.title_and_option_element)
                    print(color.yellow(f'第{i+1}题：选项含无文字图片，改由多模态作答'), flush=True)
            elif self.question_kind(self.questionType) == 'essay':
                # 主观题：程序写不了字，直接跳过，不查题库也不问 AI（省额度）
                self.all_optionWebElementList.append(None)
                self.option_text_list = ['']
                self.skipped_questions.add(i)
                print(color.yellow(f'第{i+1}题：{self.questionType}无法自动作答，跳过（不联网）'),
                      flush=True)
            else:
                # 题型没解析出来（题干/整题是图片，或计算题这类非常规题）：
                # 用「真实的选项数量」+「有没有作答编辑器」来判断——
                #   有作答编辑器 / 真实选项不足 2 个：计算/填空/简答，只截图、绝不调 AI；
                #   有 ≥2 个真实选项：多半是整题图片的选择题，交给多模态。
                if not self._can_answer_by_options(self.title_and_option_element):
                    self.all_optionWebElementList.append(None)
                    self.option_text_list = ['']
                    self.skipped_questions.add(i)
                    self._save_image_question(i, self.title_and_option_element)
                    print(color.yellow(f'第{i+1}题无作答选项（{self.questionType or "题型未知"}），'
                                       f'已跳过（只截图，不调 AI）'), flush=True)
                else:
                    options = self.title_and_option_element.find_elements(By.TAG_NAME, 'li')
                    self.all_optionWebElementList.append(options)
                    for option in options:
                        self.option_text_list.append(
                            re.sub(r'\s+', '', self.decodeSecret.decode(option.text).strip()))
                    self._mark_image_question(i, self.title_and_option_element)
                    print(color.yellow(f'第{i+1}题题型未解析但有选项，按图片题交给多模态'),
                          flush=True)

            # 无论是否可作答都要登记，否则 only_title_text/questionType_list 与题号错位
            self.all_title_dit[i] = self.title_and_option_text
            self.num_option_dit[i] = self.option_text_list

    @staticmethod
    def _has_rich_editor(question_element):
        """题目里有没有"填写答案"的富文本/文本框（填空、计算、简答都有）。

        这是最硬的判据：只要出现作答编辑器，就说明这题是主观题，程序点不了选项。
        """
        if question_element is None:
            return False
        try:
            driver = getattr(question_element, 'parent', None)
            if driver is None:
                return False
            return bool(driver.execute_script(
                "const r = arguments[0];"
                "return !!(r.querySelector('[contenteditable=\"true\"], .w-e-text-container,"
                " textarea, .edui-body-container, iframe.w-e-iframe]'));",
                question_element))
        except Exception:
            return False

    @staticmethod
    def _count_real_options(question_element):
        """数这道题有几个**真正的选项**。

        计算题/填空题的题目块里同样会出现 `<li>`（富文本编辑器的工具栏就是 li 组成的），
        所以不能只看"有没有 li"。真正的选项满足其一：
        - 带 radio/checkbox 或 `num_option` 标号；
        - 文本以 A./B./C. 这类标号开头；
        - 里面是图片（图片选项）。
        编辑器区域里的 li 一律不算。
        """
        if question_element is None:
            return 0
        try:
            driver = getattr(question_element, 'parent', None)
            if driver is None:
                return 0
            count = driver.execute_script("""
                const root = arguments[0];
                const editor = '.w-e-toolbar, .w-e-text-container, [class*="toolbar"],'
                             + ' [class*="editor"], .edui-toolbar, .edui-body-container';
                let count = 0;
                for (const li of root.querySelectorAll('li')) {
                  if (li.closest(editor)) { continue; }
                  if (li.querySelector('input[type=radio], input[type=checkbox],'
                        + ' [class*="num_option"], [class*="option"]')) { count++; continue; }
                  const text = (li.innerText || '').replace(/\\s+/g, '');
                  if (/^[A-Ha-h][.、．)）]/.test(text)) { count++; continue; }
                  if (li.querySelector('img')) { count++; continue; }
                }
                return count;
            """, question_element)
            return int(count or 0)
        except Exception:
            return 0

    def _can_answer_by_options(self, question_element):
        """这道题能不能靠点选项作答。"""
        if self._has_rich_editor(question_element):
            return False
        return self._count_real_options(question_element) >= 2

    def _mark_image_question(self, index, element):
        """登记一道图片题：先记为「未作答」，答出来以后再从 image_unanswered 里移除。"""
        self.image_questions.add(index)
        self.image_unanswered.add(index)
        self._save_image_question(index, element)

    def _save_image_question(self, title_num, element):
        """整题（题干+选项）截图，返回文件路径；失败返回空串。

        截图有两个用途：① 交给多模态模型作答；② 万一答不出来，留档给用户手动补。
        """
        try:
            folder = paths.record('图片题')
            os.makedirs(folder, exist_ok=True)
            name = f'第{title_num + 1}题_{time.strftime("%H%M%S")}.png'
            raw_path = os.path.join(folder, name)
            element.screenshot(raw_path)
            path = _shrink_image(raw_path, raw_path)
            print(color.yellow(f'  图片题截图已保存: record/图片题/{os.path.basename(path)}'), flush=True)
            return path
        except Exception as e:
            print(color.red(f'  图片题截图保存失败: {e}'), flush=True)
            return ''

    @staticmethod
    def _parse_choice_letters(text, option_count):
        """把模型回答解析成选项下标列表（从 0 开始）。

        约定回答只有字母（多选返回多个字母）。兼容 "B."、"ACD"、"A,C"、"答案：B" 这类写法，
        也兼容模型按序号回答（1/2/3…）；越界和重复一律丢弃。
        """
        if not isinstance(text, str) or not text.strip() or option_count <= 0:
            return []
        cleaned = re.sub(r'[\s，,、。．.：:；;、"\'“”()（）]', '', text)
        if re.fullmatch(r'[A-Za-z]{1,8}', cleaned):
            letters = list(cleaned)
        else:
            # 只认大写字母，避免把 "answer" 里的 e 误当成选项 E
            letters = re.findall(r'[A-Z]', text)
        indices = []
        for letter in letters:
            index = ord(letter.upper()) - ord('A')
            if 0 <= index < option_count and index not in indices:
                indices.append(index)
        if indices:
            return indices
        for number in re.findall(r'\d+', text):
            index = int(number) - 1
            if 0 <= index < option_count and index not in indices:
                indices.append(index)
        return indices

    def _ask_image_question(self, title_num, question):
        """把整题截图交给多模态模型，返回选项下标列表；失败返回 []。"""
        if not self.API_KEY or self.API_KEY == 'sk-open_deepseek' or 'sk-' not in self.API_KEY:
            print(color.yellow(f'第{title_num + 1}题为图片题，未配置 API Key，无法识图'), flush=True)
            return []
        path = self._save_image_question(title_num, question)
        if not path:
            return []
        # 选项数量以页面上的 <li> 为准：整题是图片时 num_option_dit 里只有 [''] 占位，
        # 用它算数量会把 B/C/D 全判成越界，等于白问。
        option_count = len(self.all_optionWebElementList[title_num] or [])
        if option_count <= 0:
            option_count = len(self.num_option_dit.get(title_num) or [])
        text = DeepSeekAskImage(self.API_KEY, _IMAGE_QUESTION_PROMPT, [path])
        indices = self._parse_choice_letters(text, option_count)
        if indices:
            picked = ''.join(chr(ord('A') + index) for index in indices)
            print(color.green(f'第{title_num + 1}题（图片题）AI 答案: {picked}'), flush=True)
        else:
            print(color.red(f'第{title_num + 1}题（图片题）AI 未返回可用答案'), flush=True)
        return indices

    def _finish_image_title(self, title_num):
        """图片题：截图问多模态 → 按返回的字母点击选项。

        答不出来时：随机答题模式下随机点一个，其余情况跳过并记录，最后统一提示。
        """
        question = self._relocate(title_num)
        if question is None:
            print(color.red(f'第{title_num + 1}题（图片题）定位失败，跳过'), flush=True)
            self.image_unanswered.add(title_num)
            return False
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", question)
        except Exception:
            pass
        indices = self._ask_image_question(title_num, question)
        if not indices:
            options = self.all_optionWebElementList[title_num] or []
            if self.work_choice == '随机答题' and options:
                index = random.randrange(len(options))
                print(color.red(f'第{title_num + 1}题改用随机作答: {chr(ord("A") + index)}'), flush=True)
                indices = [index]
            else:
                self.image_unanswered.add(title_num)
                return False
        clicked = False
        for index in indices:
            if self._click_option(title_num, index):
                clicked = True
            time.sleep(0.5)
        if clicked:
            self.image_unanswered.discard(title_num)
        else:
            self.image_unanswered.add(title_num)
        return clicked

    def _search_bank(self, index):
        """查题库（多源并发），返回纯文本答案列表；失败返回 []。"""
        try:
            raw = asyncio.run(main(self.questionType_list[index],
                                   self.only_title_text[index],
                                   self.num_option_dit[index], self.API_KEY))
        except Exception as e:
            print(color.red(f'第{index + 1}题搜索失败：{e}'), flush=True)
            return []
        return _as_answer_list(raw)

    def use_ai_wen_da(self):
        for i in self.all_title_dit.keys():
            if i in self.image_questions:
                # 图片题没有可检索的文本，查题库纯属浪费请求
                self.num_answer_dit[i] = []
                continue
            if i in self.skipped_questions or self.questionType_list[i] in self.UNANSWERABLE_TYPES:
                # 简答/论述/填空/名词解释/计算等程序答不了的题：直接跳过，不去联网（省额度）
                self.num_answer_dit[i] = []
                print(color.yellow(f'第{i+1}题：{self.questionType_list[i]}无法自动作答，跳过'),
                      flush=True)
                continue
            if self.times==0 and self.work_choice!='随机答题':
                print(color.green('\n<===================  分隔线  ===================>\n'), flush=True)
                self.answer_list = self._search_bank(i)
            elif self.work_choice!='随机答题':
                self.answer_list=[]
            elif self.work_choice=='随机答题':
                self.answer_list=[random.choice(self.num_option_dit[i])]
                print(color.red(f'本次采用随机答题,随机答案为：{self.answer_list}'),flush=True)
            if not self.answer_list:
                self.num_answer_dit[i] = []
                # print(color.red('无答案，跳过'), flush=True)
                continue
            else:
                self.num_answer_dit[i] = self.answer_list

    def use_deepseek(self):
        """批量问一次 AI；答案段数与题目数对不上时，退化为逐题提问。

        旧实现按 '/' 的位置把答案回填到题目：少一段就 parts[num] 越界（后面的题全不答），
        多一段就静默错位（第 N 题的答案填给第 N+1 题，日志却完全正常）。
        现在先校验段数，对不上就不猜位置，改成逐题重新问。
        （AI 答案不再写缓存：写错一次会被永久固化，见 ai_wen_da 的 cacheable 标记。）
        """
        if not self.no_answer_dit:
            return

        # 额度保护：一次最多批量问 15 道题；超出的先跳过，避免一场大测验把额度刷爆
        keys = list(self.no_answer_dit.keys())
        if len(keys) > self.MAX_AI_BATCH:
            print(color.yellow(f'待 AI 作答的题有 {len(keys)} 道，超过单次上限 '
                               f'{self.MAX_AI_BATCH} 道，其余先跳过'), flush=True)
            keys = keys[:self.MAX_AI_BATCH]

        print(color.red('正在使用deepseek搜题，请耐心等待...'), flush=True)
        title = ''.join(self.no_answer_dit[key] for key in keys)
        answers = DeepSeekAsk(self.API_KEY, title, 'all')
        parts = self._split_batch_answer(answers, len(keys))
        if parts is None:
            print(color.yellow(f'AI 返回的答案段数与待答题数({len(keys)})对不上，'
                               f'改为逐题提问，避免答案错位'), flush=True)
            for key in keys:
                self.num_answer_dit[key] = self._ask_one(key)
            return
        for key, part in zip(keys, parts):
            self.num_answer_dit[key] = [p.strip() for p in re.split(r'[,，]', part) if p.strip()]

    @staticmethod
    def _split_batch_answer(raw, expected):
        """把 'C/B,ABCD' 拆成 expected 段；数量不符返回 None（绝不按位置硬回填）。"""
        text = raw.strip() if isinstance(raw, str) else ''
        if not text:
            return None
        if text.startswith('[') and text.endswith(']'):
            text = text[1:-1].strip()
        if not text:
            return None
        if expected == 1:
            # 只有一道题时不存在错位风险，整段就是答案（省掉一次逐题提问）
            return [text]
        if '/' not in text:
            return None
        parts = re.split(r'/', text)
        # 模型常多给一个结尾 '/', 只容忍这一种「末尾空段」，其余数量不符一律降级
        while len(parts) > expected and not parts[-1].strip():
            parts.pop()
        if len(parts) != expected:
            return None
        return parts

    def _ask_one(self, key):
        """逐题问 AI，返回答案列表；失败返回 []。"""
        typ = self.questionType_list[key]
        options = self.num_option_dit[key] or []
        prompt = f'【{typ}】{self.only_title_text[key]}{options}'
        try:
            raw = DeepSeekAsk(self.API_KEY, prompt, typ)
        except Exception as e:
            print(color.red(f'第{key + 1}题 AI 兜底失败：{e}'), flush=True)
            return []
        return _as_answer_list(raw)


    # 题目/选项定位器：作业页与测验页不同，收集时记录，重定位时复用
    _q_selector = '[class="singleQuesId"]'
    _opt_by = By.TAG_NAME
    _opt_value = 'li'
    _context_mode = 'quiz'      # quiz: 需要走 iframe 链；window: 作业页在自己的窗口里
    _frame_selector = None      # 测验模块 iframe 的选择器，由 Quiz 注入

    # ---------------- 文档上下文 ----------------
    def _has_questions(self):
        try:
            return bool(self.driver.find_elements(By.CSS_SELECTOR, self._q_selector))
        except Exception:
            return False

    def _switch_work_frame(self):
        """切进「作业/测验模块」那个 iframe；元素失效时按选择器重找。"""
        # 注意：Selenium 里 switch_to.frame(None) 不会报错，而是原地不动，
        # 所以要显式跳过 None，否则会误判成「已经切进去了」。
        if self.frame is not None:
            try:
                self.driver.switch_to.frame(self.frame)
                return True
            except Exception:
                pass
        if not self._frame_selector:
            return False
        try:
            frames = self.driver.find_elements(By.CSS_SELECTOR, self._frame_selector)
        except Exception:
            return False
        for frame in frames:
            try:
                self.driver.switch_to.frame(frame)
                self.frame = frame
                return True
            except Exception:
                continue
        return False

    def _enter_context(self):
        """把浏览器切回「题面所在的文档」，并确认能读到题目。

        以前是在 main() 里写死 switch_to.frame(self.frame) + frame_content：
        页面一旦重渲染，self.frame 就是失效元素，switch 直接抛异常，整场测验被跳过。
        这里每次都从 default_content 重新走一遍，并按 id/选择器兜底。
        """
        if self._context_mode != 'quiz':
            return self._has_questions()
        driver = self.driver
        for outer in ('iframe', None):
            try:
                driver.switch_to.default_content()
            except Exception:
                return False
            if outer:
                try:
                    driver.switch_to.frame(outer)
                except Exception:
                    continue
            if not self._switch_work_frame():
                # 有的页面题目直接铺在模块页上，没有单独的模块 iframe
                if self._has_questions():
                    return True
                continue
            # 模块内部的 frame_content（部分页面没有这一层）
            entered_inner = False
            try:
                driver.switch_to.frame('frame_content')
                entered_inner = True
            except Exception:
                pass
            if self._has_questions():
                return True
            if not entered_inner:
                try:
                    frames = driver.find_elements(By.TAG_NAME, 'iframe')
                except Exception:
                    frames = []
                for frame in frames:
                    try:
                        driver.switch_to.frame(frame)
                        if self._has_questions():
                            return True
                    except Exception:
                        pass
                    try:
                        driver.switch_to.parent_frame()
                    except Exception:
                        break
        return False

    def _recover_image_navigation(self):
        """误点到图片链接时浏览器会停在图片本身，退回去继续答题。

        既可能是顶层窗口跳到图片（新标签/整页），也可能只是题目所在的 iframe
        被导航成图片，所以两种 URL 都要看。
        """
        urls = []
        try:
            urls.append(self.driver.current_url or '')
        except Exception:
            pass
        try:
            urls.append(self.driver.execute_script('return location.href') or '')
        except Exception:
            pass
        if not any(_is_image_url(u) for u in urls):
            return
        print(color.yellow('页面被导航到了图片地址，正在返回上一页'), flush=True)
        try:
            self.driver.execute_script('history.back();')
        except Exception:
            pass
        time.sleep(2)
        try:
            if _is_image_url(self.driver.current_url or ''):
                self.driver.back()
                time.sleep(2)
        except Exception as e:
            print(color.red(f'返回失败: {e}'), flush=True)

    @staticmethod
    def _element_has_image(element):
        try:
            return bool(element.find_elements(By.TAG_NAME, 'img'))
        except Exception:
            return False

    @staticmethod
    def _element_has_meaningful_image(element, min_width=40, min_height=16):
        """元素里是否有「像题干插图/公式」的图片（过滤掉 16×16 的小图标）。

        题干常常是「文字 + 公式图片」：文字能取到（例如「函数的间断点为()」），
        但关键的公式在 <img> 里，纯文字搜题只会答错。所以只要题干里有像样的图片，
        就当成图片题交给多模态。
        """
        if element is None:
            return False
        try:
            for image in element.find_elements(By.TAG_NAME, 'img'):
                try:
                    size = image.size or {}
                    if (size.get('width', 0) >= min_width
                            and size.get('height', 0) >= min_height):
                        return True
                except Exception:
                    continue
        except Exception:
            return False
        return False

    @staticmethod
    def _question_has_stem_image(question_element, min_width=40, min_height=16):
        """题干区域是否有图片：排除选项 <li> 里的图，只算选项之外的部分。"""
        if question_element is None:
            return False
        try:
            driver = getattr(question_element, 'parent', None)
            if driver is None:
                return False
            return bool(driver.execute_script("""
                const root = arguments[0];
                const minW = arguments[1], minH = arguments[2];
                for (const img of root.querySelectorAll('img')) {
                  if (img.closest('li')) { continue; }      // 选项里的图不算题干
                  const w = img.naturalWidth || img.width || 0;
                  const h = img.naturalHeight || img.height || 0;
                  if (w >= minW && h >= minH) { return true; }
                }
                return false;
            """, question_element, min_width, min_height))
        except Exception:
            return False

    def _relocate(self, title_num):
        """重新定位题目与其选项元素。

        AI 查答案往往要几十秒，期间页面会重渲染，之前抓到的 WebElement 会失效
        （Edge 报 no such element: element not found），所以每次作答前重新抓一遍。
        """
        self._recover_image_navigation()
        if not self._enter_context():
            return None
        try:
            questions = self.driver.find_elements(By.CSS_SELECTOR, self._q_selector)
            if not questions or title_num >= len(questions):
                return None
            self.questionList0 = questions
            question = questions[title_num]
            options = question.find_elements(self._opt_by, self._opt_value)
            if options:
                while len(self.all_optionWebElementList) <= title_num:
                    self.all_optionWebElementList.append(None)
                self.all_optionWebElementList[title_num] = options
            return question
        except Exception:
            return None

    # 点击选项时优先命中的「字母/文字」节点（A/B/C/D 通常在这些节点里）
    _LABEL_JS = r"""
    return (function (li) {
      var sels = ['i', 'em', 'b', 'span', '.num_option', '.option-label', '.answer_p', 'p'];
      for (var i = 0; i < sels.length; i++) {
        var nodes = li.querySelectorAll(sels[i]);
        for (var j = 0; j < nodes.length; j++) {
          var node = nodes[j];
          if (node.querySelector && node.querySelector('img')) continue;
          var txt = (node.textContent || '').trim();
          if (!txt) continue;
          node.click();
          return node.tagName + ':' + txt.substring(0, 8);
        }
      }
      li.click();
      return 'LI';
    })(arguments[0])
    """

    def _js_click_option(self, option):
        """JS 点选项：优先点 A/B/C/D 所在的文字节点，退而点 <li> 本身。

        返回点中了什么（日志/测试用），失败返回空串。
        含图片的选项必须走这里：原生点击会落在 <img> 上并弹全屏遮罩。
        """
        try:
            return self.driver.execute_script(self._LABEL_JS, option) or ''
        except Exception:
            return ''

    @staticmethod
    def _option_selected(option):
        try:
            return option.get_attribute('aria-checked') == 'true'
        except Exception:
            return False

    def _click_option(self, title_num, idx):
        """点击某题第 idx 个选项；元素失效时重定位后重试一次。

        选项里带图片时不能原生点击：鼠标落在 <img> 上会触发学习平台的全屏看图，
        遮罩盖住整页后所有点击都点不动，看起来就是程序卡死。
        含图片的选项改走 JS：先点 A/B/C/D 所在的文字节点，没选中再点 <li> 本身。
        """
        for attempt in (0, 1):
            options = self.all_optionWebElementList[title_num] or []
            if idx is None or idx < 0 or idx >= len(options):
                return False
            option = options[idx]
            try:
                if option.get_attribute('aria-checked') == 'true':
                    print(color.red('已回答，无需重复回答'), flush=True)
                    return True
                has_image = self._element_has_image(option)
                if has_image:
                    clicked = self._js_click_option(option)
                    if clicked:
                        print(color.green(
                            f'  已点击选项 {chr(ord("A") + idx)} 的文字节点({clicked})'), flush=True)
                    if not self._option_selected(option):
                        # 文字节点没触发选中（事件可能绑在 li 上），再点一次容器
                        self.driver.execute_script("arguments[0].click();", option)
                        if not self._option_selected(option):
                            print(color.yellow(
                                f'  选项 {chr(ord("A") + idx)} 点击后未检测到选中状态'), flush=True)
                else:
                    option.click()
                # 万一页面还是弹出遮罩，立刻收掉，别让它把后面的题全挡住
                if has_image or image_viewer_is_open(self.driver):
                    close_image_viewer(self.driver)
                return True
            except Exception:
                if attempt == 0:
                    close_image_viewer(self.driver)
                    self._relocate(title_num)
                else:
                    return False
        return False

    def finish_title(self, title_num):
        if title_num in self.skipped_questions:
            # 特殊题型（计算/简答/填空/题型未知）：直接跳过，不搜题、不点选项、不调 AI
            print(color.yellow(f'第{title_num + 1}题已跳过（{self.questionType_list[title_num]}）'),
                  flush=True)
            return False
        if title_num in self.image_questions:
            # 图片题（题干/选项是图片）：截图交给多模态模型，按返回的字母点选项
            return self._finish_image_title(title_num)
        question = self._relocate(title_num)
        if question is None:
            print(color.red(f'第{title_num + 1}题定位失败，跳过'), flush=True)
            return False
        try:
            # 滚动到题目
            self.driver.execute_script("arguments[0].scrollIntoView();", question)
        except:
            pass
        print(color.green(f'正在回答第{title_num + 1}题...'), flush=True)
        answer=self.num_answer_dit[title_num]
        #去重
        print(color.green(f'该题为{self.questionType_list[title_num]}，答案：{answer}'), flush=True)
        option_num=0
        try:
            if self.questionType_list[title_num]=='单选题' or self.questionType_list[title_num]=='判断题':
                matched = None
                for idx, option_text in enumerate(self.num_option_dit[title_num]):
                    if answer and answer[0] and str(answer[0]) in option_text:
                        matched = idx
                        break
                if matched is None and answer:
                    # 答案只给了字母、选项文本又不含该字母时，按字母序号兜底
                    letter = str(answer[0]).strip()[:1].upper()
                    if letter in 'ABCDEFGH':
                        matched = ord(letter) - 65
                if matched is None:
                    print(color.red('未匹配到选项，跳过该题'), flush=True)
                    return False
                if not self._click_option(title_num, matched):
                    print(color.red('选项点击失败（元素可能已失效），跳过该题'), flush=True)
                    return False
                return True
            elif self.questionType_list[title_num] == '多选题':
                self.answer_num=[]
                if len(answer)==1:
                    lst = answer[0]
                else:
                    lst = answer
                for option in self.num_option_dit[title_num]:
                    for ans in lst:
                        if ans in option:
                           self.answer_num .append(option_num)
                    option_num+=1
                self.answer_num=list(set(self.answer_num))
                if not self.answer_num:
                    print(color.red('多选题未匹配到选项，跳过该题'), flush=True)
                    return False
                # 点击正确答案
                for ans in self.answer_num:
                    time.sleep(1)
                    self._click_option(title_num, ans)
                return True

            elif self.questionType_list[title_num]=='简答题' or self.questionType_list[title_num]=='论述题' or self.questionType_list[title_num]=='名词解释':
                text_frame=self.questionList0[title_num].find_element(By.TAG_NAME,'iframe')
                self.driver.switch_to.frame(text_frame)
                p_element=self.driver.find_element(By.TAG_NAME,'p')
                check_answer = p_element.text
                if check_answer != '':
                    print(color.red('已回答，无需重复回答'), flush=True)
                    self.driver.switch_to.parent_frame()
                    return True
                # self.driver.execute_script('arguments[0].innerText = arguments[1];', p_element, answer)
                p_element.click()
                p_element.send_keys(answer)
                self.driver.switch_to.parent_frame()
                return True
            elif self.questionType_list[title_num]=='填空题':
                if self.work_choice is not None:
                    elements = self.questionList0[title_num].find_elements(By.CLASS_NAME, 'InpDIV')
                else:
                    elements = self.questionList0[title_num].find_elements(By.CSS_SELECTOR,
                                                                           '[class="edui-editor-iframeholder edui-default"]')
                text_frames = self.questionList0[title_num].find_elements(By.TAG_NAME, 'iframe')
                if  len(answer)==1:
                    answer=re.split(r' ', answer[0])
                    print(color.red(f'修正答案：{answer}'), flush=True)
                if len(elements)>len(answer):
                    print(color.red('填空题答案数量少于题目数量'), flush=True)
                    return False
                for number in range(len(elements)):
                    self.driver.execute_script("arguments[0].click();", elements[number])
                    self.driver.switch_to.frame(text_frames[number])
                    p_element = self.driver.find_element(By.TAG_NAME, 'p')
                    check_answer = p_element.text
                    if check_answer != '':
                        print(color.red('已回答，无需重复回答'), flush=True)
                        self.driver.switch_to.parent_frame()
                        continue
                    try:
                        p_element.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", p_element)
                    try:
                        p_element.send_keys(answer[number])
                    except:
                        pass
                    self.driver.switch_to.parent_frame()
                    time.sleep(1)
                return True
            else:
                print(color.red(f'该题为{self.questionType}，暂时无法作答'), flush=True)
                return False
        except Exception as e:
            print(color.red(f'答题时出错了{e}'), flush=True)
            return False

    def _work_button(self, selector):
        """找保存/提交按钮并点掉。

        按钮在「模块页」而不是 frame_content 里，答题结束时 driver 往往还待在
        frame_content，直接 find_element 会报 no such element（以前就是这么崩的）。
        这里按 当前帧 → 父帧 → 更外层 逐级找，并且原生点击失败时退化成 JS 点击。
        """
        for _ in range(3):
            button = None
            try:
                button = self.driver.find_element(By.CSS_SELECTOR, selector)
            except NoSuchElementException:
                button = None
            except Exception:
                button = None
            if button is not None:
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", button)
                    time.sleep(0.3)
                except Exception:
                    pass
                try:
                    button.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", button)
                return True
            try:
                self.driver.switch_to.parent_frame()
            except Exception:
                break
        return False

    def submit(self):
        formatted_result = "{:.2%}".format(self.ans_rate)
        print(color.red(f'本次答题率为{formatted_result}'), flush=True)
        if image_viewer_is_open(self.driver):
            close_image_viewer(self.driver)
        if self.after_finish_question=='仅自动保存':
            print(color.yellow('3秒后保存'), flush=True)
            time.sleep(3)
            if not self._work_button('[class="btnSave workBtnIndex"]'):
                # 保存按钮找不到时不要把整场测验重来一遍（重答代价太大），提示手动保存即可
                print(color.red('未找到保存按钮，请手动保存'), flush=True)
                return True
        elif self.after_finish_question=='强制自动提交'  or self.work_choice =='随机答题' or self.ans_rate >= self.after_finish_question:
            # 点击提交
            print(color.yellow('3秒后提交'), flush=True)
            time.sleep(3)
            if not self._work_button('[class="btnSubmit workBtnIndex"]'):
                print(color.red('当前测验无法提交'), flush=True)
                return True
            time.sleep(1)
            # 点击确认（弹窗在顶层文档里）
            self.driver.switch_to.default_content()
            self._click_popup_ok()
            time.sleep(2)
            try:
                message = self.driver.find_element(By.ID, 'popcontent').text
            except Exception:
                message = ''
            if message:
                print(color.red(f'提交失败，原因：{message}'), flush=True)
                self._click_popup_ok()
                return False
            self.save_score()
        else:
            print(color.yellow(f'答题率未达到提交要求{self.after_finish_question}'), flush=True)
            print(color.yellow('3秒后保存'), flush=True)
            time.sleep(3)
            if not self._work_button('[class="btnSave workBtnIndex"]'):
                print(color.red('未找到保存按钮，请手动保存'), flush=True)
                return True

        return True

    def _click_popup_ok(self):
        try:
            self.driver.find_element(By.XPATH, '//*[@id="popok"]').click()
            return True
        except Exception:
            return False

    def save_score(self):
        # save_process(self.course_name)
        title = ''
        try:
            element = self.driver.find_element(By.CLASS_NAME, 'prev_title')
            title = element.get_attribute('title') or ''
        except Exception:
            pass
        if not title:
            try:
                self.driver.switch_to.default_content()
                self.driver.switch_to.frame('iframe')
                title = self.driver.find_element(By.CLASS_NAME, 'prev_title').get_attribute('title') or ''
            except Exception:
                pass
        score = '未查询到'
        try:
            self._enter_context()
            score = self.driver.find_element(By.CSS_SELECTOR, '.achievement i').text
        except Exception:
            print(color.yellow('未查询到本次测试成绩'), flush=True)
        try:
            with open(paths.record(f'《{self.course_name}》的成绩记录.txt'), 'a', encoding='utf-8') as f:
                f.write(
                    f'已完成:《{title}》章节中的测试题，完成时间：{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))}\n测试得分：{score}分(本次使用{self.work_choice})\n\n')
            print(color.green(f'已保存进度'), flush=True)
        except Exception:
            pass
class Quiz(Common):
    # 用「src 包含」匹配：平台前端发版会把 ?v=2025-1028-1629 换成新日期，
    # 有的部署还会把 src 写成绝对 URL（https://xxx/ananas/...），
    # 用 `^=` 只要前缀一变就认不出测验页、整章测验被静默跳过；`*=` 两者都能命中。
    IFRAME_SELECTOR = 'iframe[src*="/ananas/modules/work/index.html"]'

    def __init__(self, driver, course_name,API, choice,after_finish_question):
        super().__init__(
            driver,
            self.IFRAME_SELECTOR,
            "测验",
            course_name,
            # 考试/测验经常不算任务点：只要页面上有测验 iframe 就答，不再要求任务点图标
            require_mission=False
        )
        self.API = API
        self.choice = choice
        self.after_finish_question = after_finish_question
        self.driver = driver
        self.course_name = course_name
    def start(self):
        try:
            Answer(self.driver, self.iframe, self.course_name, self.API, self.choice,
                   self.after_finish_question, frame_selector=self.IFRAME_SELECTOR)
        except Exception as e:
            error_msg = traceback.format_exc()
            send_error(
                "\n作者只解决打赏用户提交的问题，请在赞助后将截图与报错信息一同发送至作者邮箱2022865286@qq.com,未赞助的用户请自行查看用户须知文件自行解决\n" + error_msg)
            save_diagnostic_screenshot(self.driver, '测验出错')
            print(color.red(f'测验处理出错，跳过本场：{e}'), flush=True)
            print(color.yellow('具体原因请前往错误日志查看，请自行保存或提交，15秒后继续'), flush=True)
            # 出错时页面可能还盖着图片遮罩，先收掉再回学习页，否则后面整页都点不动
            try:
                close_image_viewer(self.driver)
            except Exception:
                pass
            turn_page(self.driver,'学生学习页面')
            time.sleep(15)
def finish_quiz(driver, course_name, API, choice,after_finish_question):
    # driver.switch_to.default_content()
    # driver.switch_to.frame('iframe')
    # test_frames = driver.find_elements(By.XPATH,
    #                                    '//iframe[@src="/ananas/modules/work/index.html?v=2025-1028-1629&castscreen=0"]')
    # print(color.magenta(f'已检测到{len(test_frames)}个测试'), flush=True)
    # i=0
    # for test_frame in test_frames:
    #     if i!=0:
    #         driver.switch_to.default_content()
    #         driver.switch_to.frame('iframe')
    #     print(f'当前处理第{i+1}个测试', flush=True)
    #     i+=1
    #     try:
    #         Answer(driver, test_frame, course_name, API, choice,after_finish_question)
    #     except:
    #         error_msg = traceback.format_exc()
    #         send_error(
    #             "\n作者只解决打赏用户提交的问题，请在赞助后将截图与报错信息一同发送至作者邮箱2022865286@qq.com,未赞助的用户请自行查看用户须知文件自行解决\n" + error_msg)
    #         print(color.yellow('出错了，具体原因请前往错误日志查看，请自行保存或提交,15秒后继续'), flush=True)
    #         turn_page(driver,'学生学习页面')
    #         time.sleep(15)
    quiz=Quiz(driver, course_name, API, choice,after_finish_question)
    quiz.main()
