# -*- coding: utf-8 -*-
"""「导出完整日志」弹窗：选一天 -> 后台导出 -> 生成一个 zip 单文件。

界面只负责交互：日期 / 输出目录 / 是否带图片题截图，以及进度与结果提示。
真正的收集、按日过滤、脱敏、打包都在 core.log_export，纯桩测试不需要起界面。

线程约束：Tk 的控件只能在主线程碰。后台线程只写结果变量，
由 self.after 轮询回主线程刷新 UI，不从子线程直接调 after/configure。
"""
from __future__ import annotations

import os
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core import applog, log_export
from gui import theme


class LogExportDialog(ctk.CTkToplevel):

    WIDTH, HEIGHT = 580, 410

    def __init__(self, parent):
        super().__init__(parent)
        p = theme.palette()
        font = theme.font(12)
        self._busy = False
        self._dead = False
        self._result = None

        self.title('导出完整日志')
        self.resizable(False, False)
        self.transient(parent)
        self.configure(fg_color=p['bg'])
        self.protocol('WM_DELETE_WINDOW', self._on_close)

        self.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.WIDTH) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.HEIGHT) // 3)
        self.geometry('%dx%d+%d+%d' % (self.WIDTH, self.HEIGHT, x, y))

        head = ctk.CTkFrame(self, fg_color='transparent')
        head.pack(fill='x', padx=18, pady=(16, 6))
        ctk.CTkLabel(head, text='导出完整日志', font=theme.font(15, 'bold'),
                     text_color=p['text']).pack(anchor='w')
        ctk.CTkLabel(
            head, justify='left', wraplength=540, font=font,
            text_color=p['text_muted'],
            text='把这一天的程序日志、账号明细、报错、签到日志、诊断截图、学习记录'
                 '与脱敏配置，合并导出为一个 zip 文件。\n'
                 '包内另有一份 00_FULL_LOG_<日期>.txt：所有文字日志已合并成一份，可直接发给开发者。',
        ).pack(anchor='w', pady=(8, 0))

        form = ctk.CTkFrame(self, fg_color=p['surface'], corner_radius=10)
        form.pack(fill='x', padx=18, pady=10)
        form.columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text='日期', font=font,
                     text_color=p['text']).grid(row=0, column=0, padx=(14, 8), pady=(14, 6), sticky='w')
        days = log_export.recent_days(14)
        self.day_box = ctk.CTkComboBox(
            form, values=days, font=font, width=190,
            fg_color=p['surface'], border_color=p['border'], button_color=p['accent'],
            button_hover_color=p['accent_hover'], text_color=p['text'],
            dropdown_fg_color=p['surface'], dropdown_hover_color=p['accent_soft'],
            dropdown_text_color=p['text'])
        self.day_box.set(days[0])
        self.day_box.grid(row=0, column=1, columnspan=2, sticky='w', pady=(14, 6))

        ctk.CTkLabel(form, text='保存到', font=font,
                     text_color=p['text']).grid(row=1, column=0, padx=(14, 8), pady=6, sticky='w')
        self.dir_entry = ctk.CTkEntry(form, font=font, fg_color=p['surface'],
                                      border_color=p['border'], text_color=p['text'])
        self.dir_entry.insert(0, log_export.default_out_dir())
        self.dir_entry.grid(row=1, column=1, sticky='ew', padx=(0, 6), pady=6)
        ctk.CTkButton(form, text='浏览…', width=72, font=font,
                      fg_color=p['accent_soft'], hover_color=p['border'],
                      text_color=p['text'], command=self._pick_dir
                      ).grid(row=1, column=2, padx=(0, 14), pady=6)

        self.shot_var = ctk.IntVar(value=0)
        ctk.CTkCheckBox(form, text='包含图片题截图（体积较大，默认不含）',
                        variable=self.shot_var, font=font, text_color=p['text'],
                        fg_color=p['accent'], hover_color=p['accent_hover'],
                        border_color=p['border']
                        ).grid(row=2, column=1, columnspan=2, sticky='w', pady=(2, 14))

        self.status = ctk.CTkLabel(self, text='默认导出今天；密码、API Key 与手机号已自动脱敏。',
                                   font=font, text_color=p['text_muted'],
                                   wraplength=540, justify='left')
        self.status.pack(fill='x', padx=18, pady=(2, 0))

        bar = ctk.CTkFrame(self, fg_color='transparent')
        bar.pack(fill='x', padx=18, pady=(12, 16))
        ctk.CTkButton(bar, text='取消', width=100, font=font,
                      fg_color=p['surface_alt'], hover_color=p['border'],
                      text_color=p['text'], command=self._on_close).pack(side='right', padx=(8, 0))
        self.ok_btn = ctk.CTkButton(bar, text='开始导出', width=124, font=font,
                                    fg_color=p['accent'], hover_color=p['accent_hover'],
                                    text_color='#FFFFFF', command=self._start)
        self.ok_btn.pack(side='right')

        self.after(120, self.grab_set)

    # ------------------------------------------------------------ 交互

    def _pick_dir(self):
        current = self.dir_entry.get().strip() or log_export.default_out_dir()
        chosen = filedialog.askdirectory(parent=self, initialdir=current,
                                         title='选择日志包保存位置')
        if chosen:
            self.dir_entry.delete(0, 'end')
            self.dir_entry.insert(0, chosen)

    def _start(self):
        if self._busy:
            return
        day = self.day_box.get().strip()
        out_dir = self.dir_entry.get().strip() or log_export.default_out_dir()
        self._busy = True
        self._result = None
        self.ok_btn.configure(state='disabled', text='导出中…')
        self.status.configure(text='正在收集并打包 %s 的日志，请稍候…' % day)

        def worker():
            applog.ui('点击「导出完整日志」：日期=%s 输出目录=%s' % (day, out_dir))
            try:
                result = log_export.export_day_logs(
                    day=day, out_dir=out_dir,
                    with_question_shots=bool(self.shot_var.get()))
            except Exception as e:                 # 兜底：不让后台线程静默死掉
                applog.exception('完整日志导出异常')
                result = {'ok': False, 'error': repr(e), 'warnings': [], 'entries': []}
            if result.get('ok'):
                applog.info('完整日志导出成功：%s（%d 字节，%d 个条目）'
                            % (result.get('zip_path', ''), result.get('size', 0),
                               len(result.get('entries', []))))
            else:
                applog.error('完整日志导出失败：%s' % result.get('error', '未知错误'))
            self._result = result               # 只写变量，UI 由主线程轮询刷新

        threading.Thread(target=worker, daemon=True).start()
        self.after(120, self._poll)

    def _poll(self):
        if self._dead:
            return
        if self._result is None:
            self.after(120, self._poll)
            return
        self._finish(self._result)

    def _finish(self, result):
        self._busy = False
        if self._dead:
            return
        try:
            self.ok_btn.configure(state='normal', text='开始导出')
        except Exception:
            return
        p = theme.palette()
        if not result.get('ok'):
            msg = result.get('error') or '未知错误'
            self.status.configure(text='导出失败：%s' % msg, text_color=theme.DANGER)
            messagebox.showerror('导出失败', msg, parent=self)
            return

        path = result.get('zip_path', '')
        size_mb = result.get('size', 0) / 1048576.0
        count = len(result.get('entries', []))
        warnings = result.get('warnings') or []
        self.status.configure(text='已生成：%s（%.2f MB，%d 个条目）' % (path, size_mb, count),
                              text_color=p['accent'])
        lines = ['已导出为一个单独文件：', path, '',
                 '大小：%.2f MB' % size_mb, '包内条目：%d 个' % count,
                 '包内 00_FULL_LOG_%s.txt 是所有文字日志的合并版。' % result.get('day', '')]
        if warnings:
            lines += ['', '提示：'] + ['· ' + w for w in warnings[:5]]
        messagebox.showinfo('导出完成', '\n'.join(lines), parent=self)
        if messagebox.askyesno('导出完成', '是否打开所在文件夹？', parent=self):
            try:
                os.startfile(os.path.dirname(path))
            except Exception:
                pass

    def _on_close(self):
        self._dead = True
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


def open_export_dialog(parent):
    """供 start.py 调用；返回弹窗实例（一般不需要持有）。"""
    return LogExportDialog(parent)
