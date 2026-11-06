# AI生成
# -*- coding: utf-8 -*-
"""图片题 / 元素失效 / 全屏遮罩 的回归测试。

用真实 Edge 驱动一个仿真页：
    outer.html -> iframe#iframe(study.html) -> iframe#workframe(work.html) -> iframe#frame_content(content.html)

仿真页复刻了两件真实环境里会踩的事：
    1. 选项里是 <img>，原生点击落在图片上会弹出「全屏看图」遮罩（#outerdiv）；
    2. 答题期间页面重渲染（iframe reload），之前抓到的 WebElement 全部失效。

用法：C:/Python315/python.exe tests/test_quiz_image.py
"""
import os
import sys
import tempfile
import threading
import http.server
import socketserver

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

# 数据目录指到临时目录，避免污染工程里的 task/record
HOME = tempfile.mkdtemp(prefix='xxt_test_home_')
os.environ['XXT_HOME'] = HOME
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from PIL import Image
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By

from core import driver as driver_ext
from task.quiz_ai import Answer, image_viewer_is_open, close_image_viewer
import task.quiz_ai as quiz_ai_mod

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


CONTENT_HTML = """<!doctype html><html><head><meta charset="utf-8">
<style>li img{width:70px;height:40px}</style></head><body>
<div id="q1" class="singleQuesId">
  <div class="clearfix font-cxsecret fontLabel">【单选题】1+1=?</div>
  <ul><li aria-checked="false">A.1</li><li aria-checked="false">B.2</li><li aria-checked="false">C.3</li></ul>
</div>
<div id="q2" class="singleQuesId">
  <div class="clearfix font-cxsecret fontLabel">【单选题】看图选择</div>
  <ul><li aria-checked="false"><img src="img1.png"></li><li aria-checked="false"><img src="img2.png"></li></ul>
</div>
<div id="q3" class="singleQuesId">
  <div class="clearfix font-cxsecret fontLabel"><img src="stem.png" width="120"></div>
  <ul><li aria-checked="false">A.对</li><li aria-checked="false">B.错</li></ul>
</div>
<div id="q4" class="singleQuesId">
  <div class="clearfix font-cxsecret fontLabel">【多选题】选择全部</div>
  <ul><li aria-checked="false">A.甲</li><li aria-checked="false">B.乙</li><li aria-checked="false">C.丙</li></ul>
</div>
<script>
document.addEventListener('click', function(e){
  if (e.target.tagName === 'IMG') { showViewer(e.target.src); return; }
  var li = e.target.closest ? e.target.closest('li') : null;
  if (li) { li.setAttribute('aria-checked','true'); }
}, true);
function showViewer(src){
  var d = document.getElementById('outerdiv');
  if (!d) { d = document.createElement('div'); d.id = 'outerdiv';
    d.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:9999';
    document.body.appendChild(d); }
  d.innerHTML = '<img id="innerdiv" src="' + src + '" style="position:absolute;left:50%;top:50%;'
              + 'transform:translate(-50%,-50%);max-width:90%">';
}
document.addEventListener('keydown', function(e){
  if (e.key === 'Escape') { var d = document.getElementById('outerdiv'); if (d) d.remove(); }
});
</script>
</body></html>"""

WORK_HTML = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<h3>work module</h3>
<iframe name="frame_content" id="frame_content" src="content.html" style="width:100%;height:520px"></iframe>
<div>
  <a class="btnSave workBtnIndex" href="javascript:void(0)"
     onclick="window.__saveClicked=(window.__saveClicked||0)+1">保存</a>
  <a class="btnSubmit workBtnIndex" href="javascript:void(0)"
     onclick="window.__submitClicked=(window.__submitClicked||0)+1">提交</a>
</div>
</body></html>"""

STUDY_HTML = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<h3>学生学习页面</h3>
<div class="prev_title" title="第一章 测试">第一章 测试</div>
<iframe id="workframe" src="work.html" style="width:100%;height:640px"></iframe>
</body></html>"""

