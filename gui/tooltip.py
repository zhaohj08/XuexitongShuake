""""悬停提示组件"""
import tkinter as tk

from gui import theme


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind('<Enter>', self.show_tip)
        self.widget.bind('<Leave>', self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window:
            return
        p = theme.palette()
        x = self.widget.winfo_pointerx() + 12
        y = self.widget.winfo_pointery() + 14
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        self.tip_window.wm_attributes("-topmost", True)
        # 用外层底色做出 1px 描边，替代原先的 #ffffe0 黄底系统提示
        self.tip_window.configure(bg=p['border'])
        tk.Label(self.tip_window, text=self.text, justify='left',
                 bg=p['surface'], fg=p['text'], padx=10, pady=6,
                 font=(theme.FONT_FAMILY, 9)).pack(padx=1, pady=1)

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

    def set_text(self, new_text):
        self.text = new_text
