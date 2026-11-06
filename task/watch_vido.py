# AI生成
# Copyright (c) 2025 Mortal004
# All rights reserved.
# This software is provided for non-commercial use only.
# For more information, see the LICENSE file in the root directory of this project.
import json
from selenium.common import  NoAlertPresentException
import time

from selenium.webdriver.common.by import By
import itertools

from core import paths
from core import browser
from task.tool import color
from task.tool.common import save_record
from task.tool.face import delete_face_popup

drag_progress_condition = True


def click_video_progress_end(driver,pass_vido):
    global drag_progress_condition
    if pass_vido and drag_progress_condition:
        print(color.green('尝试拖动视频进度条'), flush=True)
        driver.execute_script("""
                    var video = document.querySelector('video');
                    if (video) {
                        video.currentTime = video.duration;
                    }
                """)
        drag_progress_condition=False
def generate_combinations_list(input_list):
    """
    返回列表形式的组合，完整组合放在第一位
    """
    n = len(input_list)

    if n == 3:
        # 三者都出现的情况（放在第一位）
        triple = [input_list.copy()]
        # 两两组合的所有可能
        pairs = [list(combo) for combo in itertools.combinations(input_list, 2)]
        return triple + pairs

    elif n == 4:
        # 取四个元素的情况（放在第一位）
        quadruple = [input_list.copy()]
        # 取三个元素的所有可能
        pairs = [list(combo) for combo in itertools.combinations(input_list, 2)]
        triples = [list(combo) for combo in itertools.combinations(input_list, 3)]
        return quadruple + triples + pairs
    else:
        return [input_list]

def check_internet(driver):
    try:
        internet_choice=driver.find_element(By.CSS_SELECTOR,"[class='ans-vjserrdisplay-opts']")
        # print(color.red('网络异常'), flush=True)
        choice_list=internet_choice.find_elements(By.CSS_SELECTOR,"[name='ans-vjserrdisplay-opt']")
        for choice in choice_list:
            choice.click()
    except:
        pass

def check_video_question(driver):
    """视频播放中弹出的题目：一律随机作答，不调用 AI。

    平台对视频题没有错题校验——选错了只会给出提示，接着选下一个就能一路试到正确，
    所以这里用「逐个选项提交」的方式穷举。早期版本会先让 AI 答一次，但提交之后
    随机分支仍会继续跑，反而把 AI 的答案覆盖掉（且视频题答案不可靠），因此 AI 分支已删除。
    """
    try:
        element=driver.find_element(By.CLASS_NAME,'tkTopic')
        print(color.yellow('已检测到视频中有题目'), flush=True)
        try:
            question_type=element.find_element(By.CLASS_NAME,'tkTopic_type').text
        except:
            question_type=element.find_element(By.CLASS_NAME,'tkTopic_title').text
        options = element.find_element(By.CLASS_NAME, 'tkItem_ul')
        options = options.find_elements(By.TAG_NAME, 'li')
        submit = element.find_element(By.ID, 'videoquiz-submit')
        try:
            if question_type=='单选题' or question_type=='判断题':
                for option in options:
                    option.click()
                    #提交
                    submit.click()
                    time.sleep(0.5)
            elif question_type=='多选题':
                answer_lost=generate_combinations_list(options)
                last_ans_set=set()
                for answer in answer_lost:
                    now_ans_set=set(answer)
                    # 使用 ^ 运算符计算对称差集
                    different_elements = now_ans_set ^ last_ans_set
                    for option in different_elements:
                        option.click()
                    last_ans_set=now_ans_set
                    #提交
                    submit.click()
                    time.sleep(0.5)
        except:
            pass
        #继续学习
        try:
            continue_learn=element.find_element(By.ID,'videoquiz-continue')
            continue_learn.click()
        except :
            pass
        try:
            return_video=driver.find_element(By.CSS_SELECTOR, '[class="bntWhiteBorder ans-videoquiz-back fr"]')
            return_video.click()
        except:
            pass
    except:
        return

