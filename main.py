# Copyright (c) 2025 Mortal004
# All rights reserved.
# This software is provided for non-commercial use only.
# For more information, see the LICENSE file in the root directory of this project.

#打包python -m PyInstaller --onefile --collect-all selenium main.py
import json
import re
import pickle
import time
import traceback
from selenium.common import NoSuchDriverException, NoSuchWindowException, WebDriverException, \
    ElementNotInteractableException, SessionNotCreatedException, NoSuchElementException, \
    ElementClickInterceptedException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium import webdriver

from core import paths
from core import browser as browser_ext
from core import driver as driver_ext
from task.tool.common import save_process, save_diagnostic_screenshot
from task.tool.face import get_cookie,auto_login_with_cookies,delete_face_popup
from task.finish_dicussion import finish_discussion
from task.play_audio import play_audio
from task.tool import color
from task.watch_live import watch_live
from task.watch_ppt import __ppt
from task.watch_vido import study_page
from task.quiz_ai import  finish_quiz
from task.quiz_ai import close_image_viewer, image_viewer_is_open
from task.tool.send_wx import send_error
from task.do_work import do_work
from task.reading import reading
from task.tool.page_compat import PageCompat
condition=True#用于判断是否调节倍数
error_num=0#错误次数
_CURRENT_DRIVER = None   # 当前浏览器实例，供顶层异常处理时截图用
def login_study(driver,phone_number,password):
    """
    使用指定的手机号和密码登录学习平台网站。

    参数:
    driver: WebDriver 对象，用于控制浏览器。
    phone_number: 字符串，登录使用的手机号码。
    password: 字符串，登录使用的密码。

    返回:
    无。
    """
    # 打开网页
    driver.get("https://i.chaoxing.com/")
    turn_page(driver,'用户登录')
    print(color.green('正在登录中...'), flush=True)
    # 自动登录
    element = driver.find_element(By.ID, 'phone')
    element1 = driver.find_element(By.ID, 'pwd')
    element.send_keys(phone_number)  # 替换成你的手机号码
    time.sleep(1)
    element1.send_keys(password)  # 替换成你的密码
    # 点击登录
    login_button = driver.find_element(By.ID, 'loginBtn')
    try:
        login_button.click()
    except:
        pass
    time.sleep(3)
    if not auto_login_with_cookies(driver):
        print(color.red('登陆失败，请打开手机端学习平台，扫码登录'), flush=True)
        while driver.title=='用户登录':
            time.sleep(1)
    if get_cookie(driver):
        print(color.green('登录成功'), flush=True)
    else:
        return
    # 转到页面内窗口


def save_course_lst(driver,class_name,course_elements,phone_number):
    try:
        have_task_course_element=driver.find_element(By.ID,'stuNormalCourseListDiv')
    except:
        have_task_course_element=driver
    try:
        new_course_elements=have_task_course_element.find_elements(By.CSS_SELECTOR, f'[class*="{class_name}"]')
        if len(new_course_elements)!=0:
            course_elements=new_course_elements
        course_list = [course_element.get_attribute('title') for course_element in course_elements if
                       course_element.get_attribute('title')!= '']
        if len(course_list)==0:
            course_list=[course_element.text for course_element in new_course_elements if
                       course_element.text!= '']
        if len(course_list) == 0:
            print(color.red(f'获取课程列表失败'), flush=True)
        else:
            try:
                with open(paths.data('tool', 'course_name.json'), 'r', encoding='utf-8') as f:
                    dit = json.load(f)
                with open(paths.data('tool', 'course_name.json'), 'w', encoding='utf-8') as f:
                    new_list = dit.get(phone_number,[]) + course_list
                    # 去重
                    new_list = list(set(new_list))
                    dit[phone_number]=new_list
                    json.dump(dit, f, ensure_ascii=False, indent=2)
                print(color.green(f'保存课程列表成功,共有{len(new_list)}个课程'), flush=True)
            except:
                print(color.red('保存课程列表失败'), flush=True)
    except:
        print(color.red('保存课程列表失败'), flush=True)

def experience(driver):
    # 体验最新版本
    try:
        element = driver.find_element(By.CLASS_NAME, 'experience')
        time.sleep(1)
        element.click()
        print(color.green('正在体验最新版本'), flush=True)
    except NoSuchElementException:
        pass

# 课程列表顶部标签的关键字。不同版本文字不一样（我学的课 / 我的课程 / 我学的课(12)…），
# 旧代码写死 class='course-tab' 且要求文字完全相等，换个版本就点不到，后面就找不到课程。
COURSE_TAB_KEYWORDS = ('我学的课', '我的课程', '学习的课')

# 课程卡片可能出现的结构：老版 #stuNormalCourseListDiv/.course-name，新版是 card 或课程链接。
COURSE_CARD_SELECTORS = (
    '#stuNormalCourseListDiv [class*="course-name"]',
    '[class*="course-name"]',
    '[class*="courseName"]',
    '[class*="w_cour_txtH"]',
    '[class*="course-card"]',
    '[class*="courseCard"]',
    '[class*="course_item"]',
    '[class*="courseItem"]',
    'a[href*="courseId"]',
    'a[href*="courseid"]',
)

# 「我学的课」标签和课程列表可能在这些帧里（不同版本不一样）
COURSE_FRAME_NAMES = ('frame_content', 'iframe')

# 菜单点不动时的兜底：直接打开课程列表页（登录态靠 Cookie 复用）。
# 每个地址都会验证「是否真的出现了课程卡片」，不出现就换下一个。
COURSE_LIST_URLS = (
    'https://mooc1.chaoxing.com/visit/courses',
    'https://mooc1-1.chaoxing.com/visit/courses',
    'https://mooc2-ans.chaoxing.com/mooc2-ans/visit/courses/list',
)

# 按文字点击的 JS 兜底：Selenium 的 XPath 匹配不到时，在页面里把空白去掉再比一次。
# 2026-10-31 修正：优先点真正的 <a> / <li>（点 div/span 不会触发菜单跳转），并返回点了什么，
# 便于日志确认到底点到了哪个节点。
_CLICK_BY_TEXT_JS = """
const target = arguments[0].replace(/\\s+/g, '');
const maxLen = arguments[1];
const textOf = (node) => (node.textContent || '').replace(/\\s+/g, '');
let best = null, bestLen = 1e9;
for (const node of document.querySelectorAll('a,li,button,span,div,p')) {
  if (node.offsetParent === null) { continue; }
  const t = textOf(node);
  if (!t || t.length > maxLen || !t.includes(target)) { continue; }
  if (t.length < bestLen) { best = node; bestLen = t.length; }
}
if (!best) { return ''; }
const abs = (el) => {
  try { return el.href || new URL(el.getAttribute('href'), location.href).href; }
  catch (e) { return el.getAttribute('href') || ''; }
};
// 1) 自己或祖先是链接
const link = best.closest ? best.closest('a') : null;
if (link) { link.click(); return 'a=' + abs(link); }
// 2) 后代里有链接（<li><a>我学的课</a></li> 这种最常见）
const inner = best.querySelector ? best.querySelector('a[href]') : null;
if (inner) { inner.click(); return 'inner=' + abs(inner); }
// 3) 退而点最近的 li，并把它的属性带回去，便于判断为什么没反应
const item = best.closest ? best.closest('li') : null;
if (item) {
  item.click();
  return 'li=' + textOf(item).slice(0, 20)
       + '|cls=' + (item.className || '').slice(0, 30)
       + '|onclick=' + ((item.getAttribute('onclick') || '').slice(0, 40));
}
best.click();
return 'node=' + best.tagName;
"""

# 直接按链接文字跳转（点不动时的最后一招）：只对真实 http(s) 链接生效
_GOTO_BY_TEXT_JS = """
const target = arguments[0].replace(/\\s+/g, '');
for (const link of document.querySelectorAll('a')) {
  const t = (link.textContent || '').replace(/\\s+/g, '');
  if (!t.includes(target)) { continue; }
  const href = link.getAttribute('href') || '';
  if (/^https?:/i.test(href)) { window.location.href = href; return href; }
  if (href && !/^javascript:/i.test(href)) { window.location.href = href; return href; }
}
return '';
"""


def _switch_to_frame(driver, name):
    """切到指定帧（None = 顶层）；切不到返回 False，不影响调用方继续尝试别的帧。"""
    try:
        driver.switch_to.default_content()
        if name:
            driver.switch_to.frame(name)
        return True
    except Exception:
        return False


