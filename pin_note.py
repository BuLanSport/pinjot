# -*- coding: utf-8 -*-
"""
PinNote —— 桌面悬浮便签（单文件版）

功能：
  · 无边框小巧悬浮窗，拖标题栏移动、右下角拖拽缩放
  · 📌 一键置顶，钉在所有窗口最上层
  · 「便签」多笔记管理，边打字边自动保存
  · 「计划」待办清单，勾选完成 / 进度条 / 双击改文字
  · 窗口位置、大小、折叠状态、透明度自动记忆
  · 全局快捷键 Ctrl+Alt+N 显示 / 隐藏

依赖：仅需 Python 3 自带的 tkinter，无需安装任何第三方库。
"""

import ctypes
import json
import os
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import font as tkfont

# --------------------------------------------------------------------------- #
# 常量与配色
# --------------------------------------------------------------------------- #

APP_NAME = "PinNote"
APP_TITLE = "我的便签"
IS_WIN = sys.platform.startswith("win")

C = {
    "border":   "#E2DCCF",  # 窗口描边
    "bg":       "#FBF9F4",  # 主背景（暖米白）
    "card":     "#FFFFFF",  # 卡片/输入区
    "header":   "#F4F0E6",  # 标题栏
    "text":     "#2E2C28",  # 正文
    "muted":    "#9C9587",  # 次要文字
    "faint":    "#CFC8B9",  # 极淡
    "accent":   "#4C7CF3",  # 主题蓝
    "accent_s": "#E9F0FE",  # 主题蓝浅底
    "pin":      "#E8833A",  # 图钉橙
    "ok":       "#3FA96B",  # 完成绿
    "danger":   "#E05B4B",  # 危险红
    "hover":    "#ECE6D9",  # 悬停底色
}

MIN_W, MIN_H = 228, 190
DEF_W, DEF_H = 330, 450
HDR_H = 36
TAB_H = 30
STA_H = 22

# --------------------------------------------------------------------------- #
# 数据层
# --------------------------------------------------------------------------- #


def _data_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    p = Path(base) / APP_NAME
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        p = Path.cwd()
    return p


DATA_FILE = _data_dir() / "data.json"

WELCOME = """欢迎使用 PinNote 📌

点标题栏左边的图钉，可以把窗口钉在所有窗口最上层。
拖动顶部标题栏移动窗口，拖右下角的 ◢ 可以缩放大小。
写下的内容会自动保存，关掉再打开还在。

小技巧
Ctrl + Alt + N    显示 / 隐藏窗口
Ctrl + N          新建便签
Ctrl + S          立即保存
右键任意位置      更多设置（透明度、字号）

把这里的内容删掉，开始写你自己的笔记吧。
"""


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def default_data() -> dict:
    nid = new_id()
    return {
        "version": 1,
        "notes": [{"id": nid, "title": "欢迎使用", "content": WELCOME, "updated": stamp()}],
        "active_note": nid,
        "tasks": [
            {"id": new_id(), "text": "把 PinNote 钉在屏幕角落", "done": True, "created": stamp()},
            {"id": new_id(), "text": "写下今天要做的三件事", "done": False, "created": stamp()},
        ],
        "ui": {
            "x": None, "y": None, "w": DEF_W, "h": DEF_H,
            "topmost": True, "collapsed": False, "tab": "note",
            "opacity": 1.0, "font_size": 10,
        },
    }


def load_data() -> dict:
    for path in (DATA_FILE, DATA_FILE.with_name(DATA_FILE.name + ".bak")):
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            break
        except Exception:
            raw = None
    else:
        raw = None
    if raw is not None:
        try:
            base = default_data()
            for k, v in base.items():
                raw.setdefault(k, v)
            if not raw.get("notes"):
                raw["notes"] = base["notes"]
            if not raw.get("tasks"):
                raw["tasks"] = []
            raw["ui"].update({k: v for k, v in base["ui"].items() if k not in raw["ui"]})
            return raw
        except Exception:
            pass
    return default_data()


def save_data(data: dict) -> None:
    try:
        if DATA_FILE.exists() and DATA_FILE.stat().st_size > 0:
            bak = DATA_FILE.with_name(DATA_FILE.name + ".bak")
            try:
                shutil.copyfile(DATA_FILE, bak)
            except Exception:
                pass
        tmp = DATA_FILE.with_name(DATA_FILE.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, DATA_FILE)
    except Exception as exc:  # 保存失败不应该让程序崩掉
        print("保存失败:", exc, file=sys.stderr)


