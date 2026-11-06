# Copyright (c) 2025 Mortal004
# All rights reserved.
# This software is provided for non-commercial use only.
# For more information, see the LICENSE file in the root directory of this project.
#激活环境start_venv\Scripts\activate
#打包（推荐）：python -m PyInstaller start.spec --noconfirm
#产物 dist/start.exe，首次运行会在同目录自动释放 task/ 资源目录
#直接命令行打包时必须带资源：python -m PyInstaller --onefile --noconsole --add-data "task;task" --collect-all customtkinter start.py
import json
import signal
import time
from datetime import datetime, timedelta
import re
import threading
import tkinter as tk
import subprocess
from PIL import Image
from colorama import Fore
from tkinter import ttk, messagebox
import os
import sys
import customtkinter as ctk
import pickle
import logging

from gui import theme
from core import paths
from core import applog
from core.runner import Runner
from gui.sponsor_panel import SponsorPanel
from core.config_manager import ConfigManager
from gui.update_checker import UpdateChecker
from gui.timer_window import TimerWindow
from gui.setting_panel import SettingsPanel
from gui.sign_window import SignWindow
from gui.log_export_dialog import open_export_dialog


def app_dir() -> str:
    """打包后返回 exe 所在目录，源码运行时返回 start.py 所在目录。"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def prepare_runtime() -> None:
    """统一入口：迁移旧数据、建好可写目录、把工作目录切到程序根目录。

    打包成单文件后资源在 _MEIPASS（只读、退出即删），用户数据统一放到
    %LOCALAPPDATA%\\XuexitongShuake，exe 旁边不会产生任何文件。
    """
    paths.prepare()
    os.chdir(app_dir())


# 日志也写进用户数据目录，避免 exe 放在只读目录时启动即失败
paths.ensure_data_dirs()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(paths.root_data('输出记录.log'), encoding='utf-8')]
)
logger = logging.getLogger(__name__)

class Start:
    def __init__(self):
        prepare_runtime()
        self.announcement =("注意：本程序仅供个人学习交流使用，请遵守平台与学校规定；"
                            "使用本程序产生的任何后果由使用者自行承担，开发者不承担任何责任。")
        self.lab_lst = []
        self._alias_map = {}
        self.thread = None
        self.config = ConfigManager()
        self.runner = Runner(self.config, self._on_account_output,
                             self._on_account_finish, max_concurrency=2)
        self.timer_active = False

        self.dynamic_rows = []
        self.process = {}
        self.text_box_lst=[]

        self.colorama_to_tkinter = {
            'RED': 'red',
            'YELLOW': 'yellow',
            'BLUE': 'blue',
            'GREEN': 'green',
            'MAGENTA': 'magenta'
        }
        self.color_value_dict = theme.legacy_dict()
        self.font = theme.font(12)
        self.record_color_lst = [theme.DEFAULT_THEME]

        self.palette = theme.palette(self.record_color_lst[0])
        self.frame_fg_color = self.palette['bg']
        self.surface_color = self.palette['surface']
        self.border_color = self.palette['border']
        self.text_color = self.palette['text']
        self.text_muted_color = self.palette['text_muted']
        self.button_color = self.palette['accent']
        self.button_hover_color = self.palette['accent_hover']
        self.button_soft_color = self.palette['accent_soft']
        self.danger_color = theme.DANGER
        self.danger_hover_color = theme.DANGER_HOVER

        ctk.set_appearance_mode("light")
        self.root = ctk.CTk(fg_color=self.frame_fg_color)
        with open(paths.asset('tool', 'version_info'), 'r', encoding='utf-8') as f:
            version_info = f.read()
            self.root.title(f'课程学习助手 {version_info}')
        self.main_frame = ctk.CTkFrame(self.root, fg_color=self.frame_fg_color, corner_radius=0)
        self.set_frame = ctk.CTkFrame(self.root, fg_color=self.frame_fg_color, corner_radius=0)
        self.help_frame = ctk.CTkFrame(self.root, fg_color=self.frame_fg_color, corner_radius=0)
        self.vido_frame = ctk.CTkFrame(self.root, fg_color=self.frame_fg_color, corner_radius=0)
        self.score_frame = ctk.CTkFrame(self.root, fg_color=self.frame_fg_color, corner_radius=0)
        self.question_bank_frame = ctk.CTkFrame(self.root, fg_color=self.frame_fg_color, corner_radius=0)
        self.error_frame = ctk.CTkFrame(self.root, fg_color=self.frame_fg_color, corner_radius=0)
        self.money_frame = ctk.CTkFrame(self.root, fg_color=self.frame_fg_color, corner_radius=0)
        self.root.resizable(True, True)
        # 允许自由缩放，但给个下限，避免日志区和按钮挤成一团
        self.root.minsize(860, 560)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(1, weight=1)
        self.root.iconbitmap(paths.asset('img', 'xuexitong1 .ico'))
        self.root.attributes('-alpha', 1)
        # 关闭窗口 / 界面回调异常都记进程序日志，方便事后追溯
        self.root.protocol('WM_DELETE_WINDOW', self._on_window_close)
        self.root.report_callback_exception = self._on_ui_exception
        applog.info('窗口初始化完成：title=%s' % self.root.title())
        # 初始化子模块
        self._updater = UpdateChecker(self.root, self.config.get_version, self._get_colors)
        self._timer = TimerWindow(self.root, self._on_timer_set, self._on_timer_cancel,
                                  self._get_font, self._get_colors)
        # 加载图标
        self.menu_image = ctk.CTkImage(light_image=Image.open(paths.asset('img', 'menu.png')), size=(24, 24))
        self.fold_image = ctk.CTkImage(light_image=Image.open(paths.asset('img', 'fold.png')), size=(12, 20))
        self.open_image = ctk.CTkImage(light_image=Image.open(paths.asset('img', 'open.png')), size=(12, 20))
        self.show_image = ctk.CTkImage(light_image=Image.open(paths.asset('img', 'show.png')), size=(16, 12))
        self.add_image = ctk.CTkImage(light_image=Image.open(paths.asset('img', 'add.png')), size=(18, 19))
        self.image_name_list = ['home_dark.png', 'set.png', 'help.png', 'vido.png', 'score.png', 'find.png',
                                'error.png', 'give_money.png']
        self.image_list = []
        for name in self.image_name_list:
            self.image_list.append(ctk.CTkImage(light_image=Image.open(paths.asset('img', name)), size=(16, 16)))

        # ----------------创建菜单页面----------------
        self.navigation_frame = ctk.CTkFrame(self.root, corner_radius=0, fg_color=self.surface_color, width=20)
        self.navigation_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.navigation_frame.grid_rowconfigure(9, weight=1)
        self.open_frame = ctk.CTkFrame(self.root, corner_radius=0, width=0, fg_color=self.surface_color)
        self.open_frame.grid_rowconfigure(0, weight=1)
        self.open_button = ctk.CTkButton(self.open_frame, corner_radius=0, width=10, height=40, border_spacing=10,
                                         text="", font=self.font, image=self.open_image,
                                         fg_color='transparent', text_color=self.text_color,
                                         hover_color=self.button_soft_color, anchor="center",
                                         command=self.reopen_frame)
        self.open_button.grid(row=0, column=0, sticky="ew")
        self.navigation_frame_label = ctk.CTkLabel(self.navigation_frame, text="  MENU   ", image=self.menu_image,
                                                   compound="left", fg_color="transparent",
                                                   text_color=self.text_color, font=self.font, anchor="nw")
        self.navigation_frame_label.grid(row=0, column=0, pady=10)
        self.fold_button = ctk.CTkButton(self.navigation_frame, corner_radius=0, width=10, height=28, border_spacing=4,
                                         text='收起', font=self.font, image=self.fold_image,
                                         fg_color="transparent", text_color=self.text_muted_color,
                                         hover_color=self.button_soft_color,
                                         anchor="e", command=self.fold_frame)
        self.fold_button.grid(row=9, column=0, sticky="new")
        self.button_text_list = ["主页", "设置", "帮助", "学习记录", "测试成绩", "题库查询", "报错日志", "赞助作者"]
        self.button_command_list = [self.show_main, self.show_set, self.show_help,
                                    lambda: self.show_record('学习'), lambda: self.show_record('成绩'),
                                    self.show_question_bank, self.show_error, self.show_money]
        self.button_name_list = ['home_button', 'set_button', 'help_button', 'vido_button', 'score_button',
                                 'question_bank_button', 'money_button',
                                 self.open_button, self.fold_button]
        for i in range(len(self.button_text_list)):
            self.button_name_list[i] = ctk.CTkButton(self.navigation_frame, corner_radius=8, width=20, height=28,
                                                     border_spacing=4,
                                                     text=self.button_text_list[i], font=self.font,
                                                     image=self.image_list[i],
                                                     fg_color="transparent", text_color=self.text_color,
                                                     hover_color=self.button_soft_color, anchor="w",
                                                     command=self.button_command_list[i])
            self.button_name_list[i].grid(row=i + 1, column=0, padx=6, pady=0, sticky="ew")
        self.change_theme = ctk.CTkOptionMenu(self.navigation_frame, values=[i for i in self.color_value_dict.keys()],
                                              width=10, fg_color=self.palette['surface_alt'], font=self.font,
                                              text_color=self.text_color,
                                              dropdown_fg_color=self.surface_color, button_color=self.border_color,
                                              dropdown_hover_color=self.button_soft_color,
                                              button_hover_color=self.border_color,
                                              command=self.change_appearance_mode_event)
        self.change_theme.grid(row=11, column=0,pady=3,sticky="s")
        self.change_theme_value = self.change_theme.get()
        # self.feedback_button = ctk.CTkButton(self.navigation_frame, text="💬 我要验牌",
        #                                      font=self.font,width=10,text_color='black',
        #                                      fg_color=self.button_hover_color,
        #                                      hover_color=self.button_color,
        #                                      command=self._show_feedback_popup)
        # self.feedback_button.grid(row=10, column=0, pady=(20, 2),sticky="s")
        # ----------------标签页----------------
        self.label_frame = ctk.CTkFrame(self.root, fg_color=self.frame_fg_color, corner_radius=0)
        self.label_frame.grid(row=0, column=1, sticky='nsew')
        self.label_frame.columnconfigure(0, weight=1)

        self.time_label = ctk.CTkLabel(self.label_frame, text="", fg_color='transparent', font=self.font)
        self.time_label.grid(row=0, column=0, columnspan=3, padx=5, pady=2, sticky=tk.W)
        self.announcement_text = ctk.CTkTextbox(self.label_frame, font=self.font,
                                                fg_color=self.surface_color, border_width=1,
                                                border_color=self.border_color, height=50, width=450)
        self.announcement_text.insert(tk.END, self.announcement)
        self.announcement_text.configure(state=tk.DISABLED)
        self.announcement_text.grid(row=1, column=0, columnspan=3, sticky=tk.W + tk.E, padx=5, pady=0)

        # ---------------- 主页 ----------------
        self.start_button = ctk.CTkButton(self.main_frame, text="▶ 开始学习", height=40, border_spacing=10,
                                          fg_color=self.button_color,
                                          command=self.start, font=self.font, hover_color=self.button_hover_color)
        self.start_button.grid(row=0, column=0, padx=5, pady=5)
        self.auto_sign = ctk.CTkButton(self.main_frame, text="自动签到", height=40, border_spacing=10,
                                       fg_color=self.button_color,
                                       command=self.start_sign, font=self.font,
                                       hover_color=self.button_hover_color)
        self.auto_sign.grid(row=0, column=1, padx=5, pady=5)
        self.close_button = ctk.CTkButton(self.main_frame, text="■ 结束学习", height=40, border_spacing=10,
                                          fg_color=self.button_color, hover_color=self.button_hover_color,
                                          command=self.close, font=self.font)
        self.update_button = ctk.CTkButton(self.main_frame, text="↻ 检查更新", height=40, border_spacing=10,
                                           fg_color=self.button_color,
                                           command=self.check_update, font=self.font,
                                           hover_color=self.button_hover_color)
        self.update_button.grid(row=0, column=2, padx=5, pady=5)
        # 一键导出：把某一天的全部日志/截图/记录/脱敏配置收进一个 zip 单文件
        self.export_log_button = ctk.CTkButton(self.main_frame, text="⇩ 导出完整日志",
                                               height=40, border_spacing=10,
                                               fg_color=self.button_color,
                                               command=lambda: open_export_dialog(self.root),
                                               font=self.font,
                                               hover_color=self.button_hover_color)
        self.export_log_button.grid(row=0, column=3, padx=5, pady=5)
        self.text_box_frame= ctk.CTkFrame(self.main_frame, fg_color=self.frame_fg_color, corner_radius=0,width=450)
        self.text_box_frame.grid(row=1, column=0, columnspan=4, padx=10, pady=10, sticky=tk.W + tk.E + tk.N + tk.S)
        self.text_box_frame.columnconfigure(0, weight=1)
        self.text_box_frame.rowconfigure(1, weight=1)
        # 让内容区填满窗口，避免右侧与底部留出大片空白
        for _col in (0, 1, 2, 3):
            self.main_frame.columnconfigure(_col, weight=1)
        self.main_frame.rowconfigure(1, weight=1)

        # 日志区顶部：按账号切换查看
        self.log_bar = ctk.CTkFrame(self.text_box_frame, fg_color='transparent')
        self.log_bar.grid(row=0, column=0, sticky="ew", padx=2, pady=(0, 4))
        ctk.CTkLabel(self.log_bar, text="查看日志", font=self.font, fg_color='transparent',
                     text_color=self.text_muted_color).pack(side="left", padx=(2, 8))
        self.log_select = ctk.CTkComboBox(self.log_bar, values=[], width=240, font=self.font,
                                          dropdown_fg_color=self.surface_color,
                                          button_color=self.button_color,
                                          button_hover_color=self.button_hover_color,
                                          dropdown_hover_color=self.button_soft_color,
                                          command=self._switch_log)
        self.log_select.pack(side="left")
        # 并发运行状态：哪几个账号在跑、哪几个在排队，一眼看清
        self.runtime_label = ctk.CTkLabel(self.log_bar, text="", font=self.font,
                                          fg_color='transparent',
                                          text_color=self.text_muted_color)
        self.runtime_label.pack(side="left", padx=(12, 0))

        self.log_host = ctk.CTkFrame(self.text_box_frame, fg_color='transparent')
        self.log_host.grid(row=1, column=0, sticky="nsew")
        self.log_host.columnconfigure(0, weight=1)
        self.log_host.rowconfigure(0, weight=1)

        self.text_box_map = {}
        self._log_index = {}
        self.text_box = self._ensure_log_box('__default__')
        self.text_box.grid(row=0, column=0, sticky="nsew")

        self.hint_txt='WELCOME TO 课程学习助手 ！！！\n请先进入设置页面填写信息！！！'
        self.hint_label=ctk.CTkLabel(self.log_host,text=self.hint_txt,font=self.font,
                                     fg_color=self.surface_color,
                                     width=300,text_color=self.danger_color)
        self.hint_label.grid(row=0,column=0,sticky=tk.N,pady=5,padx=5)
        self.frame_name_list = [self.main_frame, self.set_frame, self.help_frame, self.vido_frame,
                                self.score_frame, self.question_bank_frame, self.error_frame, self.money_frame,
                                self.open_frame, self.navigation_frame, self.label_frame,self.text_box_frame]
        # ---------------- 学习记录 ----------------
        self.course_vido_entry = ctk.CTkComboBox(self.vido_frame, dropdown_font=self.font, values=[],
                                                 dropdown_fg_color=self.surface_color,
                                                 button_color=self.button_color,
                                                 button_hover_color=self.button_hover_color,
                                                 dropdown_hover_color=self.button_soft_color,
                                                 font=self.font, command=lambda value: self.show_record('学习'))
        self.course_name = self.course_vido_entry.get()
        self.course_vido_entry.grid(row=0, column=0, padx=10, pady=(10, 0), sticky=tk.W + tk.E)
        self.find_button1 = ctk.CTkButton(self.vido_frame, text="查询", command=lambda: self.show_record('学习'),
                                          fg_color=self.button_color,
                                          font=self.font, hover_color=self.button_hover_color)
        self.find_button1.grid(row=0, column=1, padx=1, pady=(10, 0), sticky=tk.W)
        self.delete_button1 = ctk.CTkButton(self.vido_frame, text="删除记录",
                                            command=lambda: self.delete_record('学习'), fg_color=self.danger_color,
                                            hover_color=self.danger_hover_color,
                                            font=self.font)
        self.delete_button1.grid(row=0, column=2, padx=1, pady=(10, 0))

        self.progress_frame = ctk.CTkFrame(self.vido_frame, fg_color='transparent', corner_radius=0)
        self.progress_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=(8, 2), sticky=tk.EW)

        self.course_progress_label = ctk.CTkLabel(self.progress_frame, text="", font=ctk.CTkFont(size=12),
                                                  fg_color='transparent', anchor="w")
        self.course_progress_label.pack(side=tk.LEFT, padx=(0, 10))

        self.course_progress_bar = ctk.CTkProgressBar(self.progress_frame, height=8, width=200,
                                                      fg_color=self.palette['accent_soft'],
                                                      progress_color=self.button_color,
                                                      corner_radius=4)
        self.course_progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.course_progress_bar.set(0)

        self.vido_text = ctk.CTkTextbox(self.vido_frame, height=self._box_height(40), width=435, font=self.font,
                                        fg_color=self.surface_color, border_width=1,
                                        border_color=self.border_color)
        self.vido_text.configure(state=tk.DISABLED)
        self.vido_text.grid(row=2, column=0, columnspan=3, padx=10, pady=5, sticky=tk.W + tk.E + tk.N + tk.S)

        # ---------------- 成绩日志 ----------------
        self.course_score_entry = ctk.CTkComboBox(self.score_frame, dropdown_font=self.font, font=self.font, values=[],
                                                  dropdown_fg_color=self.surface_color,
                                                  button_color=self.button_color,
                                                  button_hover_color=self.button_hover_color,
                                                  dropdown_hover_color=self.button_soft_color,
                                                  command=lambda value: self.show_record('成绩'))
        self.course_name = self.course_score_entry.get()
        self.course_score_entry.grid(row=0, column=0, padx=10, pady=5, sticky=tk.W + tk.E)
        self.find_button2 = ctk.CTkButton(self.score_frame, text="查询", command=lambda: self.show_record('成绩'),
                                          fg_color=self.button_color,
                                          font=self.font, hover_color=self.button_hover_color)
        self.find_button2.grid(row=0, column=1, padx=1, pady=5)
        self.delete_button2 = ctk.CTkButton(self.score_frame, text="删除记录",
                                            command=lambda: self.delete_record('成绩'), fg_color=self.danger_color,
                                            hover_color=self.danger_hover_color,
                                            font=self.font)
        self.delete_button2.grid(row=0, column=2, padx=1, pady=5)
        self.score_frame.rowconfigure(0, weight=1)
        self.score_txt = ctk.CTkTextbox(self.score_frame, height=self._box_height(60), width=435, font=self.font,
                                        fg_color=self.surface_color, border_width=1,
                                        border_color=self.border_color)
        self.score_txt.configure(state=tk.DISABLED)
        self.score_txt.grid(row=1, column=0, columnspan=3, padx=10, pady=5,
                            sticky=tk.W + tk.E + tk.N + tk.S)
        self.dit = {'学习': [self.course_vido_entry, '学习记录', self.vido_text, self.vido_frame],
                    '成绩': [self.course_score_entry, '测试成绩', self.score_txt, self.score_frame]}

        # ---------------- 题库查询 ----------------
        self.tiku_text = ctk.CTkTextbox(self.question_bank_frame, height=self._box_height(60), width=437,
                                        font=self.font, fg_color=self.surface_color, border_width=1,
                                        border_color=self.border_color)
        self.tiku_text.configure(state=tk.DISABLED)
        self.tiku_text.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky=tk.W + tk.E + tk.N + tk.S)
        self.delete_tiku_button = ctk.CTkButton(
            self.question_bank_frame, text="删除所有缓存题目", command=self.delete_huancun,
            fg_color=self.danger_color, hover_color=self.danger_hover_color, corner_radius=16, height=36
        )
        self.delete_tiku_button.grid(row=2, column=0, padx=1, pady=5, columnspan=2, sticky=tk.W + tk.E)

        # ---------------- 设置页面（委托给 SettingsPanel） ----------------
        self.style = ttk.Style()
        self.style.configure('TLabelframe', background=self.frame_fg_color, borderwidth=10)
        self.style.configure('TLabelframe.Label', background=self.frame_fg_color, font=self.font)
        self.style.configure('TLabel', background=self.frame_fg_color)
        self.account_info = self.config.load_account()
        # 设置项较多，放进可滚动容器，避免小屏下“保存设置”被窗口底部截断
        self.settings_scroll = ctk.CTkScrollableFrame(
            self.set_frame, fg_color=self.frame_fg_color, corner_radius=0,
            scrollbar_button_color=self.border_color,
            scrollbar_button_hover_color=self.text_muted_color)
        self.settings_scroll.pack(fill="both", expand=True)
        self.frame_name_list.append(self.settings_scroll)
        self.settings_panel = SettingsPanel(
            self.settings_scroll, self.config,
            change_font=self.change_font,
            change_text_box=self.change_text_box,
            get_font=self._get_font,
            get_colors=self._get_colors,
            get_theme=self._get_theme,
            show_money=self.show_money,
            root=self.root,
            _timer=self._timer
        )

        self.combobox_lst = [
            self.change_theme, self.course_score_entry, self.course_vido_entry,
        ]
        self.combobox_lst.extend(self.settings_panel.comboboxes)
        self.check_switch = list(self.settings_panel.switches)
        self.button_name_list1 = [self.start_button, self.auto_sign, self.close_button, self.update_button,
                                  self.export_log_button,
                                  self.find_button1, self.find_button2, self.delete_button1, self.delete_button2]
        self.button_name_list1.extend(self.settings_panel.buttons)

        # ---------------- 帮助页面 ----------------
        self.text = self.config.get_help_text()
        self.help_txt = ctk.CTkTextbox(self.help_frame, height=self._box_height(80), width=500, font=self.font,
                                       fg_color=self.surface_color, border_width=1,
                                       border_color=self.border_color)
        self.help_txt.grid(pady=(5,20))
        self.help_txt.insert(tk.END, self.text)
        self.help_txt.configure(state=tk.DISABLED)

        # ---------------- 报错日志 ----------------
        self.error_text = ctk.CTkTextbox(self.error_frame, height=self._box_height(80), width=497,
                                         font=self.font, fg_color=self.surface_color, border_width=1,
                                         border_color=self.border_color)
        self.error_text.configure(state=tk.DISABLED)
        self.error_text.grid(pady=(5,20),row=0,column=0)

        # ---------------- 赞助页面 ----------------
        self.sponsor_panel = SponsorPanel(self.money_frame,self._get_font,self._get_colors,self.root)


        self.process_condition = False
        self._load_data()
        self.show_main()
        self.settings_panel.function_choice()
        # 启动不再弹「用户须知」，直接进入主界面；
        # 更新检查延后到窗口画出来之后再跑，避免网络慢时白屏等 10 秒
        self.root.after(800, self.check_update)
        self.change_text_box(self.all_cour,self.multi_device)
        self.update_time()
        if self.timer_active:
            self.hint_txt+=(f"\n定时学习已开启:\n  开始时间: {self.timer_start_time}\n  "
                                 f"结束时间: {self.timer_end_time}\n"
                                 f"请勿关闭此窗口，否则定时学习将无法正常开启")
        self.hint_label.configure(text=self.hint_txt)

        # 依据内容自适应尺寸并居中显示（原先写死在屏幕右侧 +1050+20）
        self.root.update_idletasks()
        scale = ctk.ScalingTracker.get_window_scaling(self.root) or 1.0
        win_w = self.root.winfo_reqwidth()   # 逻辑尺寸，CTk 的 geometry 内部会乘以缩放比
        win_h = self.root.winfo_reqheight()
        pos_x = max(0, (self.root.winfo_screenwidth() - int(win_w * scale)) // 2)
        pos_y = max(0, (self.root.winfo_screenheight() - int(win_h * scale)) // 3)
        self.root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")


    # ========== 委托方法（供子模块回调） ==========

    def _box_height(self, extra: int = 0) -> int:
        """日志框高度按屏幕高度自适应，避免窗口高过屏幕被截断。
        返回值是 CTk 的尺寸参数（内部已按窗口缩放折算）。"""
        scale = ctk.ScalingTracker.get_window_scaling(self.root) or 1.0
        avail = self.root.winfo_screenheight() / scale
        target = max(220, min(480, avail - 340)) + extra
        return int(target / scale)

    def _get_font(self):
        return (self.account_info.get('font_type', theme.FONT_FAMILY),
                int(self.account_info.get('font_size', 12)))

    def _get_colors(self):
        name = self.record_color_lst[-1] if self.record_color_lst else theme.DEFAULT_THEME
        return theme.legacy_colors(name)

    def _get_theme(self):
        name = self.record_color_lst[-1] if self.record_color_lst else theme.DEFAULT_THEME
        return theme.legacy_colors(name)

    def _on_timer_set(self, start_str, end_str):
        self.timer_start_time = start_str
        self.timer_end_time = end_str
        self.timer_active = True
        self.hint_txt+=(     f"\n定时学习已开启:\n  开始时间: {self.timer_start_time}\n"
                             f"  结束时间: {self.timer_end_time}\n"
                             f"请勿关闭此窗口，否则定时学习将无法正常开启")
        self.text_box.see(tk.END)
        self.account_info['timer_start'] = start_str
        self.account_info['timer_end'] = end_str
        self.account_info['timer_active']=1

        self.config.save_account(self.account_info)
        self.hint_label.configure(text=self.hint_txt)

    def _on_timer_cancel(self):
        self.timer_active = False
        self.hint_txt+= "\n定时学习已禁用"
        self.account_info['timer_active']=0
        self.config.save_account(self.account_info)
        self.hint_label.configure(text=self.hint_txt)

    def _load_data(self):
        """加载账户配置和课程数据"""
        try:
            self.account_info = self.config.load_account()
            phone = self.account_info.get('phone_number', '')
            self.data = self.config.load_courses(phone)
            if self.data:
                self.course_score_entry.configure(values=tuple(self.data))
                self.course_vido_entry.configure(values=tuple(self.data))
            self.user_notice = self.account_info.get('user_notice', 'True')
            self.multi_device=self.account_info.get('multi_device',0)
            self.course_score_entry.set(self.account_info.get('cour', [''])[0])
            self.course_vido_entry.set(self.account_info.get('cour', [''])[0])
            self.all_cour=self.account_info.get('cour', [''])
            self.settings_panel.load_data(self.data)
            if self.account_info.get('timer_active'):
                self.timer_active = True
            self.timer_start_time = self.account_info.get('timer_start', '04:00:00')
            self.timer_end_time = self.account_info.get('timer_end', '03:00:00')
        except FileNotFoundError:
            pass


    # ========== 页面导航 ==========

    def delete_record(self, file_name):
        file_path = paths.record(f'《{self.dit[file_name][0].get()}》的{file_name}记录.txt')
        if os.path.exists(file_path):
            yes_no = tk.messagebox.askyesno('确认', '确定要删除吗？删除后无法恢复')
            if yes_no:
                os.remove(file_path)
                tk.messagebox.showinfo('提示', f'{file_name}记录文件已成功删除')
        else:
            tk.messagebox.showwarning('警告', f'指定的{file_name}记录文件不存在')
        self.show_record(file_name)

    def delete_huancun(self):
        try:
            folder_path = paths.record()
            tiku_files = [f for f in os.listdir(folder_path)
                          if f.endswith('.pkl') and os.path.isfile(os.path.join(folder_path, f))]
            for tiku_file in tiku_files:
                os.remove(os.path.join(folder_path, tiku_file))
            tk.messagebox.showinfo('提示', '缓存记录文件已成功删除')
        except:
            tk.messagebox.showwarning('警告', '删除失败')
        self.show_question_bank()

    # ========== 更新检查（委托） ==========

    def check_update(self):
        self.hint_label.grid(row=0, column=0, sticky=tk.N, pady=5, padx=5)
        self.hint_txt+=self._updater.check()
        self.hint_label.configure(text=self.hint_txt)


    # ========== 定时学习（委托） ==========
    def start_sign(self):
        accounts = self.config.list_accounts()
        if not accounts:
            tk.messagebox.showerror('警告', '还没有账号，请先在设置页面添加账号')
            return
        SignWindow(self.root, accounts, self.font, self.auto_sign,
                   self.button_color, self.button_hover_color, config=self.config)
        # tk.messagebox.showinfo('提示', '自动签到功能已下架，如有需要请联系作者邮箱2022865286@qq.com')
        # self._show_feedback_popup()
    def show_frame(self, frame):
        for f in self.frame_name_list[:8]:
            if f != frame:
                f.grid_forget()
            else:
                f.grid(row=1, column=1, sticky='nsew')

    def show_main(self):
        self.select_frame_by_name('主页')
        self.show_frame(self.main_frame)

    def show_record(self, name):
        self.select_frame_by_name(self.dit[name][1])
        self.dit[name][2].configure(state=tk.NORMAL)
        self.dit[name][2].delete('1.0', tk.END)
        if name == '学习':
            self.refresh_course_progress()
        try:
            with open(paths.record(f'《{self.dit[name][0].get()}》的{name}记录.txt'), 'r', encoding='utf-8') as f:
                content = f.read()
                self.dit[name][2].insert(tk.END, content)
        except FileNotFoundError:
            self.dit[name][2].insert(tk.END, f'暂未查询到《{self.dit[name][0].get()}》的{name}记录')
        self.show_frame(self.dit[name][3])
        self.dit[name][2].configure(state=tk.DISABLED)

    def refresh_course_progress(self):
        course_name = self.course_vido_entry.get()
        try:
            data = self.config.get_course_process()
            if course_name in data:
                done, total = data[course_name]
                pct = done / total if total > 0 else 0
                self.course_progress_label.configure(
                    text=f"课程进度: {pct * 100:.1f}% ",
                )
                self.course_progress_bar.set(pct)
            else:
                self.course_progress_label.configure(text="未查询到该课程的进度")
                self.course_progress_bar.set(0)
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            self.course_progress_label.configure(text="")
            self.course_progress_bar.set(0)

    def show_question_bank(self, *key):
        self.select_frame_by_name('题库查询')
        self.tiku_text.configure(state=tk.NORMAL)
        self.tiku_text.delete('1.0', tk.END)
        try:
            folder_path = paths.record()
            tiku_files = [f for f in os.listdir(folder_path)
                          if f.endswith('.pkl') and os.path.isfile(os.path.join(folder_path, f))]
            tiku_txt = ''
            for tiku_file in tiku_files:
                if 'ques1' not in tiku_file:
                    continue
                tiku_file_path = os.path.join(folder_path, tiku_file)
                data = pickle.load(open(tiku_file_path, 'rb'))['value']
                tiku_txt += f"问题: {data['question']}\n{data['options']}\n答案为：{data['answer']}\n\n"
            if tiku_txt == '':
                self.tiku_text.insert(tk.END, '暂无缓存的题目')
            self.tiku_text.insert(tk.END, tiku_txt)
        except FileNotFoundError:
            self.tiku_text.insert(tk.END, '暂无缓存的题目')
        self.show_frame(self.question_bank_frame)
        self.tiku_text.configure(state=tk.DISABLED)

    def show_error(self):
        self.select_frame_by_name('报错日志')
        try:
            self.error_text.configure(state=tk.NORMAL)
            with open(paths.root_data('error.log'), 'r', encoding='utf-8') as f:
                content = f.read()
                self.error_text.delete('1.0', tk.END)
                self.error_text.insert(tk.END, content)
        except FileNotFoundError:
            self.error_text.delete('1.0', tk.END)
            self.error_text.insert(tk.END, '暂无报错记录')
        self.show_frame(self.error_frame)
        self.error_text.configure(state=tk.DISABLED)

    def show_set(self):
        self.select_frame_by_name('设置')
        self.show_frame(self.set_frame)

    def show_money(self):
        self.select_frame_by_name('赞助作者')
        self.show_frame(self.money_frame)

    def show_help(self):
        self.select_frame_by_name('帮助')
        self.show_frame(self.help_frame)

    def select_frame_by_name(self, name):
        # 选中态用浅色底 + 主色文字，替代原先的整块高饱和填充
        self.current_page = name
        for i in range(len(self.button_name_list) - 2):
            txt = self.button_text_list[i]
            active = (name == txt)
            self.button_name_list[i].configure(
                fg_color=self.button_soft_color if active else "transparent",
                text_color=self.button_color if active else self.text_color)

    # ========== 日志面板 ==========

    def _ensure_log_box(self, account_id):
        """每个账号一个独立日志框，切换时只显示选中的那个。"""
        box = self.text_box_map.get(account_id)
        if box is None:
            box = ctk.CTkTextbox(self.log_host, border_width=1,
                                 border_color=self.border_color,
                                 fg_color=self.surface_color,
                                 height=self._box_height(),
                                 font=self.font)
            self.text_box_map[account_id] = box
        return box

    @staticmethod
    def _account_label(acc):
        name = acc.get('alias') or acc.get('phone') or '未命名'
        phone = acc.get('phone') or ''
        return f"{name}（{phone[-4:]}）" if phone else name

    def refresh_log_selector(self):
        accounts = self.config.list_accounts()
        running = set(self.runner.running_ids())
        pending = set(self.runner.pending_ids())
        current_id = self._log_index.get(self.log_select.get())
        self._log_index = {}
        values = []
        for acc in accounts:
            label = self._account_label(acc)
            if acc['id'] in running:
                label = '● ' + label + '（运行中）'
            elif acc['id'] in pending:
                label = '… ' + label + '（排队）'
            self._log_index[label] = acc['id']
            values.append(label)
        self.log_select.configure(values=values or ['（暂无账号）'])
        # 尽量保持当前选中的账号，别因为前缀变化把用户切走
        target = None
        if current_id:
            for label, aid in self._log_index.items():
                if aid == current_id:
                    target = label
                    break
        if target is None:
            target = values[0] if values else '（暂无账号）'
        self.log_select.set(target)
        self._switch_log()

    def _format_runtime_status(self, running, pending, limit):
        """拼并发状态文案：并发 2/3 ｜ 运行中：账号2、账号3 ｜ 排队：账号4"""
        name = lambda aid: self._alias_map.get(aid, aid)
        parts = ['并发 %d/%d' % (len(running), limit)]
        if running:
            parts.append('运行中：' + '、'.join(name(a) for a in running))
        if pending:
            parts.append('排队：' + '、'.join(name(a) for a in pending))
            if len(running) >= limit:
                parts.append('（已达并发上限，其余等待）')
        elif not running:
            parts.append('空闲')
        return ' ｜ '.join(parts)

    def _tick_runtime_status(self):
        """每秒刷新一次并发状态（谁在跑、谁在排队）。"""
        if not getattr(self, 'process_condition', False):
            return
        try:
            running = self.runner.running_ids()
            pending = self.runner.pending_ids()
            self.runtime_label.configure(
                text=self._format_runtime_status(running, pending, self.runner.max_concurrency))
        except Exception:
            pass
        try:
            self.root.after(1000, self._tick_runtime_status)
        except Exception:
            pass

    def _switch_log(self, _=None):
        account_id = self._log_index.get(self.log_select.get())
        if not account_id:
            return
        for box in self.text_box_map.values():
            box.grid_forget()
        box = self._ensure_log_box(account_id)
        box.grid(row=0, column=0, sticky="nsew")
        self.text_box = box
        try:
            self.hint_label.lift()
        except Exception:
            pass
        box.see("end")

    def _on_account_output(self, account_id, text, tag):
        # 主日志里留一份完整时间线（界面日志框关掉也不会丢）
        if account_id == '__default__':
            applog.info(text.rstrip())
        else:
            applog.child(self._alias_map.get(account_id, account_id), text)

        def insert():
            try:
                box = self._ensure_log_box(account_id)
                if tag:
                    box.tag_config(tag, foreground=tag)
                    box.insert("end", text, tag)
                else:
                    box.insert("end", text)
                if self._log_index.get(self.log_select.get()) == account_id:
                    box.see("end")
            except Exception:
                pass
        try:
            self.root.after(0, insert)
        except Exception:
            pass

    def _on_account_finish(self, account_id, code):
        logger.info('账号 %s 子进程结束，退出码 %s' % (account_id, code))
        applog.info('账号 %s 子进程结束，退出码 %s'
                    % (self._alias_map.get(account_id, account_id), code))

        def done():
            # 有账号结束 → 排队里的下一个会补上，这里把「运行中/排队」标记一起刷新
            try:
                self.refresh_log_selector()
            except Exception:
                pass
            if self.runner.active_count() == 0 and self.process_condition:
                self.process_condition = False
                self.start_button.grid(row=0, column=0, padx=5, pady=10)
                self.close_button.grid_forget()
                self.reopen_frame()
                try:
                    self.runtime_label.configure(text='空闲（全部结束）')
                except Exception:
                    pass
        try:
            self.root.after(0, done)
        except Exception:
            pass

    # ========== 学习控制 ==========

    def check_info(self):
        self.account_info = self.config.load_account()
        accounts = [a for a in self.config.list_accounts() if a['enabled']]
        if not accounts:
            tk.messagebox.showerror('警告', '没有启用的账号，请先在设置页面添加账号')
            return False
        if not any(a['phone'] for a in accounts):
            tk.messagebox.showerror('警告', '请先在设置页面填写手机号并保存')
            return False
        return True

    def start(self):
        if not self.check_info():
            return
        self.process_condition = True
        self.start_button.grid_forget()
        self.hint_label.grid_forget()
        self.close_button.grid(row=0, column=0, padx=5, pady=5)
        self.fold_frame()

        accounts = [a for a in self.config.list_accounts() if a['enabled'] and a['phone']]
        # 别名表用「所有账号」，这样排队/运行状态里都能显示名字而不是 id
        self._alias_map = {a['id']: (a.get('alias') or a['id'])
                           for a in self.config.list_accounts()}
        max_c = int(self.account_info.get('max_concurrency', 2) or 2)
        self.runner.set_concurrency(max_c)
        applog.ui('点击「开始学习」：启用账号 %d 个，并发上限 %d' % (len(accounts), max_c))
        started = self.runner.start([a['id'] for a in accounts])
        self.refresh_log_selector()
        self._on_account_output('__default__',
                                '已启动 %d 个账号，并发上限 %d\n'
                                % (started, self.runner.max_concurrency), None)
        logger.info('启动 %d 个账号，并发上限 %d' % (started, self.runner.max_concurrency))
        self._tick_runtime_status()

    def close(self):
        applog.ui('点击「结束学习」')
        self.process_condition = False
        self.start_button.grid(row=0, column=0, padx=5, pady=10)
        self.close_button.grid_forget()
        self.reopen_frame()
        self.runner.stop_all()
        try:
            self.runtime_label.configure(text='空闲（已停止）')
        except Exception:
            pass

    def _on_window_close(self):
        applog.ui('关闭主窗口')
        try:
            running = self.runner.active_count()
            if running:
                applog.info('关闭窗口时仍有 %d 个账号在跑，先停止子进程' % running)
            self.runner.stop_all()
        except Exception:
            applog.exception('关闭窗口时停止子进程失败')
        try:
            self.root.destroy()
        except Exception:
            pass

    def _on_ui_exception(self, exc, val, tb):
        """界面回调里未捕获的异常：记进程序日志（否则只在控制台一闪而过）。"""
        applog.exception('界面回调异常：%r' % (val,), exc_info=(exc, val, tb))
        logger.info('======================程序已成功关闭======================')

    def update_time(self):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        countdown_text = ""
        if self.timer_active:
            now = datetime.now()
            if self.process_condition:
                end_time = datetime.strptime(self.timer_end_time, "%H:%M:%S")
                end_datetime = now.replace(hour=end_time.hour, minute=end_time.minute, second=end_time.second,
                                           microsecond=0)
                if end_datetime < now:
                    end_datetime += timedelta(days=1)
                time_diff = (end_datetime - now).total_seconds()
                hours = int(time_diff // 3600)
                minutes = int((time_diff % 3600) // 60)
                seconds = int(time_diff % 60)
                countdown_text = f" | 距离结束学习还剩 {hours:02d}小时{minutes:02d}分钟{seconds:02d}秒"
            else:
                start_time = datetime.strptime(self.timer_start_time, "%H:%M:%S")
                start_datetime = now.replace(hour=start_time.hour, minute=start_time.minute, second=start_time.second,
                                             microsecond=0)
                if start_datetime < now:
                    start_datetime += timedelta(days=1)
                time_diff = (start_datetime - now).total_seconds()
                hours = int(time_diff // 3600)
                minutes = int((time_diff % 3600) // 60)
                seconds = int(time_diff % 60)
                countdown_text = f" | 距离开始学习还剩 {hours:02d}小时{minutes:02d}分钟{seconds:02d}秒"
        self.time_label.configure(text=f"当前时间: {current_time}{countdown_text}")
        self.root.after(1000, self.update_time)
        if self.timer_start_time in current_time and not self.process_condition and self.timer_active:
            self.start()
        if self.timer_end_time in current_time and self.process_condition and self.timer_active:
            self.close()

    def change_font(self):
        self.font = (self.settings_panel.font_entry.get(), int(self.settings_panel.size_entry.get()))
        self.style.configure('TLabelframe.Label', font=self.font)

        def update_font(widget):
            if isinstance(widget, (tk.Label, tk.Button, tk.Text, ttk.Label, tk.Entry, tk.LabelFrame)):
                widget.config(font=self.font)
            elif isinstance(widget, ttk.Checkbutton):
                style = ttk.Style()
                style.configure('TCheckbutton', font=self.font)
                widget.config(style='TCheckbutton')
            for child in widget.winfo_children():
                update_font(child)

        update_font(self.root)

    def change_text_box(self, all_cour, multi_device_check):
        """账号/课程变化后刷新日志切换下拉（多端学习已在多账号模式下禁用）。"""
        self.refresh_log_selector()

    def fold_frame(self):
        self.navigation_frame.grid_forget()
        self.open_frame.grid(row=0, column=0, rowspan=2, sticky="ns")

    def reopen_frame(self):
        self.open_frame.grid_forget()
        self.navigation_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")

    def change_appearance_mode_event(self, theme_name):
        p = theme.palette(theme_name)
        theme.set_current(theme_name)
        self.record_color_lst.append(theme_name)
        self.palette = p
        self.frame_fg_color = p['bg']
        self.surface_color = p['surface']
        self.border_color = p['border']
        self.text_color = p['text']
        self.text_muted_color = p['text_muted']
        self.button_color = p['accent']
        self.button_hover_color = p['accent_hover']
        self.button_soft_color = p['accent_soft']

        # 内容区用页面底色，导航栏用卡片色，形成层次
        for frame in self.frame_name_list:
            frame.configure(fg_color=p['bg'])
        self.navigation_frame.configure(fg_color=p['surface'])
        self.open_frame.configure(fg_color=p['surface'])
        self.root.configure(fg_color=p['bg'])

        self.style.configure('TLabelframe', background=p['bg'])
        self.style.configure('TLabelframe.Label', background=p['bg'])
        self.style.configure('TLabel', background=p['bg'])

        for box in (self.announcement_text, self.text_box, self.vido_text, self.score_txt,
                    self.tiku_text, self.help_txt, self.error_text):
            box.configure(fg_color=p['surface'], border_color=p['border'])

        for check in self.check_switch:
            check.configure(bg_color=p['surface'], progress_color=p['accent'])

        for button in self.button_name_list1:
            button.configure(fg_color=p['accent'], hover_color=p['accent_hover'])

        for combox in self.combobox_lst:
            combox.configure(dropdown_fg_color=p['surface'],
                             dropdown_hover_color=p['accent_soft'], bg_color='transparent',
                             button_color=p['accent'],
                             button_hover_color=p['accent_hover'])

        self.change_theme.configure(fg_color=p['surface_alt'], text_color=p['text'],
                                    dropdown_fg_color=p['surface'],
                                    button_color=p['border'],
                                    dropdown_hover_color=p['accent_soft'],
                                    button_hover_color=p['border'])

        self.sponsor_panel.update_theme([p['accent'], p['surface'], p['accent_hover']])
        self.course_progress_bar.configure(progress_color=p['accent'], fg_color=p['accent_soft'])
        self.course_progress_label.configure(text_color=p['accent'])

        self.navigation_frame_label.configure(text_color=p['text'])
        self.fold_button.configure(text_color=p['text_muted'], hover_color=p['accent_soft'])
        for btn in (self.delete_button1, self.delete_button2, self.delete_tiku_button):
            btn.configure(fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER)
        self.change_theme_value = self.change_theme.get()

        self.select_frame_by_name(getattr(self, 'current_page', '主页'))

def run_selftest() -> int:
    """打包后自检：确认单文件里该带的依赖/资源都在。

    结果写到 <数据目录>/selftest.log（窗口模式没有控制台，看不到 print）。
    用法：start.exe --selftest
    """
    import importlib
    import platform

    modules = [
        'main',
        'core.paths', 'core.runner', 'core.browser', 'core.config_manager',
        'core.log_export',
        'gui.theme', 'gui.setting_panel', 'gui.sign_window', 'gui.timer_window',
        'gui.log_export_dialog',
        'gui.tooltip', 'gui.update_checker', 'gui.sponsor_panel',
        'task.quiz_ai', 'task.do_work', 'task.watch_vido', 'task.watch_ppt',
        'task.watch_live', 'task.reading', 'task.play_audio', 'task.finish_dicussion',
        'task.tool.face', 'task.tool.no_secret', 'task.tool.ai_wen_da',
        'task.tool.DeepSeekAsk', 'task.tool.send_wx', 'task.tool.common',
        'task.tool.file',
        'task.xxt.sign', 'task.xxt.login', 'task.xxt.monitor', 'task.xxt.storage',
        'task.xxt.crypto', 'task.xxt.geocode', 'task.xxt.client',
        'task.xxt.courses', 'task.xxt.activity', 'task.xxt.constants',
        'selenium.webdriver.edge.webdriver', 'selenium.webdriver.chrome.webdriver',
        'customtkinter', 'PIL.Image', 'Crypto.Cipher.AES', 'numpy',
        'fontTools.ttLib', 'openai', 'requests', 'colorama', 'tkinter',
    ]
    assets = [
        ('tool', 'font_dict.txt'), ('tool', 'Help.txt'), ('tool', 'version_info'),
        ('tool', 'face_url.json'), ('tool', 'chrome-extension.crx'),
        ('tool', 'speed.crx'), ('tool', 'zyb-227372.crx'),
        ('img', 'menu.png'), ('img', 'xuexitong1 .ico'),
    ]
    lines = ['XuexitongShuake selftest',
             'frozen=%s' % paths.is_frozen(),
             'python=%s' % sys.version.split()[0],
             'platform=%s' % platform.platform(),
             'app_root=%s' % paths.app_root(),
             'assets=%s' % paths.ASSETS,
             'data_root=%s' % paths.DATA_ROOT,
             '']
    ok = True
    for name in modules:
        try:
            importlib.import_module(name)
            lines.append('OK    import %s' % name)
        except Exception as e:
            ok = False
            lines.append('FAIL  import %s :: %r' % (name, e))
    for parts in assets:
        target = paths.asset(*parts)
        exists = os.path.exists(target)
        ok = ok and exists
        lines.append('%s  asset %s' % ('OK   ' if exists else 'FAIL ', '/'.join(parts)))
    # 驱动情况（新电脑第一次运行最容易卡在这里）
    try:
        from core import driver as driver_ext
        for name in ('edge', 'chrome'):
            try:
                lines.append('INFO  %s version=%s driver=%s' % (
                    name, driver_ext.browser_version(name),
                    driver_ext.resolve(name, '')))
            except Exception as e:
                lines.append('INFO  %s detect failed :: %r' % (name, e))
    except Exception as e:
        lines.append('INFO  driver module failed :: %r' % (e,))
    lines.append('')
    lines.append('RESULT=%s' % ('PASS' if ok else 'FAIL'))
    text = '\n'.join(lines) + '\n'
    try:
        with open(paths.root_data('selftest.log'), 'w', encoding='utf-8') as f:
            f.write(text)
    except OSError:
        pass
    try:
        print(text, flush=True)
    except Exception:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    if sys.stdout is None or sys.stderr is None:
        # --noconsole 打包后没有控制台；导入某些模块会包装 sys.stdout，先补一个空流
        _devnull = open(os.devnull, 'w', encoding='utf-8')
        sys.stdout = sys.stdout or _devnull
        sys.stderr = sys.stderr or _devnull
    if "--selftest" in sys.argv:
        prepare_runtime()
        applog.setup('--selftest')
        code = run_selftest()
        applog.info('自检结果：%s' % ('PASS' if code == 0 else 'FAIL'))
        sys.exit(code)
    if "--core" in sys.argv:
        # 被主界面以子进程方式拉起：只跑学习核心，不建界面；输出由主进程写进程序日志
        prepare_runtime()
        import main as core
        core.run_main()
    elif "--sign" in sys.argv:
        # 自动签到的子进程入口：一个账号一个进程，XXT_HOME 由主进程指定
        prepare_runtime()
        applog.setup('--sign')
        from gui.sign_window import sign_once
        sys.exit(sign_once())
    else:
        applog.setup()
        start = Start()
        start.root.mainloop()