def check_vido_play(driver, last_time, current_time,speed,pass_face,vido_iframe):
    global b, pause_start_time
    with open(paths.data('tool', 'account_info.json'), 'r', encoding='utf-8') as f:
        account_info = json.load(f)
    if last_time == current_time and current_time != '':
        pause_duration = time.time() - pause_start_time
        b += 1
        if  pause_duration >= 2 and b < 6:
            try:
                print(color.red(f'当前视频播放被暂停,尝试恢复播放'), flush=True)
                # 优先 JS 直接 play()：不依赖按钮 class，最可靠
                driver.execute_script("var v=document.querySelector('video'); if(v&&v.paused){v.play();}")
                # 再点一次播放按钮兜底（选择器放宽为包含匹配，避免 class 拼接变化点不到）
                try:
                    driver.find_element(By.CSS_SELECTOR,
                                        '[class*="vjs-play-control"][class*="vjs-paused"]').click()
                except:
                    pass
            except :
                print(color.red(f'点击失败'), flush=True)
                driver.switch_to.default_content()
                delete_face_popup(driver,pass_face)
                driver.switch_to.frame('iframe')
                driver.switch_to.frame(vido_iframe)
            pause_start_time = time.time()  # 记录第一次检测到暂停的时间
        elif b == 6 and int(speed) >= 2:
            # 尝试多次仍未恢复且倍速>=2：降到 2 倍/1 倍，规避平台倍速检测
            try:
                if int(speed)>2:
                    print(color.red(f'当前视频已被设置不能调节高倍数，现在将倍数调至2倍'), flush=True)
                    new_speed=2
                    account_info['speed'] = '2'
                else:
                    new_speed=1
                    print(color.red(f'当前视频已被设置不能调节高倍数，现在将倍数调至1倍'), flush=True)
                    account_info['speed'] = '1'
                browser.press_key(driver, 'a', times=int(int(speed) - new_speed) * 10, interval=0.1)
                print(color.green('调节成功'), flush=True)
                driver.execute_script("var v=document.querySelector('video'); if(v&&v.paused){v.play();}")
                try:
                    driver.find_element(By.CSS_SELECTOR,
                                        '[class*="vjs-play-control"][class*="vjs-paused"]').click()
                except:
                    print(color.yellow(f'点击播放失败'), flush=True)
            except:
                pass
            with open(paths.data('tool', 'account_info.json'), 'w', encoding='utf-8') as fil:
                json.dump(account_info, fil)
            pause_start_time = time.time()
        elif b >= 8:
            # 持续暂停且多次恢复失败：给足重试窗口（b>=8 约 16 秒以上）仍无法恢复才放弃，
            # 避免网络/平台小波动的暂停直接把整页视频跳过（原来 b==3 就放弃）
            raise Exception('视频播放异常')
    else:
        pause_start_time = 0  # 视频正常播放，重置暂停时间记录
        b=0

def handle_video_error_alert(driver):
    try:
        alert = driver.switch_to.alert
        alert_text = alert.text
        if "视频播放异常" in alert_text:
            print(color.red("检测到视频播放异常弹窗，尝试刷新页面..."))
            alert.accept()
            time.sleep(2)
            driver.refresh()
            # 刷新后需要重新进入 iframe，具体逻辑根据实际情况补充
            raise Exception('视频播放异常')
        else:
            alert.accept()
            raise Exception('视频播放异常')
    except NoAlertPresentException:
        return

def check_vido_finish(driver,i,time_start,total_time,vido_iframe,lock_screen,speed,pass_face):
    last_time = 0
    h = 0
    # 判断是否完成任务
    while True:
        time.sleep(1)
        # 每次切换前先处理可能存在的弹窗
        # handle_video_error_alert(driver)
        driver.switch_to.default_content()
        driver.switch_to.frame('iframe')
        elements2 = driver.find_elements(By.CLASS_NAME, 'ans-job-icon-clear ')
        element2 = elements2[i]
        # 定位到该元素的上一级（父元素）
        parent_element2 = element2.find_element(By.XPATH, "..")
        # 获取 parent_element2 的class值
        parent_element2_class = parent_element2.get_attribute("class")
        txt = element2.get_attribute('aria-label')
        # print(parent_element2_class, flush=True)
        if txt == '任务点已完成' or 'ans-attach-ct ans-job-finished' in parent_element2_class:
            # pyautogui.scroll(-250)
            print(color.green(f'已完成第{i + 1}个视频'), flush=True)
            time_end = time.time()
            print(color.green('总共耗费了%.2f秒.' % (time_end - time_start)), flush=True)
            break
        else:
            driver.switch_to.default_content()
            driver.switch_to.frame('iframe')
            driver.switch_to.frame(vido_iframe)
            check_internet(driver)
            check_video_question(driver)
            element = driver.find_element(By.CLASS_NAME, 'vjs-current-time-display')
            current_time = element.text
            check_vido_play(driver, last_time, current_time,speed,pass_face,vido_iframe)
            last_time = current_time
            if current_time == total_time:
                if h == 0:
                    h += 1
                    try:
                        print(color.yellow('视频已播放完毕，但任务点仍未完成，开始重播'), flush=True)
                        driver.find_element(By.CSS_SELECTOR,
                                            '[class="vjs-play-control vjs-control vjs-button vjs-paused vjs-ended"]').click()
                    except:
                        print(color.red(f'点击失败'), flush=True)
                else:
                    print(color.green(f'已完成第{i + 1}个视频'), flush=True)
                    time_end = time.time()
                    print(color.green('总共耗费了%.2f秒.' % (time_end - time_start)), flush=True)
                    break
            if lock_screen:
                # 用系统 API 阻止休眠，不再抖鼠标（多账号并发时抖鼠标会干扰用户）
                browser.keep_awake()
    return True

