# -*- coding: utf-8 -*-
"""主窗口：框架、标题栏、标签页、窗口行为、保存与快捷键。"""

import ctypes
import os
from datetime import datetime

import tkinter as tk
from tkinter import font as tkfont

from .config import (APP_NAME, APP_TITLE, C, DEF_H, DEF_W, FONT_FAMILY,
                     HDR_H, IS_WIN, MIN_H, MIN_W, STA_H, TAB_H)
from .notes_page import NotePageMixin
from .plan_page import PlanPageMixin
from .storage import DATA_FILE, load_data, save_data
from .widgets import FlatButton, Tooltip


class PinJot(NotePageMixin, PlanPageMixin):
    """悬浮便签主窗口"""

    def __init__(self):
        self.data = load_data()
        self.ui = self.data["ui"]
        self._save_job = None
        self._dirty = False
        self._loading = False
        self._focus_id = None
        self._tab_ready = False

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self._pick_font()
        self._init_fonts()
        self._init_window()
        self._build_ui()
        self._bind_keys()
        self._load_notes()
        self._render_tasks()
        self._restore_ui()
        self._init_hotkey()

    # ------------------------------------------------------------------ #
    # 初始化
    # ------------------------------------------------------------------ #
    def _pick_font(self):
        global FONT_FAMILY
        try:
            fams = set(tkfont.families(self.root))
        except Exception:
            fams = set()
        for name in ("Microsoft YaHei UI", "微软雅黑",
                     "Microsoft YaHei", "Segoe UI"):
            if name in fams:
                FONT_FAMILY = name
                break

    def _init_fonts(self):
        s = int(self.ui.get("font_size", 10))
        f = FONT_FAMILY
        self.f_body = (f, s)
        self.f_small = (f, s - 2)
        self.f_tiny = (f, s - 3)
        self.f_bold = (f, s, "bold")
        self.f_title = (f, s + 1, "bold")

    def _init_window(self):
        r = self.root
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.minsize(MIN_W, MIN_H)
        r.configure(bg=C["border"])
        try:
            r.attributes("-alpha", float(self.ui.get("opacity", 1.0)))
        except Exception:
            pass
        self._round_corners()

    def _round_corners(self):
        """Win11 圆角，失败则忽略"""
        if not IS_WIN:
            return
        try:
            hwnd = (ctypes.windll.user32.GetParent(self.root.winfo_id())
                    or self.root.winfo_id())
            pref = ctypes.c_int(2)          # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # 界面骨架
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        # 外框：root 的 bg 当作 1px 描边
        self.outer = tk.Frame(self.root, bg=C["bg"])
        self.outer.pack(fill="both", expand=True, padx=1, pady=1)

        self._build_header()
        self._build_tabs()
        self._build_status()      # 先占住底部，再让正文区填充剩余空间

        self.body = tk.Frame(self.outer, bg=C["bg"])
        self.body.pack(fill="both", expand=True)

        self.page_note = tk.Frame(self.body, bg=C["bg"])
        self.page_plan = tk.Frame(self.body, bg=C["bg"])
        self._build_note_page(self.page_note)
        self._build_plan_page(self.page_plan)
        self.page_note.pack(fill="both", expand=True)

        self._build_grip()
        self._build_menu()

    def _build_header(self):
        h = tk.Frame(self.outer, bg=C["header"], height=HDR_H)
        h.pack(fill="x")
        h.pack_propagate(False)

        self.btn_pin = FlatButton(h, "📌", command=self.toggle_topmost,
                                  bg=C["header"], fg=C["pin"],
                                  hover=C["hover"], font=(FONT_FAMILY, 11),
                                  padx=8)
        self.btn_pin.pack(side="left", fill="y")
        Tooltip(self.btn_pin, "置顶：让便签钉在所有窗口最上层")

        self.lbl_title = tk.Label(h, text=APP_TITLE, bg=C["header"],
                                  fg=C["text"], font=self.f_title, anchor="w")
        self.lbl_title.pack(side="left", padx=(2, 0))

        self.btn_close = FlatButton(h, "✕", command=self.on_close,
                                    bg=C["header"], fg=C["muted"],
                                    hover="#F3D9D4", font=self.f_body, padx=9)
        self.btn_close.pack(side="right", fill="y")
        Tooltip(self.btn_close, "关闭（自动保存）")

        self.btn_min = FlatButton(h, "—", command=self.toggle_collapse,
                                  bg=C["header"], fg=C["muted"],
                                  font=self.f_body, padx=9)
        self.btn_min.pack(side="right", fill="y")
        Tooltip(self.btn_min, "折叠 / 展开")

        # 拖动
        for w in (h, self.lbl_title):
            w.bind("<Button-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<Double-Button-1>", lambda e: self.toggle_collapse())
        self.root.bind("<Button-1>", self._drag_start, add="+")
        self.root.bind("<B1-Motion>", self._drag_move, add="+")

    def _build_tabs(self):
        t = tk.Frame(self.outer, bg=C["bg"], height=TAB_H)
        t.pack(fill="x")
        t.pack_propagate(False)
        self.tab_bar = t

        inner = tk.Frame(t, bg=C["bg"])
        inner.pack(side="left", padx=6, pady=(4, 0))

        self.tab_btns = {}
        for key, label in (("note", "便签"), ("plan", "计划")):
            b = FlatButton(inner, label,
                           command=lambda k=key: self.switch_tab(k),
                           bg=C["bg"], fg=C["muted"], hover=C["bg"],
                           font=self.f_body, padx=10, pady=2)
            b.pack(side="left")
            self.tab_btns[key] = b

        self.lbl_hint = tk.Label(t, text="", bg=C["bg"], fg=C["faint"],
                                 font=self.f_tiny)
        self.lbl_hint.pack(side="right", padx=8)

    def switch_tab(self, key):
        if key == self.ui.get("tab") and self._tab_ready:
            return
        self._tab_ready = True
        self.ui["tab"] = key
        self.page_note.pack_forget()
        self.page_plan.pack_forget()
        (self.page_note if key == "note" else self.page_plan).pack(
            fill="both", expand=True)
        for k, b in self.tab_btns.items():
            if k == key:
                b.configure(fg=C["accent"], font=self.f_bold)
                b._bg = C["accent_s"]
                b.configure(bg=C["accent_s"])
            else:
                b.configure(fg=C["muted"], font=self.f_body)
                b._bg = C["bg"]
                b.configure(bg=C["bg"])
        if key == "note":
            if self._note_view == "edit":
                self.txt.focus_set()
            else:
                self._render_note_cards()
        self.schedule_save()

    # -- 状态栏 / 缩放手柄 / 右键菜单 ----------------------------------- #
    def _build_status(self):
        self.status = tk.Frame(self.outer, bg=C["bg"], height=STA_H)
        self.status.pack(fill="x", side="bottom")
        self.status.pack_propagate(False)
        self.lbl_status = tk.Label(self.status, text="就绪", bg=C["bg"],
                                   fg=C["faint"], font=self.f_tiny, anchor="w")
        self.lbl_status.pack(side="left", padx=9)

    def _build_grip(self):
        self.grip = tk.Label(self.outer, text="◢", bg=C["bg"], fg=C["faint"],
                             font=(FONT_FAMILY, 9), cursor="size_nw_se")
        self.grip.place(relx=1.0, rely=1.0, anchor="se")
        self.grip.bind("<Button-1>", self._resize_start)
        self.grip.bind("<B1-Motion>", self._resize_move)
        Tooltip(self.grip, "拖动缩放窗口")

    def _build_menu(self):
        m = tk.Menu(self.root, tearoff=0, bg=C["card"], fg=C["text"],
                    activebackground=C["accent_s"],
                    activeforeground=C["accent"], bd=0, relief="flat",
                    font=self.f_body)
        self.menu = m
        m.add_command(label="📌  置顶开关", command=self.toggle_topmost)
        m.add_command(label="↕  折叠 / 展开", command=self.toggle_collapse)
        m.add_separator()
        for pct in (100, 92, 85, 75):
            m.add_command(label=f"透明度 {pct}%",
                          command=lambda p=pct: self.set_opacity(p / 100))
        m.add_separator()
        for size in (9, 10, 11, 12):
            m.add_command(label=f"字号 {size}",
                          command=lambda s=size: self.set_font_size(s))
        m.add_separator()
        m.add_command(label="🧹  清空当前便签内容", command=self.clear_note)
        m.add_command(label="📂  打开数据文件夹", command=self.open_data_dir)
        m.add_separator()
        m.add_command(label="❓  快捷键说明", command=self.show_help)
        m.add_command(label="✕  退出", command=self.on_close)

        for w in (self.root, self.outer, self.lbl_title, self.status):
            w.bind("<Button-3>", self._popup_menu)

    def _popup_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    # ------------------------------------------------------------------ #
    # 窗口行为
    # ------------------------------------------------------------------ #
    def _drag_start(self, event):
        if event.widget is self.grip:
            return
        self._dx = event.x_root - self.root.winfo_x()
        self._dy = event.y_root - self.root.winfo_y()

    def _drag_move(self, event):
        if not hasattr(self, "_dx") or event.widget is self.grip:
            return
        # 文本域、输入框里拖拽是选字，不移动窗口
        w = event.widget
        while w is not None:
            if isinstance(w, (tk.Text, tk.Entry)):
                return
            if w is self.root:
                break
            w = getattr(w, "master", None)
        self.root.geometry(
            f"+{event.x_root - self._dx}+{event.y_root - self._dy}")

    def _resize_start(self, event):
        self._rw = self.root.winfo_width()
        self._rh = self.root.winfo_height()
        self._rx = event.x_root
        self._ry = event.y_root

    def _resize_move(self, event):
        w = max(MIN_W, self._rw + (event.x_root - self._rx))
        h = max(MIN_H, self._rh + (event.y_root - self._ry))
        self.root.geometry(f"{w}x{h}")

    def set_topmost(self, value):
        value = bool(value)
        self.ui["topmost"] = value
        self.root.attributes("-topmost", value)
        self.btn_pin.set_fg(C["pin"] if value else C["faint"])
        self.btn_pin.configure(text="📌" if value else "📍")
        self.lbl_hint.configure(text="已置顶" if value else "未置顶")
        self.schedule_save()

    def toggle_topmost(self):
        self.set_topmost(not self.ui.get("topmost", True))
        self.set_status("已钉在最上层" if self.ui["topmost"]
                        else "已取消置顶（Ctrl+Alt+N 可唤回）")

    def toggle_collapse(self):
        collapsed = not bool(self.ui.get("collapsed", False))
        self.ui["collapsed"] = collapsed
        if collapsed:
            self._expand_h = self.root.winfo_height()
            self.body.pack_forget()
            self.status.pack_forget()
            self.grip.place_forget()
            self.root.geometry(f"{self.root.winfo_width()}x{HDR_H + TAB_H + 2}")
        else:
            h = getattr(self, "_expand_h", DEF_H)
            self.status.pack(fill="x", side="bottom", before=self.body)
            self.body.pack(fill="both", expand=True)
            self.grip.place(relx=1.0, rely=1.0, anchor="se")
            self.root.geometry(f"{self.root.winfo_width()}x{max(MIN_H, h)}")
        self.set_status("已折叠" if collapsed else "就绪")
        self.schedule_save()

    def set_opacity(self, value):
        self.ui["opacity"] = value
        try:
            self.root.attributes("-alpha", value)
        except Exception:
            pass
        self.set_status(f"透明度 {int(value * 100)}%")
        self.schedule_save()

    def set_font_size(self, size):
        self.ui["font_size"] = size
        self._init_fonts()
        self.lbl_title.configure(font=self.f_title)
        self.lbl_status.configure(font=self.f_tiny)
        self.lbl_hint.configure(font=self.f_tiny)
        self.lbl_prog.configure(font=self.f_small)
        self.txt.configure(font=self.f_body)
        self.ent_title.configure(font=self.f_bold)
        for k, b in self.tab_btns.items():
            b.configure(font=self.f_bold if k == self.ui.get("tab")
                        else self.f_body)
        self._render_tasks()
        self.set_status(f"字号 {size}")
        self.schedule_save()

    def show_help(self):
        from tkinter import messagebox
        messagebox.showinfo(
            "快捷键与操作",
            "📌  左上角图钉：置顶 / 取消置顶\n"
            "—   折叠窗口（只剩标题栏）\n"
            "◢   右下角拖动缩放\n"
            "右键  菜单：透明度、字号、数据目录\n\n"
            "Ctrl + Alt + N   显示 / 隐藏窗口\n"
            "Ctrl + N         新建便签\n"
            "Ctrl + S         立即保存\n"
            "Ctrl + Z         撤销输入\n"
            "双击任务序号     重新编辑\n\n"
            f"数据存放：{DATA_FILE}",
            parent=self.root)

    def open_data_dir(self):
        try:
            os.startfile(str(DATA_FILE.parent))
        except Exception as exc:
            self.set_status(f"打开失败: {exc}")

    # ------------------------------------------------------------------ #
    # 保存 / 状态
    # ------------------------------------------------------------------ #
    def set_status(self, text):
        now = datetime.now().strftime("%H:%M")
        self.lbl_status.configure(text=f"{text} · {now}")

    def schedule_save(self):
        self._dirty = True
        if self._save_job:
            try:
                self.root.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.root.after(600, self.flush_save)

    def flush_save(self, *_):
        self._save_job = None
        if not self._dirty:
            return
        try:
            self.sync_note()
            self.ui.update({
                "x": self.root.winfo_x(), "y": self.root.winfo_y(),
                "w": self.root.winfo_width(), "h": self.root.winfo_height(),
            })
            save_data(self.data)
            self._dirty = False
            self.set_status("已保存")
        except Exception as exc:
            self.set_status(f"保存失败 {exc}")

    # ------------------------------------------------------------------ #
    # 全局快捷键 Ctrl+Alt+N
    # ------------------------------------------------------------------ #
    def _init_hotkey(self):
        if not IS_WIN:
            return
        try:
            from ctypes import wintypes
            self._user32 = ctypes.windll.user32
            u = self._user32
            self._hotkey_id = 0xB1A
            mod_alt, mod_ctrl, vk_n = 0x0001, 0x0002, 0x4E
            if not u.RegisterHotKey(None, self._hotkey_id,
                                    mod_alt | mod_ctrl, vk_n):
                return
            u.PeekMessageW.argtypes = [
                ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                wintypes.UINT, wintypes.UINT, wintypes.UINT]
            self._msg = wintypes.MSG()
            self._hotkey_on = True
            self._poll_hotkey()
        except Exception:
            self._hotkey_on = False

    def _poll_hotkey(self):
        try:
            while self._user32.PeekMessageW(ctypes.byref(self._msg), None,
                                            0x0312, 0x0312, 1):
                self.toggle_visible()
        except Exception:
            pass
        self.root.after(150, self._poll_hotkey)

    def toggle_visible(self):
        if self.root.state() == "withdrawn" or not self.root.winfo_viewable():
            self.root.deiconify()
            self.root.lift()
            if self.ui.get("topmost", True):
                self.root.attributes("-topmost", True)
        else:
            self.root.withdraw()

    # ------------------------------------------------------------------ #
    # 键盘 / 恢复 / 关闭
    # ------------------------------------------------------------------ #
    def _bind_keys(self):
        self.root.bind("<Control-s>", lambda e: self.flush_save() or "break")
        self.root.bind("<Control-n>", lambda e: self.new_note() or "break")
        self.root.bind("<Escape>", lambda e: self.txt.focus_set())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _restore_ui(self):
        u = self.ui
        w = int(u.get("w") or DEF_W)
        h = int(u.get("h") or DEF_H)
        w, h = max(MIN_W, w), max(MIN_H, h)
        sw, sh = (self.root.winfo_screenwidth(),
                  self.root.winfo_screenheight())
        x, y = u.get("x"), u.get("y")
        if x is None or not (0 <= x <= sw - 40) or not (0 <= y <= sh - 40):
            x, y = sw - w - 60, 90
        x = min(max(x, 0), sw - 60)
        y = min(max(y, 0), sh - 40)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.switch_tab(u.get("tab", "note"))
        self.set_topmost(bool(u.get("topmost", True)))
        try:
            self.root.attributes("-alpha", float(u.get("opacity", 1.0)))
        except Exception:
            pass
        self.ui["opacity"] = float(u.get("opacity", 1.0))
        self.set_opacity(self.ui["opacity"])
        self.root.update_idletasks()
        if u.get("collapsed"):
            self.root.after(60, self.toggle_collapse)
        self.root.after(200, lambda: (self.txt.focus_set(), self.root.lift()))
        self.set_status("已就绪")

    def on_close(self):
        try:
            self.sync_note()
            self.ui.update({
                "x": self.root.winfo_x(), "y": self.root.winfo_y(),
                "w": self.root.winfo_width(), "h": self.root.winfo_height(),
            })
            save_data(self.data)
        finally:
            try:
                if getattr(self, "_hotkey_on", False):
                    self._user32.UnregisterHotKey(None, self._hotkey_id)
            except Exception:
                pass
            self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    """程序入口：先设置 DPI 感知，再启动窗口。"""
    if IS_WIN:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    PinJot().run()
