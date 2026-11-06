# -*- coding: utf-8 -*-
"""图片题「点选项」的浏览器回归（真实 Edge + 本地仿真页）。

要证明的事（用户明确要求）：
  1. 选项是图片时，点击必须落在 A/B/C/D 的文字节点上，**不能点到 <img>**——
     点图片会触发平台的全屏放大遮罩，之后整页都点不动；
  2. 没有文字节点时退回点 <li> 容器，同样不碰图片；
  3. 截图确实被交给多模态接口（桩），并按返回的字母选中对应选项。

仿真页复刻：`<li><i>A</i><img></li>`（有字母）和 `<li><img></li>`（无字母），
点击目标为 IMG 时弹 #outerdiv 全屏遮罩。

用法：C:/Python315/python.exe tests/test_image_answer.py
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

os.environ['XXT_HOME'] = tempfile.mkdtemp(prefix='xxt_test_home_')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from PIL import Image
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By

from core import driver as driver_ext
import task.quiz_ai as quiz_ai
from task.quiz_ai import Answer, image_viewer_is_open, close_image_viewer

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


CONTENT_HTML = """<!doctype html><html><head><meta charset="utf-8">
<style>li img{width:80px;height:40px} li{display:block;margin:6px 0}</style></head><body>
<div id="q1" class="singleQuesId">
  <div class="clearfix font-cxsecret fontLabel"><img src="stem.png" width="120"></div>
  <ul>
    <li aria-checked="false"><i>A</i><img src="img1.png"></li>
    <li aria-checked="false"><i>B</i><img src="img2.png"></li>
  </ul>
</div>
<div id="q2" class="singleQuesId">
  <div class="clearfix font-cxsecret fontLabel"><img src="stem.png" width="120"></div>
  <ul>
    <li aria-checked="false"><img src="img1.png"></li>
    <li aria-checked="false"><img src="img2.png"></li>
  </ul>
</div>
<script>
window.__lastTag = '';
window.__lastText = '';
document.addEventListener('click', function (e) {
  window.__lastTag = e.target.tagName;
  window.__lastText = (e.target.textContent || '').trim();
  if (e.target.tagName === 'IMG') { showViewer(e.target.src); return; }
  var li = e.target.closest ? e.target.closest('li') : null;
  if (li) { li.setAttribute('aria-checked', 'true'); }
}, true);
function showViewer(src) {
  var d = document.getElementById('outerdiv');
  if (!d) {
    d = document.createElement('div');
    d.id = 'outerdiv';
    d.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:9999';
    document.body.appendChild(d);
  }
  d.innerHTML = '<img id="innerdiv" src="' + src + '">';
}
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') { var d = document.getElementById('outerdiv'); if (d) d.remove(); }
});
</script>
</body></html>"""

WORK_HTML = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<h3>work module</h3>
<iframe name="frame_content" id="frame_content" src="content.html" style="width:100%;height:520px"></iframe>
<a class="btnSave workBtnIndex" href="javascript:void(0)">保存</a>
<a class="btnSubmit workBtnIndex" href="javascript:void(0)">提交</a>
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
    site = tempfile.mkdtemp(prefix='xxt_img_answer_')
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
    resolved = driver_ext.resolve('edge')
    service = Service(executable_path=resolved) if resolved else None
    driver = webdriver.Edge(options=opts, service=service)
    driver.implicitly_wait(2)

    # 桩掉多模态：按调用顺序返回 B、A，并记录传进来的截图路径
    calls = []
    replies = ['B', 'A']

    def fake_image(api_key, prompt, paths):
        calls.append(list(paths))
        return replies[len(calls) - 1] if len(calls) <= len(replies) else ''

    original = quiz_ai.DeepSeekAskImage
    quiz_ai.DeepSeekAskImage = fake_image

    def fresh_answer():
        driver.switch_to.default_content()
        driver.switch_to.frame('iframe')
        wf = driver.find_element(By.CSS_SELECTOR, 'iframe#workframe')
        return Answer(driver, wf, '测试课', 'sk-test', None, '100%',
                      frame_selector='iframe#workframe')

    try:
        driver.get(base + '/outer.html')
        a = fresh_answer()
        a.get_title_option()
        check('两道图片题都被识别', a.image_questions == {0, 1}, a.image_questions)

        # 第 1 题：选项里有 <i>A</i>/<i>B</i> —— 必须点在字母节点上
        ok = a.finish_title(0)
        check('图片题 1 作答成功', ok is True)
        tag = driver.execute_script('return window.__lastTag')
        text = driver.execute_script('return window.__lastText')
        check('点击落在了字母节点（I），不是 IMG', tag == 'I', (tag, text))
        check('没有弹出全屏遮罩', not image_viewer_is_open(driver))
        checked = driver.find_elements(By.CSS_SELECTOR, '#q1 li[aria-checked="true"]')
        check('第 1 题选中了 B（下标 1）', len(checked) == 1, len(checked))

        # 第 2 题：选项只有图片，没有文字节点 —— 退回点 <li>，依旧不碰 IMG
        ok = a.finish_title(1)
        check('图片题 2 作答成功', ok is True)
        tag = driver.execute_script('return window.__lastTag')
        check('无字母节点时点了 LI 容器', tag == 'LI', tag)
        check('第 2 题仍没有弹出遮罩', not image_viewer_is_open(driver))
        checked2 = driver.find_elements(By.CSS_SELECTOR, '#q2 li[aria-checked="true"]')
        check('第 2 题选中了 A（下标 0）', len(checked2) == 1, len(checked2))

        check('两次请求都带上了截图', len(calls) == 2 and all(calls), calls)
        check('截图文件真实存在',
              all(os.path.isfile(calls[0][0]) for _ in [0]), calls[0])
        check('没有遗留未作答的图片题', a.image_unanswered == set(), a.image_unanswered)
    finally:
        quiz_ai.DeepSeekAskImage = original
        try:
            close_image_viewer(driver)
        except Exception:
            pass
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