# 最近一次 JS 点击点到了什么（`a=<href>` / `inner=<href>` / `li=<文本>|...`），
# 用来在"点了没跳"时按链接地址直接跳转。
_last_click_detail = ''


def _click_text_keyword(driver, keywords, timeout=8, max_text=30):
    """按文字关键字点元素，返回是否点到。

    · 用 contains 匹配，不要求完全相等，也不依赖 class 名；
    · 跳过文字很长的大容器（否则会点到包住整页的 div）；
    · 普通 click 被遮罩挡住时退回 JS click；
    · Selenium 找不到时再跑一次 JS（去掉空白后比较，兼容「我 学 的 课」被样式拆开）。
    """
    global _last_click_detail
    end = time.time() + max(1, timeout)
    while True:
        for keyword in keywords:
            try:
                candidates = driver.find_elements(
                    By.XPATH, "//*[contains(normalize-space(.), '%s')]" % keyword)
            except Exception:
                candidates = []
            for node in candidates[:8]:
                try:
                    text = (node.text or '').strip()
                    if not text or len(text) > max_text:
                        continue
                    if not node.is_displayed():
                        continue
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", node)
                    try:
                        node.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", node)
                    print(color.green(f'已点击「{keyword}」'), flush=True)
                    return True
                except Exception:
                    continue
            try:
                hit = driver.execute_script(_CLICK_BY_TEXT_JS, keyword, max_text)
            except Exception:
                hit = ''
            if hit:
                _last_click_detail = str(hit)
                print(color.green(f'已点击「{keyword}」（JS：{_last_click_detail[:80]}）'), flush=True)
                return True
        if time.time() >= end:
            return False
        time.sleep(0.5)


def _wait_course_list(driver, timeout=8):
    """等课程列表渲染出来：任一个可搜索的帧里出现课程卡片就算成功。"""
    end = time.time() + max(1, timeout)
    while True:
        for frame in (None,) + COURSE_FRAME_NAMES:
            if not _switch_to_frame(driver, frame):
                continue
            if _collect_course_cards(driver):
                return True
        if time.time() >= end:
            return False
        time.sleep(0.5)


def _goto_course_tab(driver, keywords):
    """按链接文字直接跳转（点不动时的兜底），返回跳转到的地址。"""
    for frame in (None,) + COURSE_FRAME_NAMES:
        if not _switch_to_frame(driver, frame):
            continue
        for keyword in keywords:
            try:
                href = driver.execute_script(_GOTO_BY_TEXT_JS, keyword)
            except Exception:
                href = ''
            if href:
                return str(href)
    return ''


def _open_course_list_via_url(driver, timeout=10):
    """直接打开课程列表页（菜单点不动时的兜底），返回 (是否成功, 最后试的地址)。"""
    last = ''
    for url in COURSE_LIST_URLS:
        try:
            driver.get(url)
        except Exception as e:
            print(color.yellow(f'打开 {url} 失败：{e}'), flush=True)
            continue
        last = url
        time.sleep(2)
        if _wait_course_list(driver, timeout=timeout):
            print(color.green(f'已通过地址直接打开课程列表：{url}'), flush=True)
            return True, url
        print(color.yellow(f'{url} 上没有看到课程卡片'), flush=True)
    return False, last


def _click_course_tab(driver, timeout=15):
    """点「我学的课」并**确认真的进去了**（看到课程卡片才算成功）。

    2026-10-31 修正：上一版点完不看结果，日志里写着「已进入列表」实际还停在「我的课表」。
    现在点完等 8 秒，列表没出现就换帧/换招；最后按链接 href 直接跳一次。
    """
    end = time.time() + max(1, timeout)
    while True:
        for frame in (None,) + COURSE_FRAME_NAMES:
            if not _switch_to_frame(driver, frame):
                continue
            if _click_text_keyword(driver, COURSE_TAB_KEYWORDS, timeout=1.5):
                if _wait_course_list(driver, timeout=6):
                    return True
                print(color.yellow('点了「我学的课」但列表没出来，换一种方式重试'), flush=True)
        if time.time() >= end:
            break
        time.sleep(0.5)

    # 点到的是链接但页面没跳：直接按那个地址走
    href = ''
    if _last_click_detail.startswith(('a=', 'inner=')):
        href = _last_click_detail.split('=', 1)[1].strip()
    if href:
        print(color.yellow(f'按菜单链接直接跳转：{href[:90]}'), flush=True)
        try:
            driver.get(href)
            time.sleep(2)
            if _wait_course_list(driver, timeout=8):
                return True
        except Exception:
            pass

    href = _goto_course_tab(driver, COURSE_TAB_KEYWORDS)
    if href:
        print(color.yellow(f'改为直接跳转：{href[:90]}'), flush=True)
        time.sleep(2)
        if _wait_course_list(driver, timeout=8):
            return True
    try:
        driver.switch_to.default_content()
    except Exception:
        pass
    return False


def _collect_course_cards(driver):
    """收集当前帧里的「课程名 -> 元素」，兼容新旧两套卡片结构。"""
    cards = {}
    for selector in COURSE_CARD_SELECTORS:
        try:
            nodes = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        for node in nodes:
            try:
                name = (node.get_attribute('title') or '').strip()
                if not name:
                    name = (node.text or '').strip().split('\n')[0].strip()
            except Exception:
                continue
            if not name or len(name) > 60:
                continue
            cards.setdefault(name, node)
    return cards


def _locate_course(driver, course_name, timeout=15):
    """跨帧找课程卡片并点击，返回 (是否点到, 看到的课程名列表)。"""
    end = time.time() + max(1, timeout)
    seen = []
    while True:
        for frame in (None,) + COURSE_FRAME_NAMES:
            if not _switch_to_frame(driver, frame):
                continue
            cards = _collect_course_cards(driver)
            if cards:
                seen = list(cards)[:12]
                for name, node in cards.items():
                    if course_name in name or name in course_name:
                        try:
                            driver.execute_script("arguments[0].scrollIntoView();", node)
                            driver.execute_script("arguments[0].click();", node)
                        except Exception:
                            continue
                        try:
                            driver.switch_to.default_content()
                        except Exception:
                            pass
                        return True, seen
        if time.time() >= end:
            break
        time.sleep(0.5)
    try:
        driver.switch_to.default_content()
    except Exception:
        pass
    return False, seen