OUTER_HTML = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<iframe id="iframe" src="study.html" style="width:100%;height:760px"></iframe>
</body></html>"""


def make_site():
    site = tempfile.mkdtemp(prefix='xxt_mock_')
    for name, html in (('content.html', CONTENT_HTML), ('work.html', WORK_HTML),
                       ('study.html', STUDY_HTML), ('outer.html', OUTER_HTML)):
        with open(os.path.join(site, name), 'w', encoding='utf-8') as f:
            f.write(html)
    for name in ('img1.png', 'img2.png', 'stem.png'):
        Image.new('RGB', (240, 140), (60, 120, 200)).save(os.path.join(site, name))
    return site


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    site = make_site()
    handler = lambda *a, **kw: Quiet(*a, directory=site, **kw)
    httpd = socketserver.TCPServer(('127.0.0.1', 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = 'http://127.0.0.1:%d' % port

    opts = Options()
    opts.add_argument('--headless=new')
    opts.add_argument('--window-size=1200,900')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--no-first-run')
    # 走工程自己的离线驱动解析（配置→drivers/→Selenium 缓存），
    # 不依赖 Selenium Manager 联网，避免 NoSuchDriverException 卡住回归
    service = None
    driver_path = driver_ext.resolve('edge')
    if driver_path:
        service = Service(executable_path=driver_path)
    driver = webdriver.Edge(options=opts, service=service)
    driver.implicitly_wait(2)

    # 本用例不联网：图片题会先尝试多模态，这里统一桩成「答不出」，
    # 验证答不出来时的兜底（跳过 + 不误点）。多模态正常路径另有 test_image_answer.py。
    original_image_ask = quiz_ai_mod.DeepSeekAskImage
    quiz_ai_mod.DeepSeekAskImage = lambda *args, **kwargs: ''

    def reload_page():
        driver.get(base + '/outer.html')

    def fresh_answer():
        driver.switch_to.default_content()
        driver.switch_to.frame('iframe')
        wf = driver.find_element(By.CSS_SELECTOR, 'iframe#workframe')
        return Answer(driver, wf, '测试课', 'sk-test', None, '100%',
                      frame_selector='iframe#workframe')

    try:
        reload_page()
        a = fresh_answer()

        # 1) 题目解析：图片选项 / 图片题干 都要识别出来，且四个结构等长
        a.get_title_option()
        check('题目数量 = 4', len(a.questionList0) == 4, len(a.questionList0))
        check('图片题识别 = {1,2}', a.image_questions == {1, 2}, a.image_questions)
        check('四个结构等长',
              len(a.questionType_list) == len(a.only_title_text) == len(a.all_title_dit) == 4,
              (len(a.questionType_list), len(a.only_title_text), len(a.all_title_dit)))
        check('第1题是单选题', a.questionType_list[0] == '单选题', a.questionType_list[0])

        # 2) 对照组：原生点击图片确实会弹出全屏遮罩（说明仿真页有效）
        a._enter_context()
        img = driver.find_element(By.CSS_SELECTOR, '#q2 li img')
        img.click()
        check('原生点图会弹出全屏遮罩', image_viewer_is_open(driver))
        check('遮罩能被关掉', close_image_viewer(driver) >= 0 and not image_viewer_is_open(driver))

        # 3) 图片选项必须用 JS 点 <li>，不能再触发遮罩
        a._enter_context()
        ok = a._click_option(1, 0)
        check('图片选项点击成功', ok)
        check('JS 点击不会弹遮罩', not image_viewer_is_open(driver))
        checked = driver.find_element(By.CSS_SELECTOR, '#q2 li[aria-checked="true"]')
        check('选项已被选中', checked is not None)

        # 4) 页面重渲染后元素失效：仍要能重新定位并作答
        #    从 default -> iframe 后在 study 页里 reload 模块 iframe，
        #    这样 self.frame 与 frame_content 里的元素句柄全部作废。
        driver.switch_to.default_content()
        driver.switch_to.frame('iframe')
        driver.execute_script(
            "var f=document.getElementById('workframe'); f.src=f.src;")  # 触发整个模块 reload
        import time
        time.sleep(2)
        a.num_answer_dit[0] = ['B.2']
        ok = a.finish_title(0)
        check('重渲染后仍能作答第1题', ok)
        a._enter_context()
        q1_checked = driver.find_elements(By.CSS_SELECTOR, '#q1 li[aria-checked="true"]')
        check('重渲染后选项确实被选中', len(q1_checked) == 1, len(q1_checked))

        # 5) 保存/提交按钮在父帧（模块页），从 frame_content 里也要能找到并点中
        a._enter_context()
        ok = a._work_button('[class="btnSave workBtnIndex"]')
        check('跨帧找到保存按钮', ok)
        clicked = driver.execute_script("return window.__saveClicked || 0")
        check('保存按钮真的被点了', clicked == 1, clicked)

        # 6) 多模态不可用（这里把接口桩成空返回）时，图片题仍应跳过、不产生点击
        #    注：图片题现在会先尝试多模态，若模型答不出才跳过；本用例验证「答不出」的兜底。
        a._enter_context()
        before = driver.execute_script("return document.querySelectorAll('[aria-checked=\"true\"]').length")
        ok = a.finish_title(1)
        check('图片题返回 False（跳过）', ok is False)
        a._enter_context()
        after = driver.execute_script("return document.querySelectorAll('[aria-checked=\"true\"]').length")
        check('图片题没有误点选项', before == after, (before, after))

        # 7) 坐标点击被遮罩兼容处理时：要能收掉遮罩、重定位、再点成功
        reload_page()
        a = fresh_answer()
        a.get_title_option()
        a._enter_context()
        driver.execute_script("document.querySelector('#q2 li img').click();")  # 手动制造遮罩
        check('遮罩已出现', image_viewer_is_open(driver))
        ok = a._click_option(0, 2)          # 此时原生点击会被遮罩兼容处理
        check('遮罩下仍能点中选项', ok)
        check('遮罩已被收掉', not image_viewer_is_open(driver))
        a._enter_context()
        q1_checked = driver.find_elements(By.CSS_SELECTOR, '#q1 li[aria-checked="true"]')
        check('遮罩下选项被选中', len(q1_checked) == 1, len(q1_checked))

        # 8) 误点图片链接把内容帧导航成图片后，要能退回来继续答题
        reload_page()
        a = fresh_answer()
        a.get_title_option()
        a._enter_context()
        driver.execute_script("location.href='img1.png';")
        time.sleep(1)
        check('内容帧已变成图片', driver.execute_script("return /[.](png|jpg)$/i.test(location.href)"))
        a._recover_image_navigation()
        check('已退出图片页', not driver.execute_script("return /[.](png|jpg)$/i.test(location.href)"))
        check('退回后还能进答题上下文', a._enter_context())

        # 9) 整场测验走一遍：图片题跳过、正常题作答、自动保存
        reload_page()
        import task.quiz_ai as quiz_mod
        orig = quiz_mod.DeepSeekAsk
        quiz_mod.DeepSeekAsk = lambda api, title, typ: 'B/A,B'
        try:
            a = Answer(driver, None, '测试课', 'sk-open_deepseek', '自动答题', '100%',
                       frame_selector='iframe#workframe')
        finally:
            quiz_mod.DeepSeekAsk = orig
        check('整场答题率 = 2/4', a.reword_time == 2, (a.reword_time, len(a.questionList0)))
        a._enter_context()
        q1 = driver.find_elements(By.CSS_SELECTOR, '#q1 li[aria-checked="true"]')
        q4 = driver.find_elements(By.CSS_SELECTOR, '#q4 li[aria-checked="true"]')
        q2 = driver.find_elements(By.CSS_SELECTOR, '#q2 li[aria-checked="true"]')
        check('第1题已作答', len(q1) == 1, len(q1))
        check('第4题多选已作答', len(q4) == 2, len(q4))
        check('第2题图片题未作答', len(q2) == 0, len(q2))
        a._enter_context()
        driver.switch_to.parent_frame()
        saved = driver.execute_script("return window.__saveClicked || 0")
        check('整场结束后自动保存', saved == 1, saved)
        check('整场结束后没有残留遮罩', not image_viewer_is_open(driver))
    finally:
        quiz_ai_mod.DeepSeekAskImage = original_image_ask
        driver.quit()
        httpd.shutdown()

    print('---')
    if FAILS:
        print('FAILED: %d' % len(FAILS), FAILS)
        return 1
    print('ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
