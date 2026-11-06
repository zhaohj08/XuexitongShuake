
"""
学习平台多端学习状态兼容
原理：
1. 兼容处理 Element.prototype.appendChild，兼容处理 detect.chaoxing.com 检测代码注入
2. 覆盖 window.confirm，自动关闭多端登录提示弹窗
"""

import time
from selenium.webdriver.remote.webdriver import WebDriver

class PageCompat:
    """多端学习状态兼容"""

    def __init__(self, driver: WebDriver):
        self.driver = driver
        self._enabled = False
        self._confirm_interval_script = None

    def enable(self):
        """开启多端学习（开启兼容）"""
        if self._enabled:
            return
        # ============ 手段二：覆盖 confirm 和 alert 弹窗 ============
        self.driver.execute_script("""
                // 覆盖 confirm，永远返回 true（自动点击确定）
                window._originalConfirm = window.confirm;
                window.confirm = function(msg) {
                    console.log('[多端学习] 已自动关闭 confirm 弹窗:', msg);
                    return true;
                };

                // 覆盖 alert，静默关闭（无返回值）
                window._originalAlert = window.alert;
                window.alert = function(msg) {
                    console.log('[多端学习] 已自动关闭 alert 弹窗:', msg);
                    // 不执行任何操作，弹窗消失
                };
            """)
        # ============ 手段一：兼容处理 appendChild，兼容处理检测代码 ============
        self.driver.execute_script("""
            // 保存原始 appendChild
            if (!window._originalAppendChild) {
                window._originalAppendChild = Element.prototype.appendChild;
            }

            Element.prototype.appendChild = function() {
                try {
                    // 兼容处理 detect.chaoxing.com 的检测代码
                    if (arguments[0].src && arguments[0].src.indexOf('detect.chaoxing.com') > 0) {
                        console.log('[多端学习] 已跳过检测代码:', arguments[0].src);
                        return;  // 不注入
                    }
                } catch (e) {}
                // 正常代码放行
                return window._originalAppendChild.apply(this, arguments);
            };
        """)



        # ============ 手段三：定时重新覆盖（防止页面恢复） ============
        self._confirm_interval_script = """
            if (!window._confirmInterval) {
                window._confirmInterval = setInterval(function() {
                    window.confirm = function(msg) { 
                        console.log('[多端学习] 定时重设 confirm:', msg);
                        return true; 
                    };
                    window.alert = function(msg) {
                        console.log('[多端学习] 定时重设 alert:', msg);
                    };
                }, 2000);
            }
        """
        self.driver.execute_script(self._confirm_interval_script)

        self._enabled = True
        print('[多端学习] 兼容已开启，可以多端同时学习，且已自动屏蔽 alert/confirm 弹窗')

    def disable(self):
        """关闭多端学习（恢复状态检测）"""
        if not self._enabled:
            return

        self.driver.execute_script("""
            // 恢复原始 appendChild
            if (window._originalAppendChild) {
                Element.prototype.appendChild = window._originalAppendChild;
            }

            // 恢复原始 confirm
            if (window._originalConfirm) {
                window.confirm = window._originalConfirm;
            }

            // 清除定时器
            if (window._confirmInterval) {
                clearInterval(window._confirmInterval);
                window._confirmInterval = null;
            }
        """)

        self._enabled = False
        print('[多端学习] 兼容已关闭')

    def is_enabled(self) -> bool:
        """检查是否已开启"""
        return self._enabled

# ============ 使用示例 ============
if __name__ == '__main__':
    from selenium import webdriver
    from selenium.webdriver.edge.options import Options

    options = Options()
    driver = webdriver.Edge(options=options)

    # 先登录学习平台...
    driver.get('https://i.chaoxing.com/')

    # 开启多端学习
    monitor = PageCompat(driver)
    monitor.enable()
    time.sleep(1000)

    # ... 后续正常学习 ...

    # 关闭多端学习
    # monitor.disable()