def _save_course_names(names, phone_number):
    """把看到的课程名写进 tool/course_name.json（界面里的课程下拉框用它）。"""
    if not names:
        print(color.red('获取课程列表失败'), flush=True)
        return
    try:
        path = paths.data('tool', 'course_name.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        merged = list(dict.fromkeys(list(data.get(phone_number, [])) + list(names)))
        data[phone_number] = merged
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(color.green(f'保存课程列表成功,共有{len(merged)}个课程'), flush=True)
    except Exception:
        print(color.red('保存课程列表失败'), flush=True)


def describe_course_page(driver):
    """课程列表找不到时，把页面结构打进日志，便于定位是哪个版本的版式。"""
    parts = []
    try:
        parts.append('url=%s' % (driver.current_url or '')[:120])
    except Exception:
        parts.append('url=读取失败')
    try:
        parts.append('title=%s' % (driver.title or '')[:40])
    except Exception:
        parts.append('title=读取失败')
    for frame in (None,) + COURSE_FRAME_NAMES:
        if not _switch_to_frame(driver, frame):
            continue
        label = frame or 'top'
        try:
            srcs = [(element.get_attribute('src') or '')[:60]
                    for element in driver.find_elements(By.TAG_NAME, 'iframe')]
            parts.append('%s frames=[%s]' % (label, ' | '.join(srcs[:3]) or '无'))
        except Exception:
            parts.append('%s frames=读取失败' % label)
        try:
            samples = []
            for node in driver.find_elements(By.CSS_SELECTOR, '[class*="cour"], [class*="Cour"]')[:8]:
                text = (node.text or '').strip().replace('\n', ' ')
                if text:
                    cls = (node.get_attribute('class') or '')[:24]
                    samples.append('%s=%s' % (cls, text[:24]))
            parts.append('%s 课程元素=[%s]' % (label, ' / '.join(samples) or '无'))
        except Exception:
            pass
    try:
        driver.switch_to.default_content()
    except Exception:
        pass
    return '; '.join(parts)


def choice_course(driver, course_name,speed,task_type,phone_number,_retry=True):
    # time.sleep(200)
    """
    选择指定名称的课程

    参数:
    driver: WebDriver 对象，用于控制浏览器
    course_name: 字符串，要选择的课程名称

    返回:
    无
    """
    # 1) 进入课程中心：新泛雅 → 课程 → 首页（保持原有优先级）
    try:
        driver.find_element(By.CSS_SELECTOR, '[title="新泛雅"]').click()
        time.sleep(1)
    except Exception:
        try:
            element = driver.find_element(By.CSS_SELECTOR, '[title*="课程"]')
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.5)  # 稍等滚动动画完成
            element.click()
            time.sleep(1)
        except NoSuchElementException:
            try:
                driver.find_element(By.CSS_SELECTOR, '[title*="首页"]').click()
                time.sleep(1)
            except Exception:
                pass
    time.sleep(2)

    # 2) 点「我学的课」标签：顶层和各内容帧都试一遍（不同版本位置不一样）
    if _click_course_tab(driver):
        print(color.green('已进入「我学的课」列表'), flush=True)
    else:
        # 菜单点不进去（常见于纯前端路由的 li）：直接打开课程列表页
        print(color.yellow('菜单没点进去，改为直接打开课程列表页'), flush=True)
        ok, last_url = _open_course_list_via_url(driver)
        if ok:
            print(color.green('已进入「我学的课」列表'), flush=True)
        else:
            print(color.yellow(f'直接打开课程列表也没成功（最后试的是 {last_url}）'), flush=True)
            print(color.yellow('课程列表诊断：' + describe_course_page(driver)), flush=True)
    time.sleep(1)

    # 3) 找课程卡片（跨帧 + 轮询等待异步渲染，最多 15 秒）
    print(color.green(f'正在定位《{course_name}》...'), flush=True)
    found, names = _locate_course(driver, course_name)
    if found:
        _save_course_names(names, phone_number)
        if task_type != '作业':
            set_speed(speed, driver)
        print(color.green(f'您已选择《{course_name}》'), flush=True)
        return

    # 4) 没找到：先把页面结构写进日志，再试一次「体验最新版本」
    print(color.yellow(f'没看到《{course_name}》，当前看到的课程：{names or "（空）"}'), flush=True)
    print(color.yellow('课程列表诊断：' + describe_course_page(driver)), flush=True)
    if _retry:
        try:
            driver.execute_script(
                "arguments[0].click();", driver.find_element(By.CSS_SELECTOR, ".experience"))
            print(color.green('正在体验最新版本'), flush=True)
            if not turn_page(driver, '新泛雅'):
                turn_page(driver, '课程')
            element = driver.find_elements(By.XPATH, '//*[@id="stukc"]/div[1]/div[1]/div/a')
            time.sleep(2)
            if len(element) != 0:
                element[0].click()
                driver.find_element(
                    By.XPATH, '//*[@id="stukc"]/div[1]/div[1]/div/div/ul/li[1]').click()
            choice_course(driver, course_name, speed, task_type, phone_number, _retry=False)
            return
        except Exception:
            pass

    # 5) 仍然没有：等人手动打开课程（最多 3 分钟），期间定时提示
    print(color.red(f"未找到《{course_name}》这门课程，请检查名称是否正确，或手动选择你要学习的课程，打开该课程后等待片刻"),
          flush=True)
    try:
        driver.switch_to.default_content()
        now_window_handles = len(driver.window_handles)
        waited = 0
        while len(driver.window_handles) == now_window_handles and waited < 180:
            time.sleep(2)
            waited += 2
            if waited % 30 == 0:
                print(color.yellow(f'等待手动打开课程…已等 {waited} 秒'), flush=True)
        time.sleep(1)
    except Exception:
        pass
    return

def new_find_mission(driver,speed):

    course_list=driver.find_element(By.CLASS_NAME,'list-four')
    #寻找正在学习中的课程
    all_course=course_list.find_elements(By.TAG_NAME,'li')
    for course in all_course:
        try:
            course.find_element(By.CSS_SELECTOR,"[class='list-status studying']").click()
            set_speed(speed, driver)
            return
        except NoSuchElementException:
            pass
    else:
        print(color.red('该页未找到正在学习中的课程，点击下一页'),flush=True)
        driver.find_element(By.CLASS_NAME,'arrow').click()
        time.sleep(2)
        new_find_mission(driver,speed)

def _open_first_chapter(driver, speed):
    """没有「未完成任务点」时，从章节列表的最前面打开一个节点。

    用户要求：考试/测验也要做。考试在很多课程里不算任务点，旧逻辑遇到
    「所有任务点均已完成」就整门跳过，考试永远轮不到。这里改为按顺序尝试
    几种章节/知识点节点，能进到学生学习页就返回 True，由 run() 逐页往后扫。
    """
    candidates = (
        '.catalog_tishi120',                  # 未完成任务点（正常情况）
        '[class*="catalog_tishi"]',           # 其它状态的任务点
        '.catalog_jiedian',                   # 知识点节点
        'a[onclick*="getTeacherAjax"]',       # 章节节点
        'li[onclick*="getTeacherAjax"]',
        '.catalog_name',
    )
    for selector in candidates:
        try:
            nodes = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        # 每个选择器最多试 3 个节点：点第一个没进学习页，多半这一批都不对，避免一页刷几十秒
        for node in nodes[:3]:
            try:
                if not node.is_displayed():
                    continue
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", node)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", node)
            except Exception:
                continue
            time.sleep(2)
            if _landed_on_study_page(driver):
                print(color.magenta(f'已从章节列表进入：{selector}'), flush=True)
                try:
                    set_speed(speed, driver)
                except Exception:
                    pass
                return True
    return False


def _landed_on_study_page(driver):
    """判断是否已经离开目录页、进入了学生学习页。"""
    try:
        driver.switch_to.default_content()
        driver.switch_to.frame('iframe')
        driver.find_element(By.CLASS_NAME, 'prev_title')
        return True
    except Exception:
        return False
    finally:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass


def find_mission(driver,task_type,speed,course_name):
    # 点击开始学习
    try:
        element = driver.find_element(By.CSS_SELECTOR,'[class="start-study readclosecoursepop"]')
        element.click()
    except:
        pass
    experience(driver)
    # 点击章节/作业标签（页面刚打开时元素可能还没出来，等一会儿）
    elements = _wait_elements(driver, By.CLASS_NAME, 'nav_content', timeout=15)
    if not elements:
        # 有些课程页没有 nav_content，直接找「章节 / 作业」标签
        tab = _wait_element(driver, By.CSS_SELECTOR,
                            "li[data-nav-name='%s']" % task_type, timeout=10)
        if tab is None:
            tab = _wait_element(driver, By.CSS_SELECTOR,
                                "li[data-nav-name*='%s']" % task_type, timeout=3)
        if tab is None:
            print(color.red(f'课程页面没有出现「{task_type}」标签，跳过本课程'), flush=True)
            print(color.yellow(f'当前页面标题：{_safe_title(driver)}'), flush=True)
            return False
        try:
            tab.click()
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", tab)
            except Exception:
                print(color.red(f'点击「{task_type}」标签失败，跳过本课程'), flush=True)
                return False
        elements = []
    else:
        for element in elements:
            if element.text== task_type:
                element.click()
                break
    try:
        driver.switch_to.frame(driver.find_element(By.TAG_NAME, 'iframe'))
    except NoSuchElementException:
        table = driver.find_element(By.CSS_SELECTOR, "[class='tabs font15 color333 fl']")
        # 点击全部知识点
        table.find_elements(By.TAG_NAME, 'a')[2].click()
        time.sleep(1)
        new_find_mission(driver,speed)
        return True
    # 切换到名为 frame_content-zj 的 iframe
    if task_type == '作业':
        return True
    try:
        # 查找待完成任务点的元素
        element = driver.find_element(By.CSS_SELECTOR, '.catalog_tishi120')
    except:
        driver.switch_to.default_content()
        iframes=driver.find_elements(By.TAG_NAME, 'iframe')
        print(len(iframes))
        for iframe in iframes:
            driver.switch_to.frame(iframe)
            try:
                element= driver.find_element(By.CSS_SELECTOR, '.catalog_tishi120')
                break
            except:
                driver.switch_to.default_content()
                continue
        else:
            # 没有未完成任务点：可能只剩考试/测验（不算任务点）。
            # 按用户要求改为「从章节列表最前面进去往后扫」，让 run() 发现考试。
            print(color.yellow('未找到未完成任务点，改为从章节最前面开始扫描（用于发现考试/测验）'),
                  flush=True)
            try:
                driver.switch_to.default_content()
                driver.switch_to.frame('iframe')
            except Exception:
                pass
            if _open_first_chapter(driver, speed):
                return True
            print(color.red('章节列表也点不进去，跳过本课程'), flush=True)
            return False
    refresh_process(driver,course_name)
    # 打印提示信息，表示已检测到未完成点
    print(color.magenta('已检测到未完成点'),flush=True)
    time.sleep(0.5)
    #滚动到未完成的任务点的位置
    driver.execute_script("arguments[0].scrollIntoView();", element)
    set_speed(speed, driver)
    # 点击待完成任务点的元素
    driver.execute_script("arguments[0].click();", element)
    return True