# --------------------------------------------------------------------------- #
# 小部件
# --------------------------------------------------------------------------- #


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
                     padx=8, pady=4, font=(FONT_FAMILY, 8), justify="left").pack()
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


# --------------------------------------------------------------------------- #
# 主程序
# --------------------------------------------------------------------------- #

FONT_FAMILY = "Segoe UI"


class PinNote:
    TASK_PH = "添加新计划，按回车确认"

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
        for name in ("Microsoft YaHei UI", "微软雅黑", "Microsoft YaHei", "Segoe UI"):
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
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            pref = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # 界面
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        # 外框：root 的 bg 当作 1px 描边
        self.outer = tk.Frame(self.root, bg=C["bg"])
        self.outer.pack(fill="both", expand=True, padx=1, pady=1)

        self._build_header()
        self._build_tabs()
        self._build_status()          # 先占住底部，再让正文区填充剩余空间

        self.body = tk.Frame(self.outer, bg=C["bg"])
        self.body.pack(fill="both", expand=True)

        self.page_note = tk.Frame(self.body, bg=C["bg"])
        self.page_plan = tk.Frame(self.body, bg=C["bg"])
        self._build_note_page(self.page_note)
        self._build_plan_page(self.page_plan)
        self.page_note.pack(fill="both", expand=True)

        self._build_grip()
        self._build_menu()

    # -- 标题栏 --------------------------------------------------------- #
    def _build_header(self):
        h = tk.Frame(self.outer, bg=C["header"], height=HDR_H)
        h.pack(fill="x")
        h.pack_propagate(False)

        self.btn_pin = FlatButton(h, "📌", command=self.toggle_topmost,
                                  bg=C["header"], fg=C["pin"],
                                  hover=C["hover"], font=(FONT_FAMILY, 11), padx=8)
        self.btn_pin.pack(side="left", fill="y")
        Tooltip(self.btn_pin, "置顶：让便签钉在所有窗口最上层")

        self.lbl_title = tk.Label(h, text=APP_TITLE, bg=C["header"], fg=C["text"],
                                  font=self.f_title, anchor="w")
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

    # -- 标签页 --------------------------------------------------------- #
    def _build_tabs(self):
        t = tk.Frame(self.outer, bg=C["bg"], height=TAB_H)
        t.pack(fill="x")
        t.pack_propagate(False)
        self.tab_bar = t

        inner = tk.Frame(t, bg=C["bg"])
        inner.pack(side="left", padx=6, pady=(4, 0))

        self.tab_btns = {}
        for key, label in (("note", "便签"), ("plan", "计划")):
            b = FlatButton(inner, label, command=lambda k=key: self.switch_tab(k),
                           bg=C["bg"], fg=C["muted"], hover=C["bg"],
                           font=self.f_body, padx=10, pady=2)
            b.pack(side="left")
            self.tab_btns[key] = b

        self.lbl_hint = tk.Label(t, text="", bg=C["bg"], fg=C["faint"], font=self.f_tiny)
        self.lbl_hint.pack(side="right", padx=8)

    def switch_tab(self, key):
        if key == self.ui.get("tab") and getattr(self, "_tab_ready", False):
            return
        self._tab_ready = True
        self.ui["tab"] = key
        self.page_note.pack_forget()
        self.page_plan.pack_forget()
        (self.page_note if key == "note" else self.page_plan).pack(fill="both", expand=True)
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

    # -- 便签页 --------------------------------------------------------- #
    def _build_note_page(self, page):
        self.note_list_view = tk.Frame(page, bg=C["bg"])
        self.note_edit_view = tk.Frame(page, bg=C["bg"])
        self._note_view = "list"

        # 列表视图
        head = tk.Frame(self.note_list_view, bg=C["bg"])
        head.pack(fill="x", padx=9, pady=(8, 5))
        self.lbl_note_count = tk.Label(head, text="", bg=C["bg"], fg=C["muted"],
                                       font=self.f_small)
        self.lbl_note_count.pack(side="left")
        b_new = FlatButton(head, "＋ 新建", command=self.new_note, bg=C["card"],
                           fg=C["accent"], hover=C["accent_s"],
                           font=self.f_small, padx=9, pady=3)
        b_new.pack(side="right")
        Tooltip(b_new, "新建便签 (Ctrl+N)")

        self.notes_canvas = tk.Canvas(self.note_list_view, bg=C["bg"],
                                      highlightthickness=0, bd=0)
        self.notes_canvas.pack(fill="both", expand=True, padx=(9, 5))
        self.notes_inner = tk.Frame(self.notes_canvas, bg=C["bg"])
        self.notes_win = self.notes_canvas.create_window(
            (0, 0), window=self.notes_inner, anchor="nw")
        self.notes_inner.bind(
            "<Configure>",
            lambda e: self.notes_canvas.configure(
                scrollregion=self.notes_canvas.bbox("all")))
        self.notes_canvas.bind(
            "<Configure>",
            lambda e: self.notes_canvas.itemconfigure(self.notes_win, width=e.width))

        # 编辑视图
        bar = tk.Frame(self.note_edit_view, bg=C["bg"])
        bar.pack(fill="x", padx=9, pady=(8, 0))
        FlatButton(bar, "‹ 返回列表", command=self._show_note_list, bg=C["bg"],
                   fg=C["accent"], hover=C["accent_s"], font=self.f_small,
                   padx=4, pady=2).pack(side="left")
        self.lbl_note_time = tk.Label(bar, text="", bg=C["bg"], fg=C["faint"],
                                      font=self.f_tiny)
        self.lbl_note_time.pack(side="right")
        b_del = FlatButton(bar, "🗑", command=self.delete_note, bg=C["bg"],
                           fg=C["muted"], hover="#F3D9D4", font=self.f_small,
                           padx=6, pady=2)
        b_del.pack(side="right", padx=(0, 8))
        Tooltip(b_del, "删除这条便签")

        self.var_note_title = tk.StringVar()
        self.ent_title = tk.Entry(self.note_edit_view,
                                  textvariable=self.var_note_title,
                                  bg=C["card"], fg=C["text"], font=self.f_bold,
                                  relief="flat", bd=0, highlightthickness=0,
                                  insertbackground=C["accent"])
        self.ent_title.pack(fill="x", padx=9, pady=(7, 0), ipady=6)
        self.var_note_title.trace_add("write", lambda *_: self._on_title_change())

        self.txt = tk.Text(self.note_edit_view, bg=C["card"], fg=C["text"],
                           font=self.f_body, relief="flat", bd=0,
                           highlightthickness=0, wrap="word", undo=True,
                           insertbackground=C["accent"],
                           selectbackground=C["accent_s"],
                           selectforeground=C["text"],
                           spacing1=1, spacing3=3, padx=10, pady=8)
        self.txt.pack(fill="both", expand=True, padx=9, pady=(5, 8))
        self.txt.bind("<<Modified>>", self._on_text_change)
        self.txt.bind("<Control-MouseWheel>", self._zoom_text)

        self._show_note_list()

    def _show_note_list(self):
        self.sync_note()
        self._note_view = "list"
        self.note_edit_view.pack_forget()
        self.note_list_view.pack(fill="both", expand=True)
        self._render_note_cards()

    def _open_note(self, nid):
        self.sync_note()
        self.data["active_note"] = nid
        self._note_view = "edit"
        self.note_list_view.pack_forget()
        self.note_edit_view.pack(fill="both", expand=True)
        self._load_notes()
        self.txt.focus_set()

    def _render_note_cards(self):
        for w in self.notes_inner.winfo_children():
            w.destroy()
        notes = self.data["notes"]
        cur = self.data.get("active_note")
        self.lbl_note_count.configure(text=f"共 {len(notes)} 条")
        if not notes:
            tk.Label(self.notes_inner,
                     text="还没有便签，点右上角「＋ 新建」",
                     bg=C["bg"], fg=C["faint"], font=self.f_small,
                     wraplength=240, justify="left").pack(anchor="w", padx=6, pady=16)
            return
        for n in notes:
            self._note_card(n, n["id"] == cur)

    def _note_card(self, n, active):
        title = (n.get("title") or "").strip() or "无标题"
        if len(title) > 18:
            title = title[:18] + "…"
        content = (n.get("content") or "").strip().replace("\n", " ")
        snippet = content if content else "（空）"
        if len(snippet) > 40:
            snippet = snippet[:40] + "…"

        card = tk.Frame(self.notes_inner, bg=C["card"], highlightthickness=1,
                        highlightbackground=C["accent_s"] if active else C["border"])
        card.pack(fill="x", pady=2)

        body = tk.Frame(card, bg=C["card"])
        body.pack(side="left", fill="both", expand=True, padx=(9, 0), pady=6)
        tk.Label(body, text=title, bg=C["card"], fg=C["text"],
                 font=self.f_bold, anchor="w").pack(fill="x")
        tk.Label(body, text=snippet, bg=C["card"], fg=C["muted"],
                 font=self.f_tiny, anchor="w", wraplength=220,
                 justify="left").pack(fill="x", pady=(1, 0))
        tk.Label(body, text=n.get("updated", ""), bg=C["card"], fg=C["faint"],
                 font=self.f_tiny, anchor="w").pack(fill="x", pady=(2, 0))

        dele = FlatButton(card, "✕", command=lambda: self._delete_note_id(n["id"]),
                          bg=C["card"], fg=C["faint"], hover="#F3D9D4",
                          font=self.f_small, padx=7, pady=0)
        dele.pack(side="right", fill="y", padx=(2, 2))

        for w in (card, body):
            w.bind("<Button-1>", lambda e, i=n["id"]: self._open_note(i))
        for w in body.winfo_children():
            w.bind("<Button-1>", lambda e, i=n["id"]: self._open_note(i))

    def _delete_note_id(self, nid):
        if len(self.data["notes"]) <= 1:
            self.set_status("至少保留一条便签")
            return
        self.data["notes"] = [n for n in self.data["notes"] if n["id"] != nid]
        if self.data.get("active_note") == nid:
            self.data["active_note"] = self.data["notes"][0]["id"]
        self._render_note_cards()
        self.schedule_save()
        self.set_status("已删除")

    # -- 计划页 --------------------------------------------------------- #
    def _build_plan_page(self, page):
        top = tk.Frame(page, bg=C["bg"])
        top.pack(fill="x", padx=10, pady=(8, 2))

        self.lbl_prog = tk.Label(top, text="0 / 0 已完成", bg=C["bg"], fg=C["muted"],
                                 font=self.f_small, anchor="w")
        self.lbl_prog.pack(side="left")

        self.btn_clear = FlatButton(top, "清空已完成", command=self.clear_done,
                                    bg=C["bg"], fg=C["muted"], hover=C["hover"],
                                    font=self.f_tiny, padx=6, pady=1)
        self.btn_clear.pack(side="right")

        self.pbar_bg = tk.Frame(page, bg="#EDE8DC", height=5)
        self.pbar_bg.pack(fill="x", padx=10, pady=(4, 6))
        self.pbar_bg.pack_propagate(False)
        self.pbar = tk.Frame(self.pbar_bg, bg=C["ok"])
        self.pbar.place(x=0, y=0, relheight=1, relwidth=0)

        # 添加任务（先占住底部，再让任务列表填充剩余空间）
        # 列表本身即可编辑，无需独立添加栏
        # 列表本身即可编辑
        # 任务列表（滚轮滚动，无滚动条保持简洁）
        self.task_canvas = tk.Canvas(page, bg=C["bg"], highlightthickness=0, bd=0)
        self.task_canvas.pack(fill="both", expand=True, padx=(8, 6), pady=(0, 2))
        self.task_inner = tk.Frame(self.task_canvas, bg=C["bg"])
        self.task_win = self.task_canvas.create_window((0, 0), window=self.task_inner, anchor="nw")
        self.task_inner.bind(
            "<Configure>",
            lambda e: self.task_canvas.configure(scrollregion=self.task_canvas.bbox("all")))
        self.task_canvas.bind(
            "<Configure>",
            lambda e: self.task_canvas.itemconfigure(self.task_win, width=e.width))
        self.root.bind_all("<MouseWheel>", self._on_wheel, add="+")

    # -- 状态栏 / 缩放手柄 / 右键菜单 ----------------------------------- #
    def _build_status(self):
        self.status = tk.Frame(self.outer, bg=C["bg"], height=STA_H)
        self.status.pack(fill="x", side="bottom")
        self.status.pack_propagate(False)
        self.lbl_status = tk.Label(self.status, text="就绪", bg=C["bg"], fg=C["faint"],
                                   font=self.f_tiny, anchor="w")
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
                    activebackground=C["accent_s"], activeforeground=C["accent"],
                    bd=0, relief="flat", font=self.f_body)
        self.menu = m
        m.add_command(label="📌  置顶开关", command=self.toggle_topmost)
        m.add_command(label="↕  折叠 / 展开", command=self.toggle_collapse)
        m.add_separator()
        for pct in (100, 92, 85, 75):
            m.add_command(label=f"透明度 {pct}%",
                          command=lambda p=pct: self.set_opacity(p / 100))
        m.add_separator()
        for size in (9, 10, 11, 12):
            m.add_command(label=f"字号 {size}", command=lambda s=size: self.set_font_size(s))
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
    # 便签逻辑
    # ------------------------------------------------------------------ #
    @property
    def note(self):
        nid = self.data.get("active_note")
        for n in self.data["notes"]:
            if n["id"] == nid:
                return n
        self.data["active_note"] = self.data["notes"][0]["id"]
        return self.data["notes"][0]

    def _load_notes(self):
        self._loading = True
        try:
            n = self.note
            self.var_note_title.set(n.get("title", ""))
            self.txt.delete("1.0", "end")
            self.txt.insert("1.0", n.get("content", ""))
            self.txt.edit_modified(False)
            self.txt.edit_reset()
            self.txt.mark_set("insert", "1.0")   # 光标与视图都回到开头
            self.txt.see("1.0")
            self.lbl_note_time.configure(text=n.get("updated", ""))
        finally:
            self._loading = False

    def select_note(self, nid):
        self._open_note(nid)

    def new_note(self):
        self.sync_note()
        nid = new_id()
        self.data["notes"].insert(0, {"id": nid, "title": "",
                                      "content": "", "updated": stamp()})
        self.data["active_note"] = nid
        self._note_view = "edit"
        self.note_list_view.pack_forget()
        self.note_edit_view.pack(fill="both", expand=True)
        self._load_notes()
        self.ent_title.focus_set()
        self.set_status("已新建，先写个标题吧")

    def rename_note(self):
        from tkinter import simpledialog
        cur = self.var_note_title.get()
        name = simpledialog.askstring("重命名", "便签名称：", initialvalue=cur, parent=self.root)
        if name is not None:
            self.var_note_title.set(name.strip() or "无标题")

    def delete_note(self):
        from tkinter import messagebox
        if len(self.data["notes"]) <= 1:
            messagebox.showinfo(APP_NAME, "至少要保留一个便签哦", parent=self.root)
            return
        title = (self.note.get("title") or "无标题").strip()
        if not messagebox.askyesno(APP_NAME, f"确定删除便签「{title}」？\n删除后无法恢复。",
                                   parent=self.root):
            return
        self._delete_note_id(self.data["active_note"])
        self._show_note_list()
        self.set_status("已删除便签")

    def clear_note(self):
        from tkinter import messagebox
        if messagebox.askyesno(APP_NAME, "清空当前便签的全部内容？", parent=self.root):
            self.txt.delete("1.0", "end")

    def sync_note(self):
        """把界面上的内容写回数据模型"""
        if self._loading:
            return
        n = self.note
        n["content"] = self.txt.get("1.0", "end-1c")
        title = self.var_note_title.get().strip()
        n["title"] = title
        n["updated"] = stamp()

    def _on_title_change(self):
        self.sync_note()
        self.schedule_save()

    def _on_text_change(self, _=None):
        if not self.txt.edit_modified():
            return
        self.txt.edit_modified(False)
        self.sync_note()
        self.schedule_save()

    def _zoom_text(self, event):
        size = int(self.ui.get("font_size", 10)) + (1 if event.delta > 0 else -1)
        self.set_font_size(max(8, min(16, size)))

    # ------------------------------------------------------------------ #
    # 计划逻辑
    # ------------------------------------------------------------------ #
    def _on_wheel(self, event):
        """按鼠标位置决定滚动谁"""
        try:
            w = self.root.winfo_containing(event.x_root, event.y_root)
        except Exception:
            return None
        node = w
        while node is not None:
            if node is self.task_canvas or node is self.notes_canvas:
                node.yview_scroll(-1 if event.delta > 0 else 1, "units")
                return "break"
            if isinstance(node, tk.Text):
                return None  # 交给 Text 自己处理
            node = getattr(node, "master", None)
        return None

    def _render_tasks(self):
        for w in self.task_inner.winfo_children():
            w.destroy()
        tasks = self.data["tasks"]
        if not tasks:
            tasks.append({"id": new_id(), "text": "", "done": False,
                          "created": stamp()})
        if tasks and tasks[-1]["text"]:
            tasks.append({"id": new_id(), "text": "", "done": False,
                          "created": stamp()})
        n = 0
        for i, t in enumerate(tasks):
            if t["text"]:
                n += 1
            self._task_row(t, n, last=(i == len(tasks) - 1))
        self._update_progress()

    def _task_row(self, task, idx=0, last=False):
        row = tk.Frame(self.task_inner, bg=C["card"], height=30)
        row.pack(fill="x")
        row.pack_propagate(False)

        done = task["done"]
        empty = not task["text"]
        locked = bool(task["text"]) and not task.get("edit")
        st = {"ph": empty}

        num = tk.Label(row, text="＋" if empty else str(idx),
                       bg=C["card"], fg=C["accent"] if empty else C["faint"],
                       font=self.f_small, width=2, anchor="e")
        num.pack(side="left", padx=(8, 2))
        if not empty:
            num.bind("<Double-Button-1>", lambda e, t=task: self._unlock_row(t))
            if locked:
                Tooltip(num, "双击序号可重新编辑这一条")

        if not empty:
            cv = tk.Canvas(row, width=18, height=18, bg=C["card"],
                           highlightthickness=0, cursor="hand2")
            cv.pack(side="left", padx=(2, 6))
            self._draw_check(cv, done)
            cv.bind("<Button-1>", lambda e, t=task: self.toggle_task(t))
            Tooltip(cv, "点击切换完成状态")
        else:
            tk.Frame(row, width=26, bg=C["card"]).pack(side="left")

        var = tk.StringVar(value="" if empty else task["text"])
        ent = tk.Entry(row, textvariable=var, bg=C["card"],
                       fg=C["muted"] if done else C["text"],
                       relief="flat", bd=0, highlightthickness=0,
                       insertbackground=C["accent"],
                       disabledbackground=C["card"],
                       disabledforeground=C["muted"],
                       font=self.f_body if not done else (
                           FONT_FAMILY, int(self.ui.get("font_size", 10)), "overstrike"))
        if empty:
            var.set(self.TASK_PH)
            ent.configure(fg=C["faint"])
        elif done or locked:
            ent.configure(state="disabled")
        ent.pack(side="left", fill="both", expand=True)

        if not empty:
            dele = FlatButton(row, "✕", command=lambda: self.del_task(task),
                              bg=C["card"], fg=C["faint"], hover="#F3D9D4",
                              font=self.f_small, padx=6, pady=0)
            dele.pack(side="right", fill="y")

        if not last:
            tk.Frame(self.task_inner, bg=C["border"], height=1).pack(fill="x")

        def focus_in(_=None):
            if st["ph"]:
                st["ph"] = False
                var.set("")
                ent.configure(fg=C["text"])

        def focus_out(_=None):
            if not var.get().strip():
                st["ph"] = True
                var.set(self.TASK_PH)
                ent.configure(fg=C["faint"])

        if empty:
            ent.bind("<FocusIn>", focus_in)

        for seq in ("<Return>", "<BackSpace>", "<Escape>"):
            ent.bind(seq, lambda e, t=task, v=var, s=st: self._row_key(e, t, v, s))
        ent.bind("<FocusOut>", lambda e, t=task, v=var, w=ent, s=st: (
            focus_out(), self._row_commit(t, v, w, s)))
        if task["id"] == getattr(self, "_focus_id", None) and not done:
            ent.focus_set()
            self._focus_id = None

    def _draw_check(self, cv, done):
        cv.delete("all")
        if done:
            cv.create_oval(2, 2, 16, 16, fill=C["ok"], outline="")
            cv.create_line(5, 9, 8, 12, 13, 6, fill="#FFFFFF", width=2,
                           capstyle="round", joinstyle="round")
        else:
            cv.create_oval(3, 3, 15, 15, outline=C["faint"], width=1)

    def _unlock_row(self, task):
        """双击序号解锁，可重新编辑"""
        task["edit"] = True
        self._focus_id = task["id"]
        self._render_tasks()

    def _row_commit(self, task, var, widget=None, st=None):
        v = "" if (st and st.get("ph")) else var.get().strip()
        task["text"] = v
        task.pop("edit", None)          # 提交后锁定
        if widget is not None and v:
            widget.configure(state="disabled")
        self.schedule_save()

    def _row_key(self, event, task, var, st=None):
        """回车=新增下一行并跳过去；空行退格=删除本行"""
        if st and st.get("ph"):
            if event.keysym == "Return":
                return "break"
            text = ""
        else:
            text = var.get().strip()
        if event.keysym == "Return":
            if not text:
                return "break"          # 空行回车不新增
            self._row_commit(task, var, st=st)
            new = {"id": new_id(), "text": "", "done": False, "created": stamp()}
            idx = self.data["tasks"].index(task) + 1
            self.data["tasks"].insert(idx, new)
            self._focus_id = new["id"]
            self._render_tasks()
            return "break"
        if event.keysym == "BackSpace" and not text and len(self.data["tasks"]) > 1:
            self._remove_task(task)
            return "break"
        if event.keysym == "Escape":
            var.set("" if not task["text"] else task["text"])
            event.widget.master.focus_set()
            return "break"
        return None

    def toggle_task(self, task):
        task["done"] = not task["done"]
        self._render_tasks()
        self.schedule_save()

    def del_task(self, task):
        self._remove_task(task)

    def _remove_task(self, task):
        self.data["tasks"] = [t for t in self.data["tasks"]
                              if t["id"] != task["id"]]
        self._render_tasks()
        self.schedule_save()

    def clear_done(self):
        keep = [t for t in self.data["tasks"] if not t["done"] or not t["text"]]
        n = len(self.data["tasks"]) - len(keep)
        if not n:
            self.set_status("没有已完成的任务")
            return
        self.data["tasks"] = keep
        self._render_tasks()
        self.schedule_save()
        self.set_status(f"已清理 {n} 条")

    def _update_progress(self):
        tasks = [t for t in self.data["tasks"] if t["text"]]
        total = len(tasks)
        done = sum(1 for t in tasks if t["done"])
        self.lbl_prog.configure(text=f"{done} / {total} 已完成")
        ratio = (done / total) if total else 0
        if ratio > 0:
            self.pbar.place(x=0, y=0, relheight=1, relwidth=ratio)
        else:
            self.pbar.place_forget()
        self.pbar.configure(bg=C["ok"] if ratio >= 1 and total else C["accent"])

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
        self.root.geometry(f"+{event.x_root - self._dx}+{event.y_root - self._dy}")

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
        for w in (self.lbl_title,):
            w.configure(font=self.f_title)
        self.lbl_status.configure(font=self.f_tiny)
        self.lbl_hint.configure(font=self.f_tiny)
        self.lbl_prog.configure(font=self.f_small)
        self.txt.configure(font=self.f_body)
        self.ent_title.configure(font=self.f_bold)
        for k, b in self.tab_btns.items():
            b.configure(font=self.f_bold if k == self.ui.get("tab") else self.f_body)
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
            "双击任务文字     修改内容\n\n"
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
            MOD_ALT, MOD_CONTROL, VK_N = 0x0001, 0x0002, 0x4E
            if not u.RegisterHotKey(None, self._hotkey_id, MOD_CONTROL | MOD_ALT, VK_N):
                return
            u.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                       wintypes.UINT, wintypes.UINT, wintypes.UINT]
            self._msg = wintypes.MSG()
            self._hotkey_on = True
            self._poll_hotkey()
        except Exception:
            self._hotkey_on = False

    def _poll_hotkey(self):
        try:
            from ctypes import wintypes
            while self._user32.PeekMessageW(ctypes.byref(self._msg), None, 0x0312, 0x0312, 1):
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
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
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
    if IS_WIN:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    PinNote().run()


if __name__ == "__main__":
    main()
