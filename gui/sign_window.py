from __future__ import annotations
import sys
import threading
import tkinter as tk
import customtkinter as ctk

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from task.xxt import constants, login as login_mod, monitor, storage  # noqa: E402
sign_txt = None


def bootstrap( phone: str = None, password: str = None):
    """获取可用会话: 优先用本地保存的信息, 否则提示输入"""
    client = login_mod.restore_client(sign_text=sign_txt)
    if client is not None:
        storage.log("已使用本地保存的登录信息(%s), 无需重新输入账号密码"
                    % (client.name or client.uid),sign_text=sign_txt)
        return client


    while True:
        client, msg = login_mod.do_login(phone, password)
        if client is not None:
            storage.log(msg,sign_text=sign_txt)
            storage.log("登录信息已保存到 data/config.json, 下次启动免输入",sign_text=sign_txt)
            return client
        storage.log("登录失败: %s" % msg,sign_text=sign_txt)
        try:
            answer = input("重新输入? (回车继续 / 输入 q 退出): ")
        except (EOFError, OSError):
            # 打包成子进程运行时没有 stdin，直接退出，避免卡住或抛异常
            answer = 'q'
        if answer.strip().lower() != "q":
            continue
        return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="学习平台自动签到(精简版: 普通/位置)")
    parser.add_argument("--interval", type=int, default=constants.CHECK_INTERVAL,
                        help="检查间隔秒数, 默认 %d" % constants.CHECK_INTERVAL)
    parser.add_argument("--once", action="store_true", help="只检查一轮")
    parser.add_argument("--workers", type=int, default=monitor.DEFAULT_WORKERS,
                        help="并发读取课程的线程数, 默认 %d(设 1 为串行)"
                        % monitor.DEFAULT_WORKERS)
    parser.add_argument("--relogin", action="store_true", help="忽略本地信息, 重新登录")
    return parser


def main(phone: str = None, password: str = None, stop_event=None) -> int:
    # 子进程入口是 `start.py --sign`，--sign 不是本模块的参数；
    # 用 parse_known_args 避免 argparse 报「unrecognized arguments」直接 SystemExit(2)。
    args = _build_parser().parse_known_args()[0]

    client = bootstrap(phone=phone, password=password)
    if client is None:
        storage.log("未获得有效登录, 退出",sign_text=sign_txt)
        return 1

    if args.once:
        started = time.time()
        handled = monitor.scan_and_sign_once(client, workers=args.workers)
        storage.log("本轮完成 %d 个签到, 耗时 %.1f 秒" % (len(handled), time.time() - started),sign_text=sign_txt)
        return 0

    try:
        monitor.monitor(client, interval=args.interval, workers=args.workers, stop_event=stop_event,sign_text=sign_txt)
    except KeyboardInterrupt:
        storage.log("已手动停止",sign_text=sign_txt)
    return 0
def start_sign_monitor(account, stop_event=None,sign_text=None):
    global sign_txt
    sign_txt = sign_text
    phone = account.get("phone_number", "")
    password = account.get("password", "")
    main(phone=phone, password=password, stop_event=stop_event)


def _watch_parent_exit(stop_event) -> None:
    """子进程里：GUI 主进程不在了就自己停，避免关窗口后残留继续轮询平台。"""
    try:
        ppid = os.getppid()
    except Exception:
        return

    def watch():
        while not stop_event.wait(5):
            try:
                if os.getppid() != ppid:
                    stop_event.set()
                    return
            except Exception:
                return

    threading.Thread(target=watch, daemon=True).start()


def sign_once() -> int:
    """子进程入口（`start.py --sign`）：读本账号的 account_info.json 跑签到监控。

    每个账号一个子进程、各自 XXT_HOME，签到数据（config.json/cookie）互不覆盖。
    """
    import json
    from core import paths
    try:
        with open(paths.data('tool', 'account_info.json'), 'r', encoding='utf-8') as f:
            info = json.load(f)
    except Exception as e:
        print('读取账号信息失败: %s' % e, flush=True)
        return 1
    phone = info.get('phone_number') or info.get('phone') or ''
    password = info.get('password') or ''
    if not phone:
        print('账号信息里没有手机号，无法签到', flush=True)
        return 1
    name = info.get('alias') or phone[-4:]
    print('开始为 %s 签到…' % name, flush=True)
    stop_event = threading.Event()
    _watch_parent_exit(stop_event)
    try:
        return main(phone=phone, password=password, stop_event=stop_event)
    except Exception as e:      # noqa: BLE001 - 子进程要把原因打出来而不是静默退出
        import traceback
        print('签到出错: %s' % e, flush=True)
        print(traceback.format_exc(), flush=True)
        return 1