def refresh_process(driver,course_name):
    try:
        process_text=driver.find_element(By.CLASS_NAME, 'xs_head_name').text.strip()
        # 分别提取两个数字
        match = re.search(r'已完成任务点:\s*(\d+)/(\d+)', process_text)
        if match:
            done = int(match.group(1))  # 7
            total = int(match.group(2))  # 17
            save_process(course_name,done,total)
    except Exception as r:
        print(color.red(f'刷新进度失败'), flush=True)

def _safe_title(driver) -> str:
    try:
        return (driver.title or '')[:60]
    except Exception:
        return '（读取失败）'


def _wait_element(driver, by, value, timeout=10, interval=0.5):
    """等元素出现；超时返回 None。

    页面刚打开/刚切窗口时直接 find_element 会立刻抛 NoSuchElementException，
    以前就是这么把整门课带崩的（报错还显示成「浏览器启动失败」）。
    """
    end = time.time() + max(0.5, timeout)
    while True:
        try:
            return driver.find_element(by, value)
        except Exception:
            if time.time() >= end:
                return None
            time.sleep(interval)


def _wait_elements(driver, by, value, timeout=10, interval=0.5):
    end = time.time() + max(0.5, timeout)
    while True:
        try:
            found = driver.find_elements(by, value)
        except Exception:
            found = []
        if found or time.time() >= end:
            return found
        time.sleep(interval)


def _window_titles(driver, limit=6):
    """列出所有窗口标题（当前窗口前面加 *），排查「切错窗口」用。"""
    try:
        current = driver.current_window_handle
    except Exception:
        current = None
    try:
        handles = driver.window_handles or []
    except Exception:
        handles = []
    titles = []
    for handle in handles[:limit]:
        try:
            driver.switch_to.window(handle)
            titles.append('%s%s' % ('*' if handle == current else '',
                                    (driver.title or '')[:28]))
        except Exception:
            continue
    try:
        if current:
            driver.switch_to.window(current)
    except Exception:
        pass
    return ' | '.join(titles) or '（没有窗口）'


def _switch_to_newest_window(driver, before_handles, timeout=10):
    """切到点击之后**新开**的窗口（不依赖标题），返回是否切到。

    有的任务点会在新标签页里打开学习页，标题也不叫「学生学习页面」；
    只按标题切窗口会失败，然后继续在目录页上找元素 → 页面无法识别。
    """
    before = set(before_handles or [])
    end = time.time() + max(1, timeout)
    while time.time() < end:
        try:
            handles = driver.window_handles or []
        except Exception:
            handles = []
        new = [handle for handle in handles if handle not in before]
        if new:
            try:
                driver.switch_to.window(new[-1])
                return True
            except Exception:
                pass
        time.sleep(0.5)
    return False


def _close_course_tab(driver):
    """关掉当前课程窗口；只剩一个窗口时不要关，避免把会话关没。"""
    try:
        handles = driver.window_handles or []
    except Exception:
        handles = []
    if len(handles) > 1:
        try:
            driver.close()
            time.sleep(1)
        except Exception:
            pass
    else:
        print(color.yellow('当前只剩一个窗口，跳过关闭课程页'), flush=True)


def turn_page(driver,page_name,timeout=20):
    """切换到标题包含 page_name 的窗口。

    新开标签页时标题要等页面加载后才出现，旧实现只 sleep(1) 就判断，
    拿不到就返回 False，调用方却继续在旧页面上找元素 → 连锁报错。
    这里改成轮询等待，并且对 window_handles 为空/会话失效做防护。
    """
    end = time.time() + max(1, timeout)
    last_error = ''
    while True:
        try:
            handles = driver.window_handles or []
        except Exception as e:
            last_error = str(e)
            handles = []
        for handle in handles:
            try:
                driver.switch_to.window(handle)
                if page_name in (driver.title or ''):
                    return True
            except Exception as e:
                last_error = str(e)
                continue
        if time.time() >= end:
            break
        time.sleep(0.5)
    if last_error:
        print(color.yellow(f'切换窗口失败：{last_error}'), flush=True)
    return False

def fold(driver):
    """折叠侧边目录"""
    try:
        element = driver.find_element(By.XPATH, '//*[@id="selector"]/div[2]')
        element.click()
        time.sleep(1)
    except:
        pass

def set_speed(speed,driver):
    global condition
    if not condition:
        return
    print(color.blue(f'调节倍数为：{speed}X'), flush=True)
    try:
        speed=int(speed)-1
        # 走 CDP 发给本标签页，多账号并发时不会打到别人的窗口上
        sent = browser_ext.press_key(driver, 'd', times=int(speed) * 10, interval=0.1)
        if sent == 0:
            print(color.yellow('按键未送达，倍速可能未生效'), flush=True)
        print(color.green('调节成功'), flush=True)
        condition=False
    except Exception as e:
        print(color.yellow(f'调节失败{e}'), flush=True)
        condition=True

def _scan_content_types(driver, content_types, found):
    """在当前帧里扫一遍内容类型，把命中的塞进 found。"""
    for name, by, selector in content_types:
        if name in found:
            continue
        try:
            driver.find_element(by, selector)
            found[name] = selector
        except NoSuchElementException:
            pass
    return found


def page_message(driver, max_frames=4):
    """检测页面内容类型，返回包含视频、PPT、测验、直播、讨论、音频、阅读的字典。

    2026-10-31 修正：新版学习页是 `mooc1-2.../visit/courses/study?s=...`，
    **外层只套了一个没有 id 的 iframe**，内容全在里边；旧代码只认 `#iframe`，
    所以整页"无法识别"，刷几次就被当成异常页跳过。
    现在按顺序扫：顶层文档 → `#iframe` → 其它任何 iframe（最多 4 个）。
    """
    # 内容类型配置：(名称, 查找方式, 选择器)
    CONTENT_TYPES = [
        ('视频', By.CSS_SELECTOR, '[class="ans-attach-online ans-insertvideo-online"]'),
        ('ppt', By.CSS_SELECTOR, '[class="ans-attach-online insertdoc-online-ppt"]'),
        ('ppt', By.CSS_SELECTOR, '[class="ans-attach-online insertdoc-online-pdf"]'),
        # 测验 iframe 用 src 包含匹配：平台前端发版会改 ?v= 后面的构建号，
        # 有的部署还会把 src 写成绝对 URL；前缀匹配也会漏（整章测验被静默跳过）。
        ('测验', By.CSS_SELECTOR, 'iframe[src*="/ananas/modules/work/index.html"]'),
        ('直播', By.CSS_SELECTOR, '[src^="/ananas/modules/live/index.html"]'),
        ('讨论', By.CSS_SELECTOR, '[src^="/ananas/modules/insertbbs/index.html"]'),
        ('音频', By.CSS_SELECTOR, '[class="ans-attach-online ans-insertaudio"]'),
        ('阅读', By.CSS_SELECTOR, '[class="ans-attach-online ans-book"]'),
        ('阅读', By.CSS_SELECTOR, '[src^="/ananas/modules/read/indexV2.html"]'),
    ]

    page_message_dict = {}
    original_wait = driver.timeouts.implicit_wait  # 保存原始等待时间
    driver.implicitly_wait(0)

    try:
        # 1) 顶层文档
        try:
            driver.switch_to.default_content()
            _scan_content_types(driver, CONTENT_TYPES, page_message_dict)
        except Exception:
            pass
        # 2) 逐帧下钻（#iframe 只是其中一个，新版可能用无 id 的 iframe）
        if not page_message_dict:
            for index in range(max_frames):
                try:
                    driver.switch_to.default_content()
                    frames = driver.find_elements(By.TAG_NAME, 'iframe')
                    if index >= len(frames):
                        break
                    driver.switch_to.frame(frames[index])
                except Exception:
                    continue
                _scan_content_types(driver, CONTENT_TYPES, page_message_dict)
                if page_message_dict:
                    break
    finally:
        driver.implicitly_wait(original_wait)  # 恢复原始等待时间
        try:
            driver.switch_to.default_content()
        except Exception:
            pass

    return page_message_dict


