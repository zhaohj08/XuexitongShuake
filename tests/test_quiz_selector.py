# -*- coding: utf-8 -*-
"""测验页 iframe 选择器的回归测试（真实 Edge + 本地仿真页）。

背景：平台前端发版会把测验 iframe 的 `?v=2025-1028-1629` 换成新构建号。
旧代码把整条 src 精确匹配（`[src="/ananas/modules/work/index.html?v=2025-1028-1629&castscreen=0"]`），
平台一升级就认不出测验页 → 日志「该页面无法识别」→ 跳过 → 整章测验静默漏做。

断言：
  1. 同一个 iframe（换了构建号）用新选择器能命中；
  2. 用旧的精确选择器命中不了（证明确实是这个改动救了它）；
  3. main.py 里的测验识别与 quiz_ai.Quiz.IFRAME_SELECTOR 用的是同一个前缀选择器。

用法：C:/Python315/python.exe tests/test_quiz_selector.py
"""
import http.server
import os
import socketserver
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

os.environ['XXT_HOME'] = tempfile.mkdtemp(prefix='xxt_test_home_')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service

from core import driver as driver_ext
from task.quiz_ai import Quiz

FAILS = []

# 模拟「平台升级后」的构建号
FUTURE_SRC = '/ananas/modules/work/index.html?v=2099-01-01-0000&castscreen=0'
OLD_SELECTOR = '[src="/ananas/modules/work/index.html?v=2025-1028-1629&castscreen=0"]'

PAGE_HTML = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<h3>学生学习页面</h3>
<iframe id="iframe" src="study.html" style="width:100%;height:600px"></iframe>
</body></html>"""

STUDY_HTML = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<iframe class="work" src="%s" style="width:100%%;height:500px"></iframe>
</body></html>""" % FUTURE_SRC


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def make_site():
    site = tempfile.mkdtemp(prefix='xxt_selector_')
    for name, html in (('page.html', PAGE_HTML), ('study.html', STUDY_HTML)):
        with open(os.path.join(site, name), 'w', encoding='utf-8') as f:
            f.write(html)
    # 让 iframe 的 src 也能返回 200，避免控制台噪音（查询串会被忽略）
    work_dir = os.path.join(site, 'ananas', 'modules', 'work')
    os.makedirs(work_dir, exist_ok=True)
    with open(os.path.join(work_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write('<!doctype html><html><body>work module</body></html>')
    return site


def main():
    site = make_site()
    handler = lambda *a, **kw: Quiet(*a, directory=site, **kw)
    httpd = socketserver.TCPServer(('127.0.0.1', 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    opts = Options()
    opts.add_argument('--headless=new')
    opts.add_argument('--window-size=1000,800')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--no-first-run')
    resolved = driver_ext.resolve('edge')
    service = Service(executable_path=resolved) if resolved else None
    driver = webdriver.Edge(options=opts, service=service)
    driver.implicitly_wait(2)
    try:
        driver.get('http://127.0.0.1:%d/page.html' % port)
        driver.switch_to.frame('iframe')      # 进到学生学习页，测验 iframe 在这一层

        new_hits = driver.find_elements(By.CSS_SELECTOR, Quiz.IFRAME_SELECTOR)
        old_hits = driver.find_elements(By.CSS_SELECTOR, OLD_SELECTOR)
        check('新选择器命中未来的构建号', len(new_hits) == 1, len(new_hits))
        check('旧精确选择器命中不了（证明原写法确实会漏）', len(old_hits) == 0, len(old_hits))
        check('新选择器是 src 包含匹配（兼容绝对 URL）',
              'src*=' in Quiz.IFRAME_SELECTOR and 'src^=' not in Quiz.IFRAME_SELECTOR,
              Quiz.IFRAME_SELECTOR)

        with open(os.path.join(ROOT, 'main.py'), 'r', encoding='utf-8') as f:
            main_src = f.read()
        check('main.py 的测验识别使用同一选择器',
              Quiz.IFRAME_SELECTOR.replace('iframe', '') in main_src or
              Quiz.IFRAME_SELECTOR in main_src, Quiz.IFRAME_SELECTOR)
        check('main.py 已无旧构建号的精确匹配',
              'v=2025-1028-1629&castscreen=0' not in main_src)
    finally:
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