def study_page(driver,course_name,lock_screen,pass_vido,speed,pass_face):
    global drag_progress_condition
    driver.switch_to.default_content()
    driver.switch_to.frame('iframe')
    try:
        # 判断是否完成任务
        elements1 = driver.find_elements(By.CLASS_NAME, 'ans-job-icon-clear ')
        print(color.magenta(f'已检测到{len(elements1)}个视频包含有任务点'),flush=True)
    except:
        browser.scroll_page(driver, 250)
        print(color.green('视频已完成,点击下一节'),flush=True)
        return

    for i in range(len(elements1)):
        drag_progress_condition = True
        element1=elements1[i]
        # 定位到该元素的上一级（父元素）
        parent_element = element1.find_element(By.XPATH, "..")
        try:
            # 获取 parent_element 的class值
            parent_element_class=parent_element.get_attribute("class")
            txt = element1.get_attribute('aria-label')
        except:
            txt = ''
            parent_element_class=''
        if txt == '任务点未完成' and 'ans-attach-ct' in parent_element_class:
            vido_iframe=element1.find_element(By.XPATH, "following-sibling::iframe[1]")
            driver.execute_script("arguments[0].scrollIntoView();", vido_iframe)
            driver.switch_to.frame(vido_iframe)
            print(color.green(f'开始播放第{i + 1}个视频'),flush=True)
            time_start=time.time()
            try:
                driver.find_element(By.CLASS_NAME,'vjs-big-play-button').click()
            except:
                pass
            #点击我知道了
            driver.switch_to.default_content()
            delete_face_popup(driver,pass_face)
            driver.switch_to.frame('iframe')
            driver.switch_to.frame(vido_iframe)

            try:
                element=driver.find_element(By.CLASS_NAME,'writeNote_vid_blue')
                element.click()
            except:
                pass
            try:
                print(color.blue('调节音量'), flush=True)
                element = driver.find_element(By.XPATH, '//*[@id="video"]/div[6]/div[6]')
                element.click()
                print(color.green('调节成功'), flush=True)
            except:
                print(color.yellow('未找到音量，或已经调节'), flush=True)

            time.sleep(1)
            element=driver.find_element(By.CLASS_NAME,'vjs-duration-display')
            total_time=element.text
            if  total_time=='' or total_time=='0:00':
                print(color.red('获取视频总时长失败'),flush=True)
                total_time='1'
            else:
                print(color.green(f'该视频总时长为：{total_time}'),flush=True)
            click_video_progress_end(driver,pass_vido)
            print(color.yellow('请不要将窗口最小化，这有可能导致程序异常\n视频播放完毕会自动跳转\n正在观看视频中……'),flush=True)
            driver.switch_to.default_content()
            driver.switch_to.frame('iframe')
            b = 0
            pause_start_time = 0  # 添加变量记录暂停开始时间
            check_vido_finish(driver,i,time_start,total_time,vido_iframe,lock_screen,speed,pass_face)
            save_record(driver, course_name, time, vido_iframe, '视频')
        driver.switch_to.default_content()
        # check_face(driver,driver.current_url,'popDiv1 wid640  faceCollectQrPopVideo  popClass faceRecognition_0')
        driver.switch_to.frame('iframe')
    print(color.green('所有视频均已完成'),flush=True)
    return