def describe_page(driver, limit=4):
    """诊断用：打印当前页面标题 + 顶层/学习页里所有 iframe 的 src。

    识别不到页面时调用，日志里能直接看到这一页到底是什么模块，
    不用再靠人猜或用截图。
    """
    parts = []
    try:
        parts.append('title=%s' % _short(driver.title or '', 40))
    except Exception:
        parts.append('title=读取失败')
    for scope in ('top', 'iframe'):
        try:
            driver.switch_to.default_content()
            if scope == 'iframe':
                driver.switch_to.frame('iframe')
            srcs = []
            for element in driver.find_elements(By.TAG_NAME, 'iframe'):
                src = (element.get_attribute('src') or '').strip()
                if src:
                    srcs.append(src[:80])
            parts.append('%s=[%s]' % (scope, ' | '.join(srcs[:limit]) if srcs else '无 iframe'))
        except Exception as e:
            parts.append('%s=读取失败(%s)' % (scope, e))
    try:
        driver.switch_to.default_content()
    except Exception:
        pass
    return '; '.join(parts)

NEXT_PAGE_XPATH = '//*[@id="prevNextFocusNext"]'

# 「下一页/下一节」按钮在不同版式里的备选找法（新版学习页没有 prevNextFocusNext）
NEXT_PAGE_XPATHS = (
    NEXT_PAGE_XPATH,
    '//*[self::a or self::button][normalize-space(.)="下一页"]',
    '//*[self::a or self::button][normalize-space(.)="下一节"]',
    '//*[self::a or self::button][contains(normalize-space(.), "下一页")]',
    '//*[self::a or self::button][contains(@class, "next")]',
    '//*[contains(@class, "nextBtn") or contains(@class, "next-btn")]',
)


def _find_next_button(driver):
    """找「下一页/下一节」按钮，兼容新旧版式；找不到返回 None。"""
    for xpath in NEXT_PAGE_XPATHS:
        try:
            nodes = driver.find_elements(By.XPATH, xpath)
        except Exception:
            continue
        for node in nodes[:4]:
            try:
                if not node.is_displayed():
                    continue
                size = node.size or {}
                if size.get('width', 0) <= 0 or size.get('height', 0) <= 0:
                    continue
                return node
            except Exception:
                continue
    return None


def _looks_like_home_page(driver) -> bool:
    """是不是被踢回登录页/个人空间首页了（会话失效、别处登录都会这样）。"""
    try:
        url = (driver.current_url or '').lower()
    except Exception:
        url = ''
    try:
        title = (driver.title or '')
    except Exception:
        title = ''
    if 'passport' in url or 'login' in url:
        return True
    if 'i.chaoxing.com/base' in url or url.rstrip('/').endswith('i.chaoxing.com'):
        return True
    return '用户登录' in title


def _looks_like_course_home(driver) -> bool:
    """是不是"被打回的课程空壳页"（/visit/courses/study 但没有学习内容）。

    用户实测：这个 URL 是平台把人打回来时落的页面，里面没有 `#iframe`、没有任务点，
    也没有「下一页」，在这一页上翻页只会空转，正确做法是回课程页重新定位任务点。
    """
    try:
        url = (driver.current_url or '').lower()
    except Exception:
        return False
    if '/visit/courses/study' not in url:
        return False
    # 有内容就算正常学习页（page_message 已经先判过一次，这里只是兜底）
    try:
        return not bool(driver.find_elements(By.ID, 'iframe'))
    except Exception:
        return True

# 识别不到页面时先刷新几次（平台偶尔要刷新才把内容渲染出来），仍不行才跳过
UNKNOWN_REFRESH_LIMIT = 3

# 连续几次「页面内容完全没变化」就结束本课程，避免死循环
STUCK_LIMIT = 3

# 连续多少个页面认不出来就结束本课程。认不出的页面现在只截图 + 直接下一节（很便宜），
# 所以给得宽一些，避免把一门课里几页纯文本知识点误判成"整门课没救了"。
UNKNOWN_SKIP_LIMIT = 10


# 能从 URL / iframe src 里稳定区分「第几章第几个任务点」的参数。
# 不收 s= / ktoken= 这类每次请求都可能变的随机 token，否则刷新也会被误判成「换页了」。
_PAGE_IDENTITY_KEYS = ('chapterid', 'courseid', 'clazzid', 'knowledgeid',
                       'objectid', 'jobid', 'cardid')


def _page_identity(driver):
    """当前学习页的「身份」：URL 与各 iframe src 里能区分章节的稳定参数。

    2026-11-05 修复：新版学习页切到下一节时，模块 iframe 的 class 和 src 前 80 字符
    完全不变（都是 .../ananas/modules/video/index.html?v=2026-1030-1154），
    `.prev_title` 也取不到，导致 `_content_signature()` 对所有视频页返回同一个值；
    `run()` 连续 3 次比对相同就误报卡住、提前结束整门课。
    诊断日志里 `studentstudy?chapterId=xxx` 每次都在变，那才是换页的硬凭据。
    取不到任何稳定参数时返回空串，由调用方退回到原来的内容指纹。
    """
    urls = []
    try:
        urls.append(driver.current_url or '')
    except Exception:
        pass
    try:
        elements = driver.find_elements(By.TAG_NAME, 'iframe')[:8]
    except Exception:
        elements = []
    for element in elements:
        try:
            src = element.get_attribute('src') or ''
        except Exception:
            continue
        if src:
            urls.append(src)
    keys = []
    for url in urls:
        for key in _PAGE_IDENTITY_KEYS:
            for value in re.findall(r'[?&]' + key + r'=([^&#\s]+)', url or '', flags=re.I):
                item = '%s=%s' % (key, value)
                if item not in keys:
                    keys.append(item)
    # 排序后再拼：iframe 异步加载/顺序抖动不该让同一个页面产生不同指纹
    return ','.join(sorted(keys))


def _content_signature(driver):
    """当前学习页的内容指纹：章节标题 + 已完成任务点数 + 任务点总数 + 模块 iframe 的 src。

    平台切到下一个任务点时**不一定重建 #iframe**（常见做法是改 iframe 的 src 或直接换内容），
    所以「元素句柄是否失效」不能当作翻页成功的判据——按句柄判断会误报「没前进」，
    进而把整门课提前结束，看起来就是「后面章节/测验被跳过」。
    这里改用内容特征：完成数、任务点数、模块 src 任何一项变化都算换页。
    """
    title = ''
    finished = -1
    icons = -1
    srcs = ''
    try:
        driver.switch_to.default_content()
        driver.switch_to.frame('iframe')
        try:
            title = driver.find_element(By.CLASS_NAME, 'prev_title').get_attribute('title') or ''
        except Exception:
            title = ''
        try:
            finished = len(driver.find_elements(By.CSS_SELECTOR, '[class*="ans-job-finished"]'))
            icons = len(driver.find_elements(By.CLASS_NAME, 'ans-job-icon-clear'))
        except Exception:
            pass
        try:
            srcs = ';'.join((element.get_attribute('src') or '')[:80]
                            for element in driver.find_elements(By.TAG_NAME, 'iframe'))
        except Exception:
            srcs = ''
    except Exception:
        pass
    finally:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
    return '%s|%s|%s|%s' % (title, finished, icons, srcs)


def _short(text, limit=70):
    return (text or '').replace('\n', ' ')[:limit]


