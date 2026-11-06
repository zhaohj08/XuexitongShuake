"""浏览器层小工具：不依赖窗口焦点的按键、防锁屏。

多账号并发时，pyautogui 的按键会发到「当前前台窗口」，
两个浏览器同时跑就会给 A 调倍速却打到 B 身上。
这里改用 CDP 直接给指定标签页发键事件，天然隔离。
"""
from __future__ import annotations


VK = {
    'a': 65, 'b': 66, 'c': 67, 'd': 68, 'm': 77, 'z': 90,
}

# 非字母键的 CDP 虚拟键码
VK_EXTRA = {
    'escape': 27, 'enter': 13, 'space': 32,
}

CTRL = 2


def _send_key(driver, key, vk, code=None, modifiers=0):
    """通过 CDP 向该标签页发一次完整按键。"""
    payload = {
        "key": key,
        "windowsVirtualKeyCode": vk,
        "nativeVirtualKeyCode": vk,
    }
    if code:
        payload["code"] = code
    if modifiers:
        payload["modifiers"] = modifiers
    driver.execute_cdp_cmd("Input.dispatchKeyEvent", dict(payload, type="keyDown"))
    driver.execute_cdp_cmd("Input.dispatchKeyEvent", dict(payload, type="keyUp"))


def press_escape(driver) -> bool:
    """给指定标签页发 Esc。

    学习平台的题目图片点开后会盖一层全屏预览，这层遮罩会把后续所有点击吃掉，
    表现就是「图片全屏显示 + 程序不动了」。Esc 是这类遮罩最通用的关闭方式。
    """
    try:
        _send_key(driver, 'Escape', VK_EXTRA['escape'], code='Escape')
        return True
    except Exception:
        try:
            from selenium.webdriver.common.keys import Keys
            driver.find_element('tag name', 'body').send_keys(Keys.ESCAPE)
            return True
        except Exception:
            return False


def press_key(driver, key: str, times: int = 1, interval: float = 0.05) -> int:
    """向 driver 当前标签页发送按键，返回成功发送的次数。

    走 CDP Input.dispatchKeyEvent，不受窗口焦点影响；
    CDP 不可用时回退到 ActionChains（同样只作用于该 driver 的页面）。
    """
    vk = VK.get(key.lower(), ord(key.upper()))
    sent = 0
    for _ in range(max(1, times)):
        ok = False
        try:
            driver.execute_cdp_cmd("Input.dispatchKeyEvent", {
                "type": "keyDown", "key": key, "text": key,
                "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk})
            driver.execute_cdp_cmd("Input.dispatchKeyEvent", {
                "type": "keyUp", "key": key,
                "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk})
            ok = True
        except Exception:
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                ActionChains(driver).send_keys(key).perform()
                ok = True
            except Exception:
                ok = False
        if ok:
            sent += 1
        if interval:
            import time
            time.sleep(interval)
    return sent


def press_combo(driver, key: str, modifiers: int = CTRL) -> bool:
    """发送带修饰键的组合键（modifiers: Alt=1 Ctrl=2 Meta=4 Shift=8）。"""
    vk = VK.get(key.lower(), ord(key.upper()))
    try:
        driver.execute_cdp_cmd("Input.dispatchKeyEvent", {
            "type": "keyDown", "key": key, "modifiers": modifiers,
            "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk})
        driver.execute_cdp_cmd("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": key, "modifiers": modifiers,
            "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk})
        return True
    except Exception:
        return False


def keep_awake() -> bool:
    """阻止系统休眠/锁屏，不移动鼠标。

    用 SetThreadExecutionState 代替 pyautogui.move 抖动鼠标：
    多账号并发时抖鼠标会干扰用户正常操作，而且只能作用于前台窗口。
    """
    try:
        import ctypes
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ES_DISPLAY_REQUIRED = 0x00000002
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
        return True
    except Exception:
        return False


def scroll_page(driver, delta: int) -> None:
    """页面内滚动，替代 pyautogui.scroll。"""
    try:
        driver.execute_script("window.scrollBy(0, arguments[0]);", delta)
    except Exception:
        pass
