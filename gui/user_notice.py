"""用户须知弹窗"""
import customtkinter as ctk

from gui import theme

NOTICE_TEXT = """欢迎使用课程学习助手！
    【重要声明】
    1. 本程序仅供个人学习交流使用，不得用于任何商业用途。
    2. 使用本程序产生的任何后果由使用者自行承担，开发者不承担任何责任。
    3. 请遵守学校及平台的有关规定，合理使用本程序。
    4. 请勿将本程序用于任何违规用途。
    5. 开发者保留对本程序的最终解释权。
    【使用说明】
    1. 建议在稳定的网络环境下使用本程序。
    2. 如遇到问题，请查看帮助文档或联系作者。
    3. 请合理设置播放速度，避免影响正常学习。

    请您仔细阅读以上内容，使用本程序即表示您同意遵守上述条款。"""


class UserNotice:
    def __init__(self, root, on_confirm, on_cancel):
        self.root = root
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.remaining_time = 10

    def show(self):
        p = theme.palette()
        notice_window = ctk.CTkToplevel(self.root)
        notice_window.title("用户须知")
        notice_window.resizable(False, False)
        notice_window.transient(self.root)
        notice_window.grab_set()
        notice_window.wm_attributes("-topmost", True)
        notice_window.configure(fg_color=p['bg'])

        text_widget = ctk.CTkTextbox(notice_window, wrap="word", width=620, height=400,
                                     font=theme.font(12), fg_color=p['surface'],
                                     border_width=1, border_color=p['border'],
                                     text_color=p['text'], corner_radius=8)
        text_widget.insert("end", NOTICE_TEXT)
        text_widget.configure(state="disabled")
        text_widget.grid(row=0, column=0, padx=16, pady=16)

        button_frame = ctk.CTkFrame(notice_window, fg_color="transparent")
        button_frame.grid(row=1, column=0, pady=(0, 16))

        self.confirm_button = ctk.CTkButton(
            button_frame, text=f"确认 ({self.remaining_time}s)", width=110, height=34,
            font=theme.font(12), state="disabled",
            fg_color=p['accent'], hover_color=p['accent_hover'],
            command=lambda: self._confirm(notice_window))
        cancel_button = ctk.CTkButton(
            button_frame, text="取消", width=90, height=34, font=theme.font(12),
            fg_color="transparent", text_color=p['text_muted'],
            hover_color=p['surface_alt'], border_width=1, border_color=p['border'],
            command=lambda: self._cancel(notice_window))

        self.confirm_button.pack(side="left", padx=8)
        cancel_button.pack(side="left", padx=8)

        self._countdown(notice_window)

        notice_window.update_idletasks()
        x = (notice_window.winfo_screenwidth() // 2) - (notice_window.winfo_width() // 2)
        y = (notice_window.winfo_screenheight() // 2) - (notice_window.winfo_height() // 2)
        notice_window.geometry(f"+{x}+{y}")
        notice_window.protocol("WM_DELETE_WINDOW", lambda: None)

    def _countdown(self, window):
        if self.remaining_time > 0:
            self.confirm_button.configure(text=f"确认 ({self.remaining_time}s)")
            self.remaining_time -= 1
            window.after(1000, lambda: self._countdown(window))
        else:
            self.confirm_button.configure(text="确认", state="normal")

    def _confirm(self, window):
        window.destroy()
        self.on_confirm()

    def _cancel(self, window):
        window.destroy()
        self.on_cancel()