def click_next_page(driver, pass_face):
    """点「下一页」，返回 False 表示课程已到底；True 表示点过了。

    是否真的换页**不在这里判断**（平台换内容时 #iframe 不失效，按句柄判断会误报「没前进」），
    交给 run() 用 `_content_signature()` 比对：连续几次内容都没变化才算卡死。
    """
    global error_num

    def _try_click():
        """在「当前上下文」里找并点下一页；返回 'clicked' / 'finished' / 'none'。"""
        button = _find_next_button(driver)
        if button is None:
            return 'none'
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        except Exception:
            pass
        try:
            button.click()
        except ElementNotInteractableException:
            return 'finished'
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", button)
            except Exception:
                return 'none'
        return 'clicked'

    # 1) 先在顶层点
    try:
        driver.switch_to.default_content()
    except Exception:
        pass
    result = _try_click()

    # 2) 顶层没有：逐个进 iframe 找（新版学习页把内容/按钮都放在无 id 的 iframe 里）
    if result == 'none':
        for index in range(4):
            try:
                driver.switch_to.default_content()
                frames = driver.find_elements(By.TAG_NAME, 'iframe')
                if index >= len(frames):
                    break
                driver.switch_to.frame(frames[index])
            except Exception:
                continue
            result = _try_click()
            if result != 'none':
                break
    try:
        driver.switch_to.default_content()
    except Exception:
        pass

    if result == 'finished':
        print(color.red('🎉 🎉 该课程全部已完结，撒花！！！'), flush=True)
        return False
    if result == 'none':
        print(color.yellow('暂时没找到「下一页」按钮，等一会儿再点'), flush=True)
        error_num += 1
        if error_num >= 8:
            print(color.red('❌ 连续多次找不到「下一页」，结束本课程'), flush=True)
            return False
        time.sleep(2)
        return True
    error_num = 0          # 成功点击后清零，避免历史错误把后面的课拖停

    # 有的页面翻页会弹确认框，先点掉再等页面渲染
    time.sleep(0.8)
    try:
        driver.find_element(By.XPATH, '//*[@id="mainid"]/div[1]/div/div[3]/a[2]').click()
    except Exception:
        pass
    time.sleep(1.5)
    return True