class SignWindow:
    """自动签到窗口：支持勾选多个账号，每个账号一个子进程（数据互不干扰）。"""

    def __init__(self, master, accounts, font, auto_sign_btn, button_color,
                 button_hover_color, config=None):
        from core.config_manager import ConfigManager
        from core.runner import Runner

        self._Runner = Runner
        self.config = config or ConfigManager()
        if isinstance(accounts, dict):
            accounts = [accounts]
        self.accounts = list(accounts or [])
        self.master = master
        self.font = font
        self.button_color = button_color
        self.button_hover_color = button_hover_color
        self.auto_sign_btn = auto_sign_btn
        self.auto_sign_btn.configure(state=tk.DISABLED)
        self.runner = None
        self.checks = {}
        self._aliases = {a['id']: (a.get('alias') or a.get('phone', '')[-4:] or a['id'])
                         for a in self.accounts if a.get('id')}

        self.window = ctk.CTkToplevel(master)
        self.window.title("自动签到（可多选账号）")
        self.window.geometry("460x460")
        self.window.resizable(True, True)
        self.window.after(100, self.window.lift)
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        # 账号勾选区
        pick_bar = ctk.CTkFrame(self.window, fg_color='transparent')
        pick_bar.pack(fill=tk.X, padx=10, pady=(10, 0))
        ctk.CTkLabel(pick_bar, text="选择要签到的账号：", font=font,
                     fg_color='transparent').pack(side=tk.LEFT)
        ctk.CTkButton(pick_bar, text="全选", width=56, font=ctk.CTkFont(size=11),
                      fg_color=button_color, hover_color=button_hover_color,
                      command=lambda: self._check_all(True)).pack(side=tk.RIGHT, padx=2)
        ctk.CTkButton(pick_bar, text="全不选", width=64, font=ctk.CTkFont(size=11),
                      fg_color="#6B7280", hover_color="#4B5563",
                      command=lambda: self._check_all(False)).pack(side=tk.RIGHT, padx=2)

        self.list_frame = ctk.CTkScrollableFrame(self.window, height=110)
        self.list_frame.pack(fill=tk.X, padx=10, pady=(4, 0))
        for acc in self.accounts:
            if not acc.get('id'):
                continue
            var = tk.BooleanVar(value=bool(acc.get('enabled', True)))
            cb = ctk.CTkCheckBox(self.list_frame, text=self._label(acc), variable=var,
                                 font=font, checkbox_width=18, checkbox_height=18)
            cb.pack(anchor='w', padx=6, pady=1)
            self.checks[acc['id']] = var
        if not self.checks:
            ctk.CTkLabel(self.list_frame, text="（还没有账号，请先在设置里添加）",
                         font=font, fg_color='transparent').pack(anchor='w', padx=6)

        # 按钮区
        self.btn_frame = ctk.CTkFrame(self.window, fg_color='transparent')
        self.btn_frame.pack(fill=tk.X, padx=10, pady=(8, 0))
        self.hint_label = ctk.CTkLabel(
            self.btn_frame, font=ctk.CTkFont(size=11),
            text="提示：只能自动完成常规签到和位置签到；多账号各起一个子进程，签到数据互不影响",
            fg_color='transparent', text_color='gray')
        self.hint_label.pack(side=tk.TOP, anchor=tk.W, pady=(0, 5))
        self.start_btn = ctk.CTkButton(self.btn_frame, text="▶ 启动自动签到", font=font,
                                       fg_color=button_color, hover_color=button_hover_color,
                                       command=self.start_monitor)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ctk.CTkButton(self.btn_frame, text="■ 关闭自动签到", font=font,
                                      fg_color="#DC2626", hover_color="#B91C1C",
                                      command=self.stop_monitor)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # 输出区
        self.sign_text = ctk.CTkTextbox(self.window, font=font, border_width=1)
        self.sign_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._log('勾选账号后点「启动自动签到」。\n')

    # ------------------------------------------------------------------ 小工具
    def _label(self, acc):
        alias = acc.get('alias') or '未命名'
        phone = acc.get('phone') or ''
        tail = phone[-4:] if phone else ''
        return '%s（%s）' % (alias, tail) if tail else alias

    def _check_all(self, value):
        for var in self.checks.values():
            var.set(bool(value))

    def _log(self, text):
        """线程安全地往输出框追加文本。"""
        try:
            self.sign_text.after(0, self._log_now, text)
        except Exception:
            pass

    def _log_now(self, text):
        try:
            self.sign_text.insert(tk.END, text)
            self.sign_text.see(tk.END)
        except Exception:
            pass

    # ------------------------------------------------------------------ 控制
    def start_monitor(self):
        selected = [aid for aid, var in self.checks.items() if var.get()]
        if not selected:
            self._log('请先勾选要签到的账号\n')
            return
        if self.runner is not None and self.runner.active_count():
            self._log('已有签到任务在跑，先关闭再启动\n')
            return
        names = '、'.join(self._aliases.get(aid, aid) for aid in selected)
        self._log('开始签到：%s\n' % names)
        self.runner = self._Runner(
            self.config, self._on_output, self._on_finish,
            max_concurrency=max(1, min(3, len(selected))),
            entry_args=('--sign',))
        self.runner.start(selected)
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)

    def _on_output(self, account_id, text, tag):
        name = self._aliases.get(account_id, account_id)
        for line in (text or '').splitlines():
            if line.strip():
                self._log('[%s] %s\n' % (name, line))

    def _on_finish(self, account_id, code):
        name = self._aliases.get(account_id, account_id)
        self._log('[%s] 签到进程结束，退出码 %s\n' % (name, code))

    def stop_monitor(self):
        if self.runner is not None:
            self.runner.stop_all()
        self._log('自动签到已关闭\n')
        self.stop_btn.configure(state=tk.DISABLED)
        self.start_btn.configure(state=tk.NORMAL)

    def on_close(self):
        try:
            self.stop_monitor()
        except Exception:
            pass
        self.window.destroy()
        self.auto_sign_btn.configure(state=tk.NORMAL)