# -*- coding: utf-8 -*-
"""浏览器驱动解析：先找本机已有的驱动，实在没有才联网下载。

单文件 exe 在**新电脑**上第一次运行时，Selenium Manager 需要联网下载
msedgedriver / chromedriver；国内网络、代理缺失、或 Edge 刚更新还没发
对应驱动时，就会报：

    NoSuchDriverException: Unable to obtain driver for MicrosoftEdge

这里按 配置路径 → 程序目录 drivers/ → 数据目录 drivers/ → Selenium 缓存
→ 官方 CDN 下载 的顺序兜底；仍然失败时给出能照着做的提示，而不是一句
看不懂的英文异常。
"""
from __future__ import annotations

import glob
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile

import requests

from core import paths

DRIVER_NAMES = {'edge': 'msedgedriver', 'chrome': 'chromedriver'}
BROWSER_LABELS = {'edge': 'Microsoft Edge', 'chrome': 'Google Chrome'}

# Edge 驱动的官方下载源（国内一般可达，azureedge 作为备用）
EDGE_URLS = (
    'https://msedgedriver.microsoft.com/{version}/edgedriver_{tag}.zip',
    'https://msedgedriver.azureedge.net/{version}/edgedriver_{tag}.zip',
)
CHROME_TESTING_JSON = ('https://googlechromelabs.github.io/chrome-for-testing/'
                       'last-known-good-versions.json')
CHROME_URL = ('https://storage.googleapis.com/chrome-for-testing-public/'
              '{version}/{tag}/chromedriver-{tag}.zip')


def _is_windows() -> bool:
    return os.name == 'nt'


def platform_tag() -> str:
    """Selenium 缓存 / 官方包使用的平台标签。"""
    if _is_windows():
        return 'win32' if platform.architecture()[0] == '32bit' else 'win64'
    if sys.platform == 'darwin':
        return 'mac-x64' if platform.machine().lower() in ('x86_64', 'amd64') else 'mac-arm64'
    return 'linux64' if platform.machine().lower() in ('x86_64', 'amd64') else 'linux-arm64'


def _exe(name: str) -> str:
    return name + ('.exe' if _is_windows() else '')


# ---------------------------------------------------------------------------
# 本机浏览器版本
# ---------------------------------------------------------------------------
def _reg_value(root, subkey, name):
    try:
        import winreg
        with winreg.OpenKey(root, subkey) as key:
            return str(winreg.QueryValueEx(key, name)[0])
    except Exception:
        return None