chapter_name=''
def check_chapter_active(driver,multi_device):
    """判断该章节是否正在被学习"""
    global chapter_name
    if not multi_device:
        return True
    element = driver.find_element(By.CLASS_NAME, 'prev_title')
    chapter_name = element.get_attribute('title')
    record_path = paths.record('studying_record.txt')
    marker = f'正在学习{chapter_name}...\n'
    try:
        with open(record_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if marker in content:
                print(color.yellow(f'检测到{chapter_name}章节正在学习中，跳过'), flush=True)
                return False
    except FileNotFoundError:
        pass
    with open(record_path, 'a', encoding='utf-8') as f:
        f.write(marker)
    return True

def delete_record():
    """删除该章节的正在学习记录"""
    record_path = paths.record('studying_record.txt')
    try:
        with open(record_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return
    # 兼容旧版本写下的标记（转义写法）
    legacy_prefix = '\u6b63\u5728\u5237'
    if chapter_name=='':
        content = re.sub(r'正在学习.*?\.\.\.\n', '', content)
        content = re.sub(legacy_prefix + r'.*?\.\.\.\n', '', content)
    else:
        content = content.replace(f'正在学习{chapter_name}...\n', '')
        content = content.replace(f'{legacy_prefix}{chapter_name}...\n', '')
    with open(record_path, 'w', encoding='utf-8') as f:
        f.write(content)

def wait_page_message(driver, tries=3, interval=2):
    """页面可能还在加载，多试几次再判定为「无法识别」。

    旧逻辑一次识别不到就直接跳过，遇到加载慢的页面会白白漏掉任务点。
    """
    for i in range(max(1, tries)):
        try:
            message = page_message(driver)
        except Exception:
            message = {}
        if message:
            return message
        if i < tries - 1:
            time.sleep(interval)
    return {}


def dispatch_page(driver, message, course_name, choice, API, lock_screen, pass_face,
                  video_title_choice, discussion_choice, after_finish_question,
                  pass_vido, speed):
    """按页面内容类型分发处理；每类单独兜底，单点异常不中断整页。"""
    def safe(name, func):
        try:
            func()
        except UnexpectedAlertPresentException:
            try:
                driver.switch_to.alert.accept()
            except Exception:
                pass
        except Exception as e:
            print(color.red(f'{name}处理出错: {e}'), flush=True)
            save_diagnostic_screenshot(driver, f'{name}出错')

    if 'ppt' in message:
        safe('PPT', lambda: __ppt(driver, course_name))
    if '直播' in message:
        safe('直播', lambda: watch_live(driver, message['直播'], course_name))
    if '音频' in message:
        safe('音频', lambda: play_audio(driver, message['音频'], course_name))
    if '讨论' in message:
        if discussion_choice != '跳过讨论':
            safe('讨论', lambda: finish_discussion(
                driver, API, message['讨论'], discussion_choice, course_name))
        else:
            print(color.yellow(f'您已选择{discussion_choice}'), flush=True)
    if '阅读' in message:
        safe('阅读', lambda: reading(driver, message['阅读'], course_name))
    if '视频' in message:
        # 视频内弹题固定随机作答（见 task/watch_vido.py check_video_question），
        # 不再需要 API 与 video_title_choice
        safe('视频', lambda: study_page(
            driver, course_name, lock_screen, pass_vido, speed, pass_face))
    if '测验' in message:
        # 兼容旧配置里保存的值（旧版本用过一个现在不再使用的叫法）
        if choice not in ('不作答', '\u4e0d\u5237\u9898'):
            safe('测验', lambda: finish_quiz(
                driver, course_name, API, choice, after_finish_question))
        else:
            print(color.yellow('您已选择不作答，即将跳过测试题'), flush=True)


def run(driver,choice,course_name,API,lock_screen,pass_face,video_title_choice,
        discussion_choice,after_finish_question,pass_vido,speed,multi_device):
    unknown_count = 0
    no_progress = 0
    last_sig = ''
    while True:
        cond = True
        delete_face_popup(driver, pass_face)
        # 图片题被点开后可能留下一层全屏遮罩，先收掉，否则整页点击都会失效
        try:
            if image_viewer_is_open(driver):
                close_image_viewer(driver)
        except Exception:
            pass
        if check_chapter_active(driver, multi_device):
            print(color.green('正在检测页面内容'), flush=True)
            page_message_dict = wait_page_message(driver)

            if not page_message_dict:
                # 认不出来的页面本身就说明页面结构/内容变了，不能让「卡住」计数跨页累积
                # （2026-11-05：计数曾跨 38 分钟、跨多个章节挂到第 3 次，误结束整门课）。
                no_progress = 0
                last_sig = ''
                # 用户要求：认不出来的页面不要反复刷新耗时间，先截一张诊断图，然后直接点下一节。
                unknown_count += 1
                print(color.red(f'该页面无法识别（第 {unknown_count} 次）'), flush=True)
                print(color.yellow('页面诊断：' + describe_page(driver)), flush=True)
                save_diagnostic_screenshot(driver, '未识别页面')
                if _looks_like_home_page(driver):
                    print(color.red('页面已经回到首页/登录页（会话失效或被别处登录踢下线），'
                                    '结束本课程'), flush=True)
                    return 'home'
                if _looks_like_course_home(driver):
                    # 被平台打回课程空壳页：这页没有任务点也没有「下一页」，死磕只会空转
                    print(color.yellow('当前是"被打回的课程空壳页"，回去重新定位未完成任务点'),
                          flush=True)
                    return 'lost'
                if unknown_count > UNKNOWN_SKIP_LIMIT:
                    print(color.red(f'连续 {UNKNOWN_SKIP_LIMIT} 页都无法识别，结束本课程（避免空转）'),
                          flush=True)
                    return 'lost'
                print(color.yellow('跳过该页，直接点下一节'), flush=True)
            else:
                unknown_count = 0
                # 「页面身份」优先：chapterId / objectId 变了就说明确实换了页，
                # 哪怕模块 iframe 的 src、完成点数看起来一模一样。
                signature = _content_signature(driver)
                identity = _page_identity(driver)
                fingerprint = '%s||%s' % (identity, signature)
                if signature and fingerprint == last_sig:
                    no_progress += 1
                    print(color.yellow(f'第 {no_progress} 次仍停留在同一页：{_short(fingerprint)}'),
                          flush=True)
                    if no_progress >= STUCK_LIMIT:
                        print(color.yellow(
                            f'连续 {STUCK_LIMIT} 次页面身份和内容都没变化，先刷新重试一次'), flush=True)
                        print(color.yellow('页面诊断：' + describe_page(driver)), flush=True)
                        save_diagnostic_screenshot(driver, '页面卡住')
                        try:
                            driver.refresh()
                            time.sleep(2)
                        except Exception:
                            pass
                        new_identity = _page_identity(driver)
                        new_signature = _content_signature(driver)
                        refreshed = '%s||%s' % (new_identity, new_signature)
                        # 刷新后 iframe 还没加载完时 identity 会是空串，不能把「参数还没出来」
                        # 当成「换页了」，否则真卡住时会一直「刷新→误判有进展」无限循环。
                        changed = ((new_identity and new_identity != identity)
                                   or new_signature != signature)
                        if changed:
                            print(color.green('刷新后页面已变化，继续学习'), flush=True)
                            no_progress = 0
                            last_sig = refreshed
                            delete_record()
                            continue
                        # 真的卡住了：'lost' 会让 main() 回课程页重新定位任务点（最多 3 次），
                        # 不再像以前那样 return 'done' 直接把整门课判成「学完」。
                        print(color.red('刷新后仍停在同一页，回课程页重新定位任务点'), flush=True)
                        return 'lost'
                elif signature:
                    no_progress = 0
                    last_sig = fingerprint
                print(color.green(f'该页面含有{list(page_message_dict.keys())}'), flush=True)
                try:
                    dispatch_page(driver, page_message_dict, course_name, choice, API,
                                  lock_screen, pass_face, video_title_choice,
                                  discussion_choice, after_finish_question, pass_vido, speed)
                except Exception as e:
                    # 刷新一次就够了：刷新后不再原地重跑同一页，交给下面的翻页逻辑推进，
                    # 否则处理器每次都抛同一个异常时就会永久循环。
                    print(color.red(f'处理页面出错: {e}'), flush=True)
                    unknown_count += 1
                    # 刚刷新过，页面内容必然重新加载，不能让「卡住」计数挂着跨到下一轮
                    no_progress = 0
                    last_sig = ''
                    try:
                        driver.refresh()
                        time.sleep(2)
                    except Exception:
                        pass
                    if unknown_count <= UNKNOWN_REFRESH_LIMIT:
                        delete_record()
                        continue
                    print(color.yellow('该页处理连续失败，跳过该页'), flush=True)
                    unknown_count = 0
                    cond = True      # 允许推进，避免在同一页反复重试
            delete_record()

        driver.switch_to.default_content()
        if cond:
            print(color.green('跳转下一页'), flush=True)
            if not click_next_page(driver, pass_face):
                return 'done'
            time.sleep(1)
        else:
            delete_face_popup(driver, pass_face)
            fold(driver)
        time.sleep(1)


def start_browser(browser,driver_path,speed):
    print(color.green('启动浏览器中...'), flush=True)
    browser_key = 'chrome' if browser == 'chrome' else 'edge'
    if browser_key == 'chrome':
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        driver_class = webdriver.Chrome
    else:
        from selenium.webdriver.edge.service import Service
        from selenium.webdriver.edge.options import Options
        driver_class = webdriver.Edge
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")  # 禁用自动化控制提示
    if speed!='1':
        options.add_extension(paths.asset('tool', 'speed.crx'))
    options.add_extension(paths.asset('tool', 'chrome-extension.crx'))
    options.add_argument("--enable-extensions")
    options.add_argument("--disable-web-security")

    # 新电脑上没有驱动缓存时，Selenium Manager 需要联网下载；
    # 国内网络/代理缺失/Edge 刚更新时会报 NoSuchDriverException。
    # 先用本机已有的驱动（配置路径、drivers/ 目录、Selenium 缓存），没有再联网。
    resolved = None
    try:
        resolved = driver_ext.resolve(browser_key, driver_path)
    except Exception as e:
        print(color.yellow(f'解析本机驱动失败: {e}'), flush=True)
    if resolved:
        print(color.green(f'使用本机驱动: {resolved}'), flush=True)
        service = Service(resolved)
    else:
        print(color.yellow('本机没有可用驱动，交给 Selenium 自动获取'), flush=True)
        service = Service()

    try:
        driver = driver_class(service=service, options=options)
    except NoSuchDriverException:
        print(color.yellow('自动获取驱动失败，尝试按本机浏览器版本直接下载...'), flush=True)
        try:
            downloaded = driver_ext.download(browser_key)
        except Exception as e:
            message = driver_ext.human_error(browser_key, e)
            print(color.red(message), flush=True)
            raise WebDriverException(message)
        driver = driver_class(service=Service(downloaded), options=options)

    driver.implicitly_wait(2)
    return driver

def main(browser, driver_path, phone_number, password, choice, course_lst,API,after_finish_question,
         lock_screen,speed, task_type,homework,pass_face,video_title_choice,discussion_choice,pass_vido,multi_device):
    global _CURRENT_DRIVER
    driver = start_browser(browser, driver_path,speed)
    _CURRENT_DRIVER = driver
    # time.sleep(20)
    login_study(driver, phone_number, password)
    for course_name in course_lst:
        delete_record()
        choice_course(driver, course_name, speed,  task_type,phone_number)
        if not turn_page(driver, course_name):
            # 课程页可能还在加载；只提示，不在这里放弃（find_mission 里会再等导航标签）
            print(color.yellow(f'暂未切换到《{course_name}》窗口，继续等页面加载'), flush=True)
            print(color.yellow(f'当前页面标题：{_safe_title(driver)}'), flush=True)
        experience(driver)
        delete_face_popup(driver,pass_face,course_name)

        # 点任务点有可能开新标签页，先记下当前窗口，后面用它判断"是不是开了新窗口"
        try:
            before_handles = list(driver.window_handles or [])
        except Exception:
            before_handles = []

        if find_mission(driver,task_type,speed,course_name):
            if task_type=='作业':
                do_work(driver,course_name,homework,API)
                return
            if not turn_page(driver, '学生学习页面', timeout=8):
                # 学习页可能开在新标签页里、标题也不叫「学生学习页面」：
                # 切到新开的窗口再说，否则会在目录页上找元素 → 整页无法识别。
                if _switch_to_newest_window(driver, before_handles, timeout=8):
                    print(color.yellow(f'已切换到新开的页面：{_safe_title(driver)}'), flush=True)
                elif _landed_on_study_page(driver):
                    print(color.yellow(f'当前窗口就是学习页（标题：{_safe_title(driver)}），继续'),
                          flush=True)
                else:
                    print(color.yellow(f'没能切换到学习页，当前窗口：{_window_titles(driver)}'),
                          flush=True)

            if multi_device:
                monitor = PageCompat(driver)
                monitor.enable()

            delete_face_popup(driver,pass_face)
            fold(driver)
            browser_ext.press_combo(driver, 'm', browser_ext.CTRL)
            status = run(driver, choice, course_name, API, lock_screen, pass_face,
                         video_title_choice, discussion_choice, after_finish_question,
                         pass_vido, speed, multi_device)

            # 页面被平台打回空壳页 / 认不出来：回课程页重新定位任务点再继续（最多 3 次）
            retry = 0
            while status == 'lost' and retry < 3:
                retry += 1
                print(color.yellow(f'页面丢了，回课程页重新定位未完成任务点（第 {retry} 次）'),
                      flush=True)
                if not _reenter_course(driver, course_name, speed, task_type, phone_number):
                    print(color.red('回不到课程页，结束本课程'), flush=True)
                    break
                delete_face_popup(driver, pass_face)
                fold(driver)
                status = run(driver, choice, course_name, API, lock_screen, pass_face,
                             video_title_choice, discussion_choice, after_finish_question,
                             pass_vido, speed, multi_device)
            if status == 'home':
                print(color.red(f'《{course_name}》已被踢回首页/登录页，跳过剩余内容'), flush=True)
        _close_course_tab(driver)
        turn_page(driver, '个人空间')


def _reenter_course(driver, course_name, speed, task_type, phone_number):
    """从空壳页/首页回到课程页并重新定位未完成任务点。"""
    if _looks_like_home_page(driver):
        # 被踢回个人空间：重新选课进去
        choice_course(driver, course_name, speed, task_type, phone_number)
        if not turn_page(driver, course_name, timeout=10):
            print(color.yellow(f'没能切回《{course_name}》页面'), flush=True)
            return False
    else:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        if not turn_page(driver, course_name, timeout=5):
            # 还在课程页里，只是内容丢了：刷新一下再定位
            try:
                driver.refresh()
                time.sleep(2)
            except Exception:
                pass
    try:
        before = list(driver.window_handles or [])
    except Exception:
        before = []
    if not find_mission(driver, task_type, speed, course_name):
        return False
    if not turn_page(driver, '学生学习页面', timeout=8):
        _switch_to_newest_window(driver, before, timeout=5)
    return True


def extract_browser_versions(error_text):
    """从错误信息中提取浏览器和驱动版本"""

    versions = {
        'driver_supported_version': None,  # 驱动支持的版本
        'browser_version': None,  # 浏览器当前版本
        'browser_type': None  # 浏览器类型
    }

    # 模式1: 匹配ChromeDriver/EdgeDriver支持的版本
    # 兼容两种格式:
    # 1. This version of ChromeDriver only supports Chrome version 140
    # 2. This version of EdgeDriver only supports Microsoft Edge version 120
    driver_pattern = r'This version of (ChromeDriver|Microsoft Edge WebDriver) only supports (?:Chrome|Microsoft Edge) version (\d+)'
    driver_match = re.search(driver_pattern, error_text)

    if driver_match:
        versions['browser_type'] = driver_match.group(1).replace('Driver', '')
        versions['driver_supported_version'] = driver_match.group(2)

    # 模式2: 匹配当前浏览器版本
    # 兼容多种格式:
    # 1. Current browser version is 143.0.7499.193
    # 2. Current Microsoft Edge version is 120.0.2210.91
    browser_pattern = r'Current (?:browser|Microsoft Edge) version is ([\d.]+)'
    browser_match = re.search(browser_pattern, error_text)

    if browser_match:
        versions['browser_version'] = browser_match.group(1)

    return versions

def parse_versions_from_text(error_text):
    """从文本中解析版本信息的完整函数"""

    # 提取版本信息
    versions = extract_browser_versions(error_text)

    # 打印结果
    print(color.red("=" * 50))
    print("版本信息分析结果:")
    print("=" * 50)

    if versions['browser_type']:
        print(f"浏览器类型: {versions['browser_type']}")

    if versions['driver_supported_version']:
        print(f"驱动支持版本: {versions['driver_supported_version']}")

    if versions['browser_version']:
        print(f"浏览器当前版本: {versions['browser_version']}")

    # 给出建议
    print("\n" + "=" * 50)
    print("问题诊断和建议:")
    print("=" * 50)

    if versions['browser_type'] and versions['driver_supported_version'] and versions['browser_version']:
        driver_ver = int(versions['driver_supported_version'])
        browser_main_ver = int(versions['browser_version'].split('.')[0])

        if browser_main_ver > driver_ver:
            print(f"版本不兼容: {versions['browser_type']}浏览器版本(v{browser_main_ver})过高，"
                  f"但驱动仅支持到v{driver_ver}")
            print(f"📋 解决方案:")
            print(f"  1. 下载{versions['browser_type']}Driver {browser_main_ver}的版本")
            print(f"  2. 或降级{versions['browser_type']}浏览器到{driver_ver}版本")
        elif browser_main_ver < driver_ver:
            print(f"⚠️  浏览器版本(v{browser_main_ver})可能过旧")
            print(f"📋 建议: 更新{versions['browser_type']}浏览器到最新版本")
        else:
            print(f"✅ 版本匹配: {versions['browser_type']}浏览器和驱动版本一致")

    print("\n相关下载链接:")
    if versions['browser_type'] == 'Chrome':
        print("  • 谷歌驱动: https://chromedriver.chromium.org/")
        print("  • Chrome浏览器: https://www.google.com/chrome/")
    elif versions['browser_type'] == 'Microsoft Edge Web':
        print("  • Edge驱动: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/")
        print("  • Edge浏览器: https://www.microsoft.com/edge")
    print('\n具体操作步骤见用户须知')

    return versions

def _error_brief(error_msg: str) -> str:
    """取异常摘要：优先取「异常类型: 消息」那一行。

    旧实现取最后一行，遇到 WebDriver 附带的原生堆栈就只剩一句 `(No symbol) [0x...]`，
    日志面板看起来像「浏览器启动失败」，完全误导排查。
    """
    lines = [l.strip() for l in (error_msg or '').strip().splitlines() if l.strip()]
    for line in reversed(lines):
        if ('selenium.common.exceptions.' in line
                or 'Error:' in line or 'Exception:' in line):
            return line[:200]
    for line in reversed(lines):
        if (line.startswith('(No symbol)') or line.startswith('File "')
                or line.startswith('^')):
            continue
        return line[:200]
    return (lines[-1] if lines else '未知错误')[:200]


def run_main():
    try:
        with open(paths.data('tool', 'account_info.json'), 'r', encoding='utf-8') as fil:
            account_info = json.load(fil)
        main(account_info['browser'], account_info['driver_path'], account_info['phone_number'], account_info['password'],
             account_info['choice'], account_info['cour'],account_info['API'],account_info['after_finish_question'],
             account_info['lock_screen'],account_info['speed'],account_info['task_type'],account_info['homework'],
             account_info['pass_face'],account_info['video_title_choice'],account_info['discussion_choice'],
             account_info['pass_vido'],account_info['multi_device'])
    except NoSuchWindowException as e:
        print(color.red('❌ 窗口意外关闭'),flush=True)
    except SessionNotCreatedException as e:
        error_msg = traceback.format_exc()
        send_error(
            "\n作者只解决打赏用户提交的问题，请在赞助后将截图与报错信息一同发送至作者邮箱2022865286@qq.com,未赞助的用户请自行查看用户须知文件自行解决\n" + error_msg)
        print(color.red(f'❌ 浏览器驱动版本不匹配: {_error_brief(error_msg)}'), flush=True)
        # 执行分析
        result = parse_versions_from_text(error_msg)

    except NoSuchElementException as e:
        # 页面元素没找到 ≠ 浏览器启动失败：多半是页面没加载完、没切到课程页，或平台改版
        error_msg = traceback.format_exc()
        send_error(
            "\n作者只解决打赏用户提交的问题，请在赞助后将截图与报错信息一同发送至作者邮箱2022865286@qq.com,未赞助的用户请自行查看用户须知文件自行解决\n" + error_msg)
        save_diagnostic_screenshot(_CURRENT_DRIVER, '找不到元素')
        print(color.red(f'❌ 页面上找不到预期元素（不是浏览器问题）: {_error_brief(error_msg)}'), flush=True)
        print(color.yellow('常见原因：页面没加载完、课程页没切过去、平台改版；完整堆栈见 error.log'), flush=True)
    except WebDriverException as e:
        if 'ERR_INTERNET_DISCONNECTED' in str(e) or 'ERR_NAME_NOT_RESOLVED' in str(e):
            print(color.red('❌ 网络未连接，请检查网络后重试'),flush=True)
        else:
            error_msg = traceback.format_exc()
            send_error("\n作者只解决打赏用户提交的问题，请在赞助后将截图与报错信息一同发送至作者邮箱2022865286@qq.com,未赞助的用户请自行查看用户须知文件自行解决\n"+error_msg)
            save_diagnostic_screenshot(_CURRENT_DRIVER, '浏览器会话异常')
            print(color.red(f'❌ 浏览器会话异常: {_error_brief(error_msg)}'), flush=True)
            print(color.yellow('完整堆栈已写入程序目录下的 error.log，可在「报错日志」页查看'), flush=True)
    except PermissionError:
        print(color.red('请关闭该窗口后，再右键点击本程序用管理员权限打开'))
    except Exception as e:
        error_msg = traceback.format_exc()
        send_error("\n作者只解决打赏用户提交的问题，请在赞助后将截图与报错信息一同发送至作者邮箱2022865286@qq.com,未赞助的用户请自行查看用户须知文件自行解决\n"+error_msg)
        save_diagnostic_screenshot(_CURRENT_DRIVER, '程序异常')
        print(color.red(f'❌ 出错了: {_error_brief(error_msg)}'), flush=True)
        print(color.yellow('完整堆栈已写入程序目录下的 error.log，可在「报错日志」页查看'), flush=True)

if __name__ == '__main__':
    run_main()
