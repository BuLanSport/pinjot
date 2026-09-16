# -*- coding: utf-8 -*-
"""通用小部件：扁平按钮、悬停提示。"""

import tkinter as tk

from .config import C, FONT_FAMILY


class FlatButton(tk.Label):
    """扁平图标按钮：悬停变色，点击回调"""

    def __init__(self, master, text="", command=None, bg=None, fg=None,
                 hover=None, font=None, padx=7, pady=3, cursor="hand2", **kw):
        self._bg = bg or master.cget("bg")
        self._hover = hover or C["hover"]
        self._fg = fg or C["text"]
        self._command = command
        super().__init__(master, text=text, bg=self._bg, fg=self._fg,
                         font=font, padx=padx, pady=pady, cursor=cursor, **kw)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)

    # -- 外观 ------------------------------------------------------------- #
    def set_fg(self, color):
        self._fg = color
        self.configure(fg=color)

    def set_hover(self, color):
        self._hover = color

    # -- 事件 ------------------------------------------------------------- #
    def _enter(self, _=None):
        if self._command:
            self.configure(bg=self._hover)

    def _leave(self, _=None):
        self.configure(bg=self._bg)

    def _press(self, _=None):
        if self._command:
            self.configure(bg=self._hover)

    def _release(self, _=None):
        self.configure(bg=self._bg)
        if self._command:
            self._command()


class Tooltip:
    """悬停提示气泡"""

    def __init__(self, widget, text, delay=420):
        self.widget, self.text, self.delay = widget, text, delay
        self.tip = None
        self._after = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _=None):
        self._cancel()
        self._after = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after:
            try:
                self.widget.after_cancel(self._after)
            except Exception:
                pass
            self._after = None

    def _show(self):
        if self.tip or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            self.tip = tk.Toplevel(self.widget)
            self.tip.wm_overrideredirect(True)
            self.tip.wm_attributes("-topmost", True)
            tk.Label(self.tip, text=self.text, bg="#33312D", fg="#F7F4EE",
                     padx=8, pady=4, font=(FONT_FAMILY, 8),
                     justify="left").pack()
            self.tip.wm_geometry(f"+{x}+{y}")
        except Exception:
            self.tip = None

    def _hide(self, _=None):
        self._cancel()
        if self.tip:
            try:
                self.tip.destroy()
            except Exception:
                pass
            self.tip = None