def _windows_version(browser: str):
    try:
        import winreg
    except Exception:
        return None
    if browser == 'chrome':
        roots = ((winreg.HKEY_CURRENT_USER, 'Software\\Google\\Chrome\\BLBeacon'),
                 (winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\WOW6432Node\\Google\\Chrome\\BLBeacon'),
                 (winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Google\\Chrome\\BLBeacon'))
        # Google 更新器里也记着版本号
        update_roots = ((winreg.HKEY_LOCAL_MACHINE,
                         'SOFTWARE\\WOW6432Node\\Google\\Update\\Clients\\'
                         '{8A69D345-D564-463c-AFF1-A69D9E530F96}'),)
    else:
        roots = ((winreg.HKEY_CURRENT_USER, 'Software\\Microsoft\\Edge\\BLBeacon'),
                 (winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\WOW6432Node\\Microsoft\\Edge\\BLBeacon'),
                 (winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Microsoft\\Edge\\BLBeacon'))
        # EdgeUpdate 的客户端键（BLBeacon 缺失时用）
        update_roots = ((winreg.HKEY_LOCAL_MACHINE,
                         'SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate\\Clients\\'
                         '{56EB18F8-B008-4CBD-B6D2-8C97FE7E9062}'),
                        (winreg.HKEY_LOCAL_MACHINE,
                         'SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\'
                         '{56EB18F8-B008-4CBD-B6D2-8C97FE7E9062}'))
    for root, subkey in roots:
        version = _reg_value(root, subkey, 'version')
        if version:
            return version
    for root, subkey in update_roots:
        version = _reg_value(root, subkey, 'pv')
        if version:
            return version
    return None


def _unix_version(browser: str):
    candidates = (['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser']
                  if browser == 'chrome'
                  else ['microsoft-edge', 'microsoft-edge-stable', 'msedge'])
    for binary in candidates:
        exe = shutil.which(binary)
        if not exe:
            continue
        try:
            out = subprocess.run([exe, '--version'], capture_output=True,
                                 text=True, timeout=8).stdout
        except Exception:
            continue
        for token in reversed((out or '').strip().split()):
            if token[:1].isdigit() and '.' in token:
                return token
    return None


def browser_version(browser: str):
    """返回本机浏览器版本（如 156.0.4314.42），拿不到返回 None。"""
    browser = 'chrome' if str(browser).lower() == 'chrome' else 'edge'
    return _windows_version(browser) if _is_windows() else _unix_version(browser)


# ---------------------------------------------------------------------------
# 候选驱动
# ---------------------------------------------------------------------------
def cache_root() -> str:
    """Selenium Manager 的缓存目录（与 selenium 保持一致）。"""
    return (os.environ.get('SE_CACHE_PATH')
            or os.path.join(os.path.expanduser('~'), '.cache', 'selenium'))


def cache_candidates(browser: str):
    name = DRIVER_NAMES[browser]
    pattern = os.path.join(cache_root(), name, platform_tag(), '*', _exe(name))
    return sorted(glob.glob(pattern))


def local_candidates(browser: str):
    """程序目录/data 目录下的 drivers/（解压一份就能离线用）。"""
    name = _exe(DRIVER_NAMES[browser])
    found = []
    for base in (os.path.join(paths.app_root(), 'drivers'),
                 os.path.join(paths.DATA_ROOT, 'drivers')):
        found += sorted(glob.glob(os.path.join(base, '**', name), recursive=True))
    return found


def _version_from_path(driver_path: str):
    parts = driver_path.replace('\\', '/').split('/')
    for part in reversed(parts[:-1]):
        if part[:1].isdigit() and '.' in part:
            return part
    return None


def driver_version(driver_path: str):
    """驱动自己的版本：先看路径里的版本目录，再问驱动本身。"""
    version = _version_from_path(driver_path)
    if version:
        return version
    try:
        out = subprocess.run([driver_path, '--version'], capture_output=True,
                             text=True, timeout=8).stdout
    except Exception:
        return None
    for token in reversed((out or '').strip().split()):
        if token[:1].isdigit() and '.' in token:
            return token.strip('vV')
    return None


def _major(version) -> str:
    return str(version or '').split('.')[0]


def pick(candidates, version):
    """挑出与本机浏览器大版本一致的驱动；版本对不上宁可不返回。"""
    if not candidates:
        return None
    if not version:
        return candidates[0] if len(candidates) == 1 else None
    for candidate in candidates:
        if _major(driver_version(candidate)) == _major(version):
            return candidate
    return None


def resolve(browser: str, configured: str = ''):
    """离线解析驱动：配置路径 → 本地 drivers/ → Selenium 缓存。找不到返回 None。"""
    browser = 'chrome' if str(browser).lower() == 'chrome' else 'edge'
    configured = (configured or '').strip().strip('"')
    if configured and os.path.isfile(configured):
        return configured
    version = browser_version(browser)
    return pick(local_candidates(browser) + cache_candidates(browser), version)


# ---------------------------------------------------------------------------
# 联网下载
# ---------------------------------------------------------------------------
def _download_bytes(url: str) -> bytes:
    response = requests.get(url, timeout=90, allow_redirects=True)
    response.raise_for_status()
    return response.content


def _extract_driver(blob: bytes, driver_name: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        archive = os.path.join(tmp, 'driver.zip')
        with open(archive, 'wb') as f:
            f.write(blob)
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                if member.replace('\\', '/').endswith(driver_name):
                    return zf.read(member)
    raise RuntimeError('下载包里没有找到 %s' % driver_name)


def download(browser: str):
    """按本机浏览器版本下载官方驱动，返回 exe 路径。"""
    browser = 'chrome' if str(browser).lower() == 'chrome' else 'edge'
    version = browser_version(browser)
    if not version:
        raise RuntimeError('检测不到本机 %s 版本' % BROWSER_LABELS[browser])
    tag = platform_tag()
    name = _exe(DRIVER_NAMES[browser])

    urls = []
    if browser == 'edge':
        urls = [template.format(version=version, tag=tag) for template in EDGE_URLS]
    else:
        full = version
        if full.count('.') < 3:
            try:
                import json
                data = json.loads(_download_bytes(CHROME_TESTING_JSON).decode('utf-8'))
                full = data['channels']['Stable']['version']
            except Exception:
                pass
        urls = [CHROME_URL.format(version=full, tag='win64' if tag in ('win64', 'win32')
                                  else ('mac-x64' if tag == 'mac-x64' else
                                        ('mac-arm64' if tag == 'mac-arm64' else tag)))]

    last_error = None
    for url in urls:
        try:
            print('正在下载浏览器驱动: %s' % url, flush=True)
            blob = _download_bytes(url)
            payload = _extract_driver(blob, name)
            target_dir = os.path.join(paths.DATA_ROOT, 'drivers', browser, version)
            os.makedirs(target_dir, exist_ok=True)
            target = os.path.join(target_dir, name)
            with open(target, 'wb') as f:
                f.write(payload)
            if not _is_windows():
                os.chmod(target, 0o755)
            print('驱动已保存: %s' % target, flush=True)
            return target
        except Exception as e:
            last_error = e
            continue
    raise RuntimeError('下载 %s %s 驱动失败: %s' % (BROWSER_LABELS[browser], version, last_error))


def human_error(browser: str, reason=None) -> str:
    """给用户看的、能照做的错误说明。"""
    browser = 'chrome' if str(browser).lower() == 'chrome' else 'edge'
    label = BROWSER_LABELS[browser]
    version = browser_version(browser) or '未知'
    driver = _exe(DRIVER_NAMES[browser])
    drivers_dir = os.path.join(paths.DATA_ROOT, 'drivers')
    lines = [
        '无法获取 %s 驱动（本机浏览器版本: %s）。' % (label, version),
        '已按顺序尝试：设置里的驱动地址 → 程序目录 drivers/ → 数据目录 drivers/ '
        '→ Selenium 缓存 → 官方 CDN 下载。',
    ]
    if reason:
        lines.append('最后一次错误: %s' % reason)
    lines += [
        '可以这样解决：',
        '  1) 联网后重试（程序会自动下载匹配版本）；',
        '  2) 手动下载 %s（要 %s 对应版本），放到：%s' % (driver, version, drivers_dir),
        '     或 exe 同目录的 drivers\\ 文件夹，程序启动会自动识别；',
        '  3) 在「设置 → 驱动地址」里直接选中驱动 exe；',
        '  4) 换用另一个浏览器（设置里切到 chrome / edge）。',
        '驱动下载页: https://developer.microsoft.com/microsoft-edge/tools/webdriver/'
        if browser == 'edge' else
        '驱动下载页: https://googlechromelabs.github.io/chrome-for-testing/',
        '详细说明见 输出记录.log。',
    ]
    return '\n'.join(lines)
