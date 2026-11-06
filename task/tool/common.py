from selenium.webdriver.common.by import By
from task.tool import color
from core import paths
import os
import re
import time
import ast
import json


def save_diagnostic_screenshot(driver, tag='诊断'):
    """把当前窗口截图存到 record/诊断截图/，返回路径（失败返回空串）。

    用户要求：遇到识别不了 / 处理出错的页面，都留一张截图当诊断日志，
    事后不用再靠口头描述复现。截图按 `标签_年月日_时分秒.png` 命名，不会互相覆盖。
    """
    if driver is None:
        return ''
    try:
        folder = paths.record('诊断截图')
        os.makedirs(folder, exist_ok=True)
        safe_tag = re.sub(r'[\\/:*?"<>|\s]+', '_', str(tag or '诊断')).strip('_')[:20] or '诊断'
        name = '%s_%s.png' % (safe_tag, time.strftime('%Y%m%d_%H%M%S'))
        path = os.path.join(folder, name)
        driver.save_screenshot(path)
        print(color.yellow(f'诊断截图已保存: record/诊断截图/{name}'), flush=True)
        return path
    except Exception as e:
        print(color.yellow(f'诊断截图保存失败: {e}'), flush=True)
        return ''


class Common:
    def __init__(self,driver,iframe_element,type,course_name,require_mission=True):
        self.course_name = course_name
        self.type=type
        self.driver=driver
        # 是否要求「任务点」图标存在。视频/PPT 等仍按任务点处理；
        # 测验/考试传 False —— 平台上的考试经常不算任务点，旧逻辑会把它整段跳过。
        self.require_mission = require_mission
        self.driver.switch_to.default_content()
        self.driver.switch_to.frame("iframe")
        self.iframes = self.driver.find_elements(By.CSS_SELECTOR,iframe_element)
        num = len(self.iframes)
        print(color.green(f'{self.type}数量：{num}'),flush=True)

    def check_audio_finished(self):
        """该模块是否已完成：父容器 class 含 ans-job-finished 即视为已完成。

        旧实现用 `== 'ans-attach-ct ans-job-finished'` 精确比较，class 顺序/多一个空格
        就判不出来；取父元素失败时还会直接抛异常把整页带崩。这里改为包含匹配并兜底。
        """
        try:
            parent_element = self.iframe.find_element(By.XPATH, "..")
            parent_element_class = parent_element.get_attribute("class") or ""
        except Exception:
            return False
        if 'ans-job-finished' in parent_element_class:
            print(color.green(f"该{self.type}已完成（父容器标记 ans-job-finished），跳过"), flush=True)
            return True
        return False

    def check_exist_mission(self):
        # 定位到该元素的所有兄弟元素
        all_elements = self.iframe.find_elements(By.XPATH,  "preceding-sibling::* | following-sibling::*")
        for element in all_elements:
            class_attr = element.get_attribute("class") or ""
            if 'ans-job-icon ' in class_attr:
                print(color.green(f"该{self.type}存在任务点"), flush=True)
                return True
        print(color.green(f"该{self.type}不存在任务点"), flush=True)
        return False
    def main(self):
        num=0
        for iframe in self.iframes:
            self.driver.switch_to.default_content()
            self.driver.switch_to.frame("iframe")
            self.iframe = iframe
            num+=1

            # 检测是否存在任务点（测验/考试不要求任务点，见 require_mission）
            if self.require_mission and not self.check_exist_mission():
                print(color.yellow(f'第{num}个{self.type}没有任务点标记，跳过'), flush=True)
                continue
            # 检查任务点是否已完成
            if self.check_audio_finished():
                continue
            # 滚动到任务点：有的模块（尤其不算任务点的考试）前面没有兄弟 div，
            # 取不到就不滚动，绝不能因此把整场测验带崩。
            try:
                anchor = self.iframe.find_element(By.XPATH, "preceding-sibling::div[1]")
                self.driver.execute_script("arguments[0].scrollIntoView();", anchor)
            except Exception:
                pass
            print(color.green(f'开始第{num}个{self.type}'), flush=True)
            try:
                self.start()
            except Exception as e:
                print(color.red(f'第{num}个{self.type}处理出错，跳过：{e}'), flush=True)
                continue
            print(color.green(f'第{num}个{self.type}已完成'), flush=True)
            save_record(self.driver, self.course_name, time, iframe, self.type)
    def start(self):
        pass

def turn_page(driver,page_name):
    #获取当前所有窗口的名称
    try:
        current_window_handle = driver.title
        if page_name in current_window_handle:
            return 'True'
    except:
        pass
    # 遍历所有窗口句柄
    for handle in driver.window_handles:
        # 先切换到该窗口
        driver.switch_to.window(handle)
        # 得到该窗口的标题栏字符串，判断是不是我们要操作的那个窗口
        if page_name in driver.title:
            # 如果是，那么这时候WebDriver对象就是对应的该该窗口，正好，跳出循环，
            return True
    return False
def save_record(driver, course_name, time, iframe, typ):
    save_process(course_name)
    if typ!='测验':
        try:
            driver.switch_to.default_content()
            element = driver.find_element(By.CLASS_NAME, 'prev_title')
            title = element.get_attribute('title')
            driver.switch_to.frame(driver.find_element(By.CSS_SELECTOR, '[id="iframe"]'))
            name = json.loads(iframe.get_attribute("data")).get('name',
                    json.loads(iframe.get_attribute("data")).get('title',
                    json.loads(iframe.get_attribute("data")).get('bookname', '')))
            with open(paths.record(f'《{course_name}》的学习记录.txt'), 'a', encoding='utf-8') as f:
                f.write(
                    f'已完成:《{title}》章节中的{typ}:<{name}>，完成时间：{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))}\n\n')
            print(color.green('已保存进度'), flush=True)
        except:
            print(color.red('保存进度失败'), flush=True)
def save_process(course_name,done=0,total=0):
    with open(paths.data('tool', 'course_process.json'), 'r', encoding='utf-8') as f:
        data = json.load(f)
        num_list=data.get(course_name,'')
        if num_list!='' and done==0:
            data[course_name]=[num_list[0]+1,num_list[1]]
        elif total!=0:
            data[course_name]=[done,total]
            print(color.green(f'已保存进度：{done}/{total}'), flush=True)
        with open(paths.data('tool', 'course_process.json'), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

