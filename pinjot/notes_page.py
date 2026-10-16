# -*- coding: utf-8 -*-
"""笔记页：知识库树视图 + 富文本编辑视图。

以 Mixin 形式混入 PinJot 主类，与主窗口共享
self.data / self.root / self.schedule_save() 等。

文档结构：知识库 → 多层级子笔记（树），见 storage.py 说明。
行内样式：tk 的 tag 实时渲染，保存为 [start, end, style] 字符偏移列表。
"""

import tkinter as tk
from tkinter import messagebox, simpledialog

from . import outline
from . import storage
from .config import APP_NAME, C, DEFAULT_HOTKEYS
from .storage import count_notes, find_book, find_note, new_id, stamp
from .widgets import FlatButton, Tooltip


# 文字颜色选择（"" = 恢复默认）
STYLE_COLORS = [
    ("默认", ""), ("砖红", "#E05B4B"), ("暖橙", "#E8833A"),
    ("草绿", "#3FA96B"), ("天蓝", "#4C7CF3"), ("紫罗兰", "#8A63D2"),
    ("樱粉", "#E0678C"), ("石墨灰", "#7C8698"),
]
ARROW_OPEN, ARROW_CLOSE = "▾", "▸"

# Shift + 数字 在 tk 里的 keysym（如 Ctrl+Shift+8 的 keysym 是 asterisk）
SHIFT_NUM = {
    "1": "exclam", "2": "at", "3": "numbersign", "4": "dollar",
    "5": "percent", "6": "asciicircum", "7": "ampersand",
    "8": "asterisk", "9": "parenleft", "0": "parenright",
}
SHIFT_NUM_REV = {v: k for k, v in SHIFT_NUM.items()}
MOD_KEYSYMS = {"Control_L", "Control_R", "Shift_L", "Shift_R",
               "Alt_L", "Alt_R", "Super_L", "Super_R", "Win_L", "Win_R"}


def _is_style_tag(tag):
    """判断是否是行内样式 tag（区别于 sel/insert 等系统 tag）"""
    return tag in ("b", "i", "u") or tag.startswith(("c:", "s:"))


def hotkey_to_tk(spec):
    """'Ctrl+Shift+8' -> tk 绑定序列 '<Control-asterisk>'；解析失败返回 None。"""
    parts = [p for p in (spec or "").split("+") if p]
    if not parts:
        return None
    key, mods = parts[-1], parts[:-1]
    seq = []
    if "Ctrl" in mods:
        seq.append("Control")
    if "Alt" in mods:
        seq.append("Alt")
    if "Shift" in mods:
        if key in SHIFT_NUM:
            key = SHIFT_NUM[key]                # 7 -> ampersand
        elif len(key) == 1 and key.isalpha():
            key = key.upper()                   # B -> B（大写 keysym 即 Shift+B）
        else:
            seq.append("Shift")                 # F2 等特殊键照常拼 Shift
    elif len(key) == 1 and key.isalpha():
        key = key.lower()
    try:
        return "<" + "-".join(seq + [key]) + ">"
    except Exception:
        return None


def event_to_hotkey(event):
    """键盘事件 -> 'Ctrl+Shift+8' 格式；处理不了返回 None。"""
    if event.keysym in MOD_KEYSYMS:
        return None                             # 只摁了修饰键，继续等
    mods = []
    if event.state & 0x0004:
        mods.append("Ctrl")
    if event.state & 0x0008:
        mods.append("Alt")
    ks = event.keysym
    if ks in SHIFT_NUM_REV:
        if "Shift" not in mods:
            mods.append("Shift")
        key = SHIFT_NUM_REV[ks]                 # asterisk -> 8
    elif len(ks) == 1 and ks.isalpha():
        key = ks.upper()
        if ks.isupper() and "Shift" not in mods:
            mods.append("Shift")
    else:
        key = ks
        if (event.state & 0x0001) and "Shift" not in mods:
            mods.append("Shift")
    return "+".join(mods + [key])


class NotePageMixin:
    """笔记页的界面构建与业务逻辑"""

    # ------------------------------------------------------------------ #
    # 界面
    # ------------------------------------------------------------------ #
    def _build_note_page(self, page):
        self.note_list_view = tk.Frame(page, bg=C["bg"])
        self.note_edit_view = tk.Frame(page, bg=C["bg"])
        self._note_view = "list"

        # ---- 树视图（知识库 + 笔记树）----
        head = tk.Frame(self.note_list_view, bg=C["bg"])
        head.pack(fill="x", padx=9, pady=(8, 5))
        b_book = FlatButton(head, "＋ 知识库", command=self.new_book,
                            bg=C["card"], fg=C["accent"],
                            hover=C["accent_s"], font=self.f_small,
                            padx=8, pady=3)
        b_book.pack(side="left")
        Tooltip(b_book, "新建知识库（比如「书籍笔记」「工作」）")
        self.lbl_note_count = tk.Label(head, text="", bg=C["bg"], fg=C["muted"],
                                       font=self.f_tiny)
        self.lbl_note_count.pack(side="right")

        self.notes_canvas = tk.Canvas(self.note_list_view, bg=C["bg"],
                                      highlightthickness=0, bd=0,
                                      yscrollincrement=18)
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
            lambda e: (self.notes_canvas.itemconfigure(self.notes_win,
                                                       width=e.width),
                       self._clamp_tree_scroll(None)))
        self.notes_canvas.bind("<MouseWheel>", self._tree_scroll)

        # ---- 编辑视图 ----
        bar = tk.Frame(self.note_edit_view, bg=C["bg"])
        bar.pack(fill="x", padx=9, pady=(8, 0))
        FlatButton(bar, "‹ 返回", command=self._show_note_list, bg=C["bg"],
                   fg=C["accent"], hover=C["accent_s"], font=self.f_small,
                   padx=4, pady=2).pack(side="left")
        self.lbl_crumb = tk.Label(bar, text="", bg=C["bg"], fg=C["faint"],
                                  font=self.f_tiny, anchor="w")
        self.lbl_crumb.pack(side="left", padx=(6, 0))
        b_del = FlatButton(bar, "🗑", command=self.delete_note, bg=C["bg"],
                           fg=C["muted"], hover="#F3D9D4", font=self.f_small,
                           padx=6, pady=2)
        b_del.pack(side="right", padx=(0, 6))
        Tooltip(b_del, "删除这篇笔记（含子笔记）")
        self.lbl_note_time = tk.Label(bar, text="", bg=C["bg"], fg=C["faint"],
                                      font=self.f_tiny)
        self.lbl_note_time.pack(side="right")

        # 格式工具栏
        tb = tk.Frame(self.note_edit_view, bg=C["bg"])
        tb.pack(fill="x", padx=9, pady=(6, 0))

        def tb_btn(text, cmd, tip, **kw):
            kw.setdefault("font", self.f_small)
            b = FlatButton(tb, text, command=cmd, bg=C["bg"], fg=C["muted"],
                           hover=C["hover"], padx=5, pady=2, **kw)
            b.pack(side="left")
            Tooltip(b, tip)
            return b

        tb_btn("🖍", self._pick_color, "文字颜色（先选中文字，或对整行生效）")
        tb_btn("A－", lambda: self._change_size(-1), "缩小选中文字")
        tb_btn("A＋", lambda: self._change_size(1), "放大选中文字")
        tk.Frame(tb, width=1, bg=C["border"]).pack(side="left", fill="y",
                                                   padx=3, pady=2)
        tb_btn("B", lambda: self._toggle_fmt("b"), "加粗",
               font=(self.f_small[0], self.f_small[1], "bold"))
        tb_btn("I", lambda: self._toggle_fmt("i"), "斜体",
               font=(self.f_small[0], self.f_small[1], "italic"))
        tb_btn("U", lambda: self._toggle_fmt("u"), "下划线")
        tk.Frame(tb, width=1, bg=C["border"]).pack(side="left", fill="y",
                                                   padx=3, pady=2)
        tb_btn("•", lambda: self._outline_toggle("bullet"), "符号列表（点第二次取消）")
        tb_btn("1.", lambda: self._outline_toggle("num"), "数字编号（点第二次取消）")
        tb_btn("⌫", self._clear_format, "清除选中文字 / 整行的格式")

        self.var_note_title = tk.StringVar()
        self.ent_title = tk.Entry(self.note_edit_view,
                                  textvariable=self.var_note_title,
                                  bg=C["card"], fg=C["text"], font=self.f_bold,
                                  relief="flat", bd=0, highlightthickness=0,
                                  insertbackground=C["accent"])
        self.ent_title.pack(fill="x", padx=9, pady=(7, 0), ipady=6)
        self.var_note_title.trace_add("write",
                                      lambda *_: self._on_title_change())

        self.txt = tk.Text(self.note_edit_view, bg=C["card"], fg=C["text"],
                           font=self.f_body, relief="flat", bd=0,
                           highlightthickness=0, wrap="word", undo=True,
                           insertbackground=C["accent"],
                           selectbackground=C["accent_s"],
                           selectforeground=C["text"],
                           spacing1=1, spacing3=3, padx=10, pady=8)
        self.txt.pack(fill="both", expand=True, padx=9, pady=(5, 8))
        self.txt.bind("<<Modified>>", self._on_text_change)
        self.txt.bind("<Return>", self._outline_enter)
        self.txt.bind("<Tab>", self._outline_tab)
        self.txt.bind("<Shift-Tab>", self._outline_shift_tab)
        self.txt.bind("<ISO_Left_Tab>", self._outline_shift_tab)
        self.txt.bind("<BackSpace>", self._outline_backspace)
        self.txt.bind("<Control-MouseWheel>", self._zoom_text)

        self._bind_custom_hotkeys()
        self._show_note_list()

    # ------------------------------------------------------------------ #
    # 视图切换
    # ------------------------------------------------------------------ #
    def _show_note_list(self):
        self.sync_note()
        self._note_view = "list"
        self.note_edit_view.pack_forget()
        self.note_list_view.pack(fill="both", expand=True)
        self._render_note_cards()

    def _open_note(self, nid):
        self.sync_note()
        hit = find_note(self.data["books"], nid)
        if hit is None:
            return
        self.data["active_note"] = nid
        self.data["active_book"] = hit[0]["id"]
        self._note_view = "edit"
        self.note_list_view.pack_forget()
        self.note_edit_view.pack(fill="both", expand=True)
        self._load_notes()
        self.txt.focus_set()

    # ------------------------------------------------------------------ #
    # 数据
    # ------------------------------------------------------------------ #
    @property
    def note(self):
        """当前编辑的笔记（树节点）；找不到时兜底到全树第一篇。"""
        hit = find_note(self.data["books"], self.data.get("active_note"))
        if hit:
            return hit[1]
        nid = storage.first_note_id(self.data["books"])
        hit = find_note(self.data["books"], nid)
        if hit:
            self.data["active_note"] = nid
            return hit[1]
        return None

    def _load_notes(self):
        self._loading = True
        try:
            n = self.note
            if n is None:                       # 极端情况兜底
                book = self.data["books"][0]
                n = storage.new_note("", "")
                book["notes"].append(n)
                self.data["active_note"] = n["id"]
            self.var_note_title.set(n.get("title", ""))
            self.txt.delete("1.0", "end")
            self.txt.insert("1.0", n.get("content", ""))
            self._load_styles(n.get("rich"))
            self.txt.edit_modified(False)
            self.txt.edit_reset()
            self.txt.mark_set("insert", "1.0")
            self.txt.see("1.0")
            self.lbl_note_time.configure(text=n.get("updated", ""))
            self.lbl_crumb.configure(text=self._breadcrumb(n["id"]))
            self._note_ready = True     # 从这一刻起编辑器内容才代表真实数据
        finally:
            self._loading = False

    def _breadcrumb(self, nid):
        """父级路径，如「书籍笔记 › 第一章」；过长时省略中间。"""
        hit = find_note(self.data["books"], nid)
        if hit is None:
            return ""
        book = hit[0]

        def build(nodes, acc):
            for x in nodes:
                if x["id"] == nid:
                    return acc
                r = build(x.get("children") or [], acc + [x])
                if r is not None:
                    return r
            return None

        path = build(book["notes"], []) or []
        names = [book["name"]] + [(x.get("title") or "无标题").strip()
                                  for x in path]
        if len(names) > 3:
            names = names[:1] + ["…"] + names[-2:]
        return " › ".join(names)

    def sync_note(self):
        """把编辑器里的内容写回数据模型"""
        # 三种情况下编辑器内容都不代表真实数据，必须挡住：
        #   _loading        —— 正在往编辑器灌数据
        #   not _note_ready —— 编辑器还没被填充过（启动阶段）
        #   _rebuilding     —— 界面正在重建，编辑器是新建的空控件
        if (self._loading or not getattr(self, "_note_ready", False)
                or getattr(self, "_rebuilding", False)):
            return
        n = self.note
        if n is None:
            return
        n["content"] = self.txt.get("1.0", "end-1c")
        n["rich"] = self._dump_styles()
        n["title"] = self.var_note_title.get().strip()
        n["updated"] = stamp()

    def _on_title_change(self):
        self.sync_note()
        self.schedule_save()

    def _on_text_change(self, _=None):
        if not self.txt.edit_modified():
            return
        if getattr(self, "_renumbering", False):
            return
        self.txt.edit_modified(False)
        self._outline_apply_renumber()
        self.sync_note()
        self.schedule_save()

    # ------------------------------------------------------------------ #
    # 富文本：颜色 / 字号 / 粗斜线 / 清除格式
    # ------------------------------------------------------------------ #
    def _sel_or_line(self):
        """有选区用选区，否则取光标所在整行。"""
        t = self.txt
        if t.tag_ranges("sel"):
            return t.index("sel.first"), t.index("sel.last")
        ln = int(t.index("insert").split(".")[0])
        return f"{ln}.0", f"{ln}.end"

    def _configure_tag(self, spec):
        fam = self.f_body[0]
        base = int(self.ui.get("font_size", 10))
        if spec.startswith("c:"):
            self.txt.tag_configure(spec, foreground=spec[2:])
        elif spec.startswith("s:"):
            size = max(7, min(24, base + int(spec[2:])))
            self.txt.tag_configure(spec, font=(fam, size))
        elif spec == "b":
            self.txt.tag_configure(spec, font=(fam, base, "bold"))
        elif spec == "i":
            self.txt.tag_configure(spec, font=(fam, base, "italic"))
        elif spec == "u":
            self.txt.tag_configure(spec, underline=True)

    def _ensure_tag(self, spec):
        if spec not in self.txt.tag_names():
            self._configure_tag(spec)

    def _add_style(self, spec, start, end):
        self._ensure_tag(spec)
        self.txt.tag_add(spec, start, end)

    def _refresh_style_tags(self):
        """全局字号/字体变化后调用，重配行内样式 tag。"""
        for tag in self.txt.tag_names():
            if _is_style_tag(tag):
                self._configure_tag(tag)

    def _pick_color(self):
        m = tk.Menu(self.root, tearoff=0, bg=C["card"], fg=C["text"],
                    activebackground=C["accent_s"],
                    activeforeground=C["accent"], bd=0, relief="flat",
                    font=self.f_body)
        for name, hexv in STYLE_COLORS:
            m.add_command(
                label=f"● {name}", foreground=(hexv or C["text"]),
                command=lambda h=hexv: self._apply_color(h))
        x = self.txt.winfo_rootx() + 12
        y = self.txt.winfo_rooty() + 4
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    def _apply_color(self, hexv):
        start, end = self._sel_or_line()
        for tag in list(self.txt.tag_names()):
            if tag.startswith("c:"):
                self.txt.tag_remove(tag, start, end)
        if hexv:
            self._add_style(f"c:{hexv}", start, end)
        self.txt.focus_set()

    def _change_size(self, step):
        start, end = self._sel_or_line()
        cur = 0
        for tag in self.txt.tag_names(start):
            if tag.startswith("s:"):
                cur = int(tag[2:])
        new = max(-4, min(6, cur + step))
        for tag in list(self.txt.tag_names()):
            if tag.startswith("s:"):
                self.txt.tag_remove(tag, start, end)
        if new:
            self._add_style(f"s:{new:+d}", start, end)
        self.txt.focus_set()
        self.set_status(f"字号 {new:+d}")

    def _toggle_fmt(self, fmt):
        start, end = self._sel_or_line()
        if fmt in self.txt.tag_names(start):
            self.txt.tag_remove(fmt, start, end)
        else:
            self._add_style(fmt, start, end)
        self.txt.focus_set()

    def _clear_format(self):
        start, end = self._sel_or_line()
        for tag in list(self.txt.tag_names()):
            if _is_style_tag(tag):
                self.txt.tag_remove(tag, start, end)
        self.txt.focus_set()
        self.set_status("已清除格式")

    def _dump_styles(self):
        """编辑器里的样式 tag → [[start, end, spec], ...] 字符偏移。"""
        t = self.txt

        def offset(idx):
            r = t.count("1.0", idx, "chars")     # 同 index 时 tk 返回 None
            return r[0] if r else 0

        out = []
        for tag in t.tag_names():
            if not _is_style_tag(tag):
                continue
            ranges = t.tag_ranges(tag)
            for i in range(0, len(ranges), 2):
                s = offset(ranges[i])
                e = offset(ranges[i + 1])
                if e > s:
                    out.append([s, e, tag])
        return out

    def _load_styles(self, styles):
        """[[start, end, spec], ...] → 编辑器样式 tag。"""
        t = self.txt
        for item in styles or []:
            try:
                s, e, tag = int(item[0]), int(item[1]), str(item[2])
            except Exception:
                continue
            if not _is_style_tag(tag):
                continue
            self._ensure_tag(tag)
            t.tag_add(tag, f"1.0 + {s} chars", f"1.0 + {e} chars")

    # ------------------------------------------------------------------ #
    # 大纲列表：Enter 续号 / Tab 降级 / Shift+Tab 升级 / 行首退格 / 类型切换
    # ------------------------------------------------------------------ #
    def _outline_enter(self, _event):
        """列表行里按回车：自动续项；空列表项则退出列表。"""
        t = self.txt
        if t.tag_ranges("sel"):
            return None
        ln, col = (int(x) for x in t.index("insert").split("."))
        line = t.get(f"{ln}.0", f"{ln}.end")
        p = outline.parse(line)
        if p is None:
            return None
        kind, indent, marker, sep, content = p
        plen = len(indent) + len(marker) + len(sep)
        if col < plen:
            return None                      # 光标还在前缀里：默认换行
        if not content.strip():
            t.delete(f"{ln}.0", f"{ln}.{plen}")   # 空项：退出列表
            t.mark_set("insert", f"{ln}.0")
            return "break"
        if kind == "num":
            path = outline.path_of(marker)
            nxt = ".".join(map(str, path[:-1] + [path[-1] + 1])) + "."
        else:
            nxt = marker                    # 符号列表：续同层级符号
        t.insert("insert", "\n" + indent + nxt + " ")
        return "break"

    def _outline_tab(self, _event):
        return self._outline_shift(1)

    def _outline_shift_tab(self, _event):
        return self._outline_shift(-1)

    def _outline_shift(self, delta):
        """列表行 Tab 降为上一项的子节点 / Shift+Tab 升一级。"""
        t = self.txt
        if t.tag_ranges("sel"):
            return None
        ln, col = (int(x) for x in t.index("insert").split("."))
        line = t.get(f"{ln}.0", f"{ln}.end")
        if outline.parse(line) is None:
            return None                      # 普通行：默认 Tab 行为
        r = outline.shifted_prefix(t.get("1.0", "end-1c"), ln, delta)
        if r is None:
            return "break"                   # 已到边界：吞掉按键
        new_prefix, old_plen = r
        t.edit_separator()                   # 删旧前缀+插新前缀合并为一个撤销块
        t.configure(autoseparators=False)
        try:
            t.delete(f"{ln}.0", f"{ln}.{old_plen}")
            t.insert(f"{ln}.0", new_prefix)
        finally:
            t.configure(autoseparators=True)
            t.edit_separator()
        t.mark_set("insert",
                   f"{ln}.{len(new_prefix) + max(0, col - old_plen)}")
        return "break"

    def _outline_backspace(self, _event):
        """退格自动降级：光标在行首 / 前缀内 / 紧贴正文前时触发。

        - 有缩进：层级降一级（等同 Shift+Tab）
        - 顶级列表项：清掉整个前缀，退回普通文本行
        光标在正文中间时不拦截，保持普通退格（正常删字）。
        """
        t = self.txt
        if t.tag_ranges("sel"):
            return None
        ln, col = (int(x) for x in t.index("insert").split("."))
        p = outline.parse(t.get(f"{ln}.0", f"{ln}.end"))
        if p is None:
            return None
        kind, indent, marker, sep, _ = p
        plen = len(indent) + len(marker) + len(sep)
        if col > plen:
            return None                      # 正文中间：正常删字
        if indent:
            return self._outline_shift(-1)   # 自动降级
        t.delete(f"{ln}.0", f"{ln}.{plen}")  # 顶级列表项：清掉前缀
        return "break"

    def _outline_toggle(self, want):
        """工具栏「•」「1.」：切到对应列表类型；已是该类型则取消。"""
        t = self.txt
        t.focus_set()
        ln = int(t.index("insert").split(".")[0])
        line = t.get(f"{ln}.0", f"{ln}.end")
        p = outline.parse(line)
        if p is not None:
            kind, indent, marker, sep, content = p
            plen = len(indent) + len(marker) + len(sep)
            t.delete(f"{ln}.0", f"{ln}.{plen}")
            if kind == want:
                self.set_status("已取消列表")
                return                          # 同类型：取消即止
            level = len(indent) // outline.INDENT_N
        else:
            raw = line[:len(line) - len(line.lstrip())]
            indent = raw
            level = len(raw) // outline.INDENT_N
        if want == "bullet":
            t.insert(f"{ln}.0", outline.bullet_prefix(level))
        else:
            t.insert(f"{ln}.0", outline.INDENT * level + "1. ")
        self.set_status("Enter 续项，Tab 降级，Shift+Tab 升级")

    def _outline_apply_renumber(self):
        """把全文列表标记重排成规范状态（幂等，仅改动需要变化的行）。"""
        t = self.txt
        changes = outline.renumber(t.get("1.0", "end-1c"))
        if not changes:
            return
        cur = t.index("insert")
        ln, col = int(cur.split(".")[0]), int(cur.split(".")[1])
        # 若正被 Enter/Tab 等操作嵌套调用（autoseparators 已关），
        # 重排动作并入外层操作的撤销块，不要自行封块。
        was_auto = bool(t.cget("autoseparators"))
        self._renumbering = True
        t.configure(autoseparators=False)
        try:
            for idx, new_line, old_plen, new_plen in changes:
                l = idx + 1
                t.delete(f"{l}.0", f"{l}.end")
                t.insert(f"{l}.0", new_line)
                if l == ln:                  # 光标随前缀长度平移
                    nc = (col + new_plen - old_plen
                          if col >= old_plen else new_plen)
                    t.mark_set("insert", f"{l}.{max(0, nc)}")
        finally:
            t.configure(autoseparators=was_auto)
            if was_auto:
                t.edit_separator()           # 独立懒重排：整组成一个撤销块
            t.edit_modified(False)
            self._renumbering = False

    # ------------------------------------------------------------------ #
    # 列表快捷键（可自定义）
    # ------------------------------------------------------------------ #
    def _bind_custom_hotkeys(self):
        """按 ui.hotkeys 绑定 root 级快捷键（可重复调用，先解旧绑）。"""
        for seq in getattr(self, "_hotkey_seqs", []):
            try:
                self.root.unbind(seq)
            except Exception:
                pass
        self._hotkey_seqs = []
        hk = dict(DEFAULT_HOTKEYS)
        hk.update(self.ui.get("hotkeys") or {})
        for action, spec in hk.items():
            seq = hotkey_to_tk(spec)
            if not seq:
                continue
            handler = (self._hotkey_bullet if action == "bullet"
                       else self._hotkey_number)
            try:
                self.root.bind(seq, handler)
                self._hotkey_seqs.append(seq)
            except Exception:
                pass

    def _hotkey_bullet(self, _event=None):
        if self._note_view != "edit":
            return None
        self._outline_toggle("bullet")
        return "break"

    def _hotkey_number(self, _event=None):
        if self._note_view != "edit":
            return None
        self._outline_toggle("num")
        return "break"

    def open_hotkey_settings(self):
        """快捷键设置窗口：点按钮后按新组合键即可改绑。"""
        win = getattr(self, "_hk_win", None)
        if win is not None and win.winfo_exists():
            win.lift()
            win.focus_force()
            return
        win = tk.Toplevel(self.root)
        self._hk_win = win
        self._capturing = None
        win.title("快捷键设置")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.attributes("-topmost", True)
        x = self.root.winfo_x() + 24
        y = self.root.winfo_y() + 90
        win.geometry(f"310x180+{x}+{y}")

        tk.Label(win, text="点按钮后，按下想要的组合键（Esc 取消）：",
                 bg=C["bg"], fg=C["muted"], font=self.f_small,
                 anchor="w").pack(fill="x", padx=14, pady=(12, 6))

        self._hk_btns = {}
        for action, label in (("bullet", "•   符号列表"),
                              ("number", "1.   数字编号")):
            row = tk.Frame(win, bg=C["bg"])
            row.pack(fill="x", padx=14, pady=3)
            tk.Label(row, text=label, bg=C["bg"], fg=C["text"],
                     font=self.f_body, anchor="w").pack(side="left")
            b = FlatButton(row, "",
                           command=lambda a=action: self._start_capture(a),
                           bg=C["card"], fg=C["accent"],
                           hover=C["accent_s"], font=self.f_small,
                           padx=10, pady=3, width=16)
            b.pack(side="right")
            self._hk_btns[action] = b
        self._refresh_hk_btns()

        foot = tk.Frame(win, bg=C["bg"])
        foot.pack(fill="x", padx=14, pady=(10, 12), side="bottom")
        FlatButton(foot, "恢复默认", command=self._reset_hotkeys,
                   bg=C["card"], fg=C["muted"], hover=C["hover"],
                   font=self.f_small, padx=10, pady=3).pack(side="left")
        FlatButton(foot, "关闭", command=self._close_hk_win,
                   bg=C["card"], fg=C["accent"], hover=C["accent_s"],
                   font=self.f_small, padx=16, pady=3).pack(side="right")
        win.bind("<KeyPress>", self._on_hotkey_capture)
        win.focus_force()

    def _close_hk_win(self):
        self._capturing = None
        win = getattr(self, "_hk_win", None)
        if win is not None and win.winfo_exists():
            win.destroy()

    def _current_hotkeys(self):
        hk = dict(DEFAULT_HOTKEYS)
        hk.update(self.ui.get("hotkeys") or {})
        return hk

    def _refresh_hk_btns(self):
        hk = self._current_hotkeys()
        for action, b in self._hk_btns.items():
            if self._capturing == action:
                b.configure(text="按下新快捷键…", fg=C["pin"])
            else:
                b.configure(text=hk.get(action, "未设置"), fg=C["accent"])

    def _start_capture(self, action):
        self._capturing = action
        self._refresh_hk_btns()
        self.set_status("按下新的快捷键（Esc 取消）")

    def _cancel_capture(self):
        self._capturing = None
        self._refresh_hk_btns()

    def _on_hotkey_capture(self, event):
        if not self._capturing:
            return None
        if event.keysym == "Escape":
            self._cancel_capture()
            self.set_status("已取消")
            return "break"
        spec = event_to_hotkey(event)
        if spec is None:
            return "break"                  # 只按了修饰键：继续等
        if not ("Ctrl" in spec or "Alt" in spec):
            self.set_status("快捷键至少要带 Ctrl 或 Alt，再试一次")
            return "break"                  # 保持捕获状态
        action = self._capturing
        hotkeys = self._current_hotkeys()
        other = "number" if action == "bullet" else "bullet"
        if hotkeys.get(other) == spec:
            self._capturing = None
            self._refresh_hk_btns()
            self.set_status(f"{spec} 已被另一项占用，换一个吧")
            return "break"
        hotkeys[action] = spec
        self.ui["hotkeys"] = hotkeys
        self._capturing = None
        self._refresh_hk_btns()
        self._bind_custom_hotkeys()
        self.schedule_save()
        self.set_status(f"快捷键已改为 {spec}")
        return "break"

    def _reset_hotkeys(self):
        self.ui["hotkeys"] = dict(DEFAULT_HOTKEYS)
        self._capturing = None
        self._refresh_hk_btns()
        self._bind_custom_hotkeys()
        self.schedule_save()
        self.set_status("快捷键已恢复默认")

    def _zoom_text(self, event):
        size = int(self.ui.get("font_size", 10)) + (1 if event.delta > 0 else -1)
        self.set_font_size(max(8, min(16, size)))

    # ------------------------------------------------------------------ #
    # 树视图渲染
    # ------------------------------------------------------------------ #
    def _render_note_cards(self):
        y = self.notes_canvas.yview()
        for w in self.notes_inner.winfo_children():
            w.destroy()
        books = self.data["books"]
        total = count_notes(books)
        self.lbl_note_count.configure(text=f"共 {total} 篇")
        cur = self.data.get("active_note")
        if total == 0:
            tk.Label(self.notes_inner, text="还没有笔记\n点知识库那行的 ＋ 新建一篇",
                     bg=C["bg"], fg=C["faint"], font=self.f_small,
                     justify="center").pack(pady=48)
        for book in books:
            self._book_row(book)
            if book.get("expanded", True):
                if not book["notes"]:
                    tk.Label(self.notes_inner, text="（暂无笔记，点 ＋ 新建）",
                             bg=C["bg"], fg=C["faint"], font=self.f_tiny,
                             anchor="w").pack(fill="x", padx=(30, 0), pady=2)
                else:
                    self._note_nodes(book, book["notes"], 1, cur)
        self.notes_canvas.update_idletasks()
        self._clamp_tree_scroll(y[0])      # 内容不足一屏回顶，避免滚出空白
        self._bind_wheel_tree(self.notes_inner)

    def _bind_hover(self, parts, flats, normal, hover):
        """整行悬停高亮：Frame/Label 与内部按钮一起换底色。"""
        def on_enter(_=None):
            for w in parts:
                w.configure(bg=hover)
            for b in flats:
                b._bg = hover
                b.configure(bg=hover)

        def on_leave(_=None):
            for w in parts:
                w.configure(bg=normal)
            for b in flats:
                b._bg = normal
                b.configure(bg=normal)

        for w in list(parts) + list(flats):
            w.bind("<Enter>", on_enter, add="+")
            w.bind("<Leave>", on_leave, add="+")

    def _book_row(self, book):
        row = tk.Frame(self.notes_inner, bg=C["bg"])
        row.pack(fill="x", pady=(7, 1), padx=(2, 2))
        arrow = ARROW_OPEN if book.get("expanded", True) else ARROW_CLOSE
        name = (book.get("name") or "未命名").strip()
        if len(name) > 14:
            name = name[:14] + "…"

        head = FlatButton(row, arrow, command=lambda b=book: self._toggle_book(b),
                          bg=C["bg"], fg=C["muted"], hover=C["hover"],
                          font=self.f_small, padx=3, pady=1)
        head.pack(side="left")
        lbl = tk.Label(row, text=f"📚 {name}", bg=C["bg"], fg=C["text"],
                       font=self.f_bold, anchor="w", cursor="hand2", padx=2)
        lbl.pack(side="left")
        plus = FlatButton(row, "＋", command=lambda b=book: self.new_note(book=b),
                          bg=C["bg"], fg=C["faint"], hover=C["hover"],
                          font=self.f_small, padx=6, pady=0)
        plus.pack(side="right")
        Tooltip(plus, "在此知识库新建笔记")

        self._bind_hover([row, lbl], [head, plus], C["bg"], C["hover"])
        for w in (row, lbl):
            w.bind("<Button-1>", lambda e, b=book: self._toggle_book(b))
            w.bind("<Button-3>",
                   lambda e, b=book: self._menu_book(e, b))

    def _note_nodes(self, book, nodes, depth, cur):
        for n in nodes:
            self._note_row(book, n, depth, cur)
            if n.get("expanded", True) and n.get("children"):
                self._note_nodes(book, n["children"], depth + 1, cur)

    def _note_row(self, book, n, depth, cur):
        active = n["id"] == cur
        base = C["accent_s"] if active else C["card"]
        hover = C["accent_s"] if active else C["hover"]
        row = tk.Frame(self.notes_inner, bg=base)
        row.pack(fill="x", pady=1, padx=(2, 2))
        parts = [row]

        # 当前笔记：左侧色条
        bar = tk.Frame(row, width=3, bg=(C["accent"] if active else base))
        bar.pack(side="left", fill="y")
        if not active:
            parts.append(bar)

        # 层级引导线：每深一层多一条细竖线
        for _ in range(depth):
            ln = tk.Frame(row, width=1, bg=C["border"])
            ln.pack(side="left", fill="y", padx=(5, 6))
            parts.append(ln)

        kids = n.get("children") or []
        flats = []
        if kids:
            arrow = ARROW_OPEN if n.get("expanded", True) else ARROW_CLOSE
            btn = FlatButton(row, arrow,
                             command=lambda x=n: self._toggle_note(x),
                             bg=base, fg=C["muted"], hover=C["hover"],
                             font=self.f_tiny, padx=4, pady=1)
            btn.pack(side="left", padx=(2, 0))
            flats.append(btn)
        else:
            dot = tk.Label(row, text="·", bg=base, fg=C["faint"],
                           font=self.f_tiny, padx=4)
            dot.pack(side="left", padx=(2, 0))
            parts.append(dot)

        title = (n.get("title") or "").strip() or "无标题"
        if len(title) > 16:
            title = title[:16] + "…"
        lbl = tk.Label(row, text=title, bg=base,
                       fg=C["accent"] if active else C["text"],
                       font=(self.f_bold if (kids or active) else self.f_body),
                       anchor="w", cursor="hand2", padx=2, pady=4)
        lbl.pack(side="left")
        parts.append(lbl)

        plus = FlatButton(row, "＋",
                          command=lambda b=book, x=n: self.new_note(
                              parent=x, book=b),
                          bg=base, fg=C["faint"], hover=C["accent_s"],
                          font=self.f_small, padx=6, pady=0)
        plus.pack(side="right", padx=(0, 2))
        flats.append(plus)
        Tooltip(plus, "新建子笔记")

        self._bind_hover(parts, flats, base, hover)
        for w in (row, lbl):
            w.bind("<Button-1>", lambda e, i=n["id"]: self._open_note(i))
            w.bind("<Button-3>",
                   lambda e, x=n, b=book: self._menu_note(e, x, b))

    # -- 滚动 ----------------------------------------------------------- #
    def _tree_scroll(self, event):
        """滚轮：内容不足一屏时不动，避免滚出空白。"""
        c = self.notes_canvas
        bbox = c.bbox("all")
        if bbox and (bbox[3] - bbox[1]) > c.winfo_height():
            c.yview_scroll(-2 if event.delta > 0 else 2, "units")
        return "break"

    def _clamp_tree_scroll(self, keep):
        """内容不足一屏时强制回顶；否则恢复之前位置（越界自动钳制）。"""
        c = self.notes_canvas
        bbox = c.bbox("all")
        if not bbox:
            return
        if (bbox[3] - bbox[1]) <= c.winfo_height():
            c.yview_moveto(0.0)
        elif keep is not None:
            c.yview_moveto(keep)

    def _bind_wheel_tree(self, widget):
        """把滚轮事件绑到树里所有子控件，鼠标停在行上也能滚。"""
        widget.bind("<MouseWheel>", self._tree_scroll)
        for ch in widget.winfo_children():
            self._bind_wheel_tree(ch)

    def _toggle_book(self, book):
        book["expanded"] = not book.get("expanded", True)
        self._render_note_cards()
        self.schedule_save()

    def _toggle_note(self, note):
        note["expanded"] = not note.get("expanded", True)
        self._render_note_cards()
        self.schedule_save()

    # ------------------------------------------------------------------ #
    # 右键菜单
    # ------------------------------------------------------------------ #
    def _tree_menu(self):
        m = tk.Menu(self.root, tearoff=0, bg=C["card"], fg=C["text"],
                    activebackground=C["accent_s"],
                    activeforeground=C["accent"], bd=0, relief="flat",
                    font=self.f_body)
        return m

    def _menu_book(self, event, book):
        m = self._tree_menu()
        m.add_command(label="＋  新建笔记",
                      command=lambda: self.new_note(book=book))
        m.add_command(label="✏  重命名知识库",
                      command=lambda: self._rename_book(book))
        m.add_separator()
        m.add_command(label="🗑  删除知识库",
                      command=lambda: self._delete_book(book))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _menu_note(self, event, note, book):
        m = self._tree_menu()
        m.add_command(label="＋  新建子笔记",
                      command=lambda: self.new_note(parent=note, book=book))
        m.add_command(label="✏  重命名",
                      command=lambda: self._rename_note_obj(note))
        m.add_separator()
        m.add_command(label="🗑  删除（含子笔记）",
                      command=lambda: self._delete_note_id(note["id"]))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    # ------------------------------------------------------------------ #
    # 增删改
    # ------------------------------------------------------------------ #
    def select_note(self, nid):
        self._open_note(nid)

    def new_book(self):
        self.sync_note()
        name = simpledialog.askstring("新建知识库", "知识库名称：",
                                      initialvalue="新知识库",
                                      parent=self.root)
        if name is None:
            return
        name = name.strip() or "新知识库"
        book = storage.new_book(name)
        self.data["books"].append(book)
        self._render_note_cards()
        self.schedule_save()
        self.set_status(f"已新建知识库「{name}」，点 ＋ 加笔记")

    def new_note(self, parent=None, book=None):
        """新建笔记：parent 为 None 时放进知识库根（默认当前知识库）。"""
        self.sync_note()
        books = self.data["books"]
        if book is None:
            book = find_book(books, self.data.get("active_book")) or books[0]
        note = storage.new_note("", "")
        if parent is None:
            book["notes"].insert(0, note)
        else:
            parent.setdefault("children", []).insert(0, note)
            parent["expanded"] = True
        book["expanded"] = True
        self.data["active_book"] = book["id"]
        self.data["active_note"] = note["id"]
        self._note_view = "edit"
        self.note_list_view.pack_forget()
        self.note_edit_view.pack(fill="both", expand=True)
        self._load_notes()
        self.ent_title.focus_set()
        self.set_status("已新建，先写个标题吧")
        self.schedule_save()

    def _rename_book(self, book):
        name = simpledialog.askstring(
            "重命名知识库", "知识库名称：",
            initialvalue=book.get("name", ""), parent=self.root)
        if name is not None:
            book["name"] = name.strip() or "未命名"
            self._render_note_cards()
            self.schedule_save()

    def _rename_note_obj(self, note):
        name = simpledialog.askstring(
            "重命名笔记", "笔记名称：",
            initialvalue=note.get("title", ""), parent=self.root)
        if name is not None:
            note["title"] = name.strip()
            note["updated"] = stamp()
            if self.data.get("active_note") == note["id"]:
                self.var_note_title.set(note["title"])
                self.lbl_crumb.configure(text=self._breadcrumb(note["id"]))
            self._render_note_cards()
            self.schedule_save()

    def delete_note(self):
        """删除当前正在编辑的笔记。"""
        n = self.note
        if n is None:
            return
        self._delete_note_id(n["id"])
        if self._note_view == "edit":
            self._show_note_list()

    def _subtree_size(self, note):
        """子树笔记数（含自身）"""
        return 1 + sum(self._subtree_size(c)
                       for c in (note.get("children") or []))

    def _delete_note_id(self, nid):
        hit = find_note(self.data["books"], nid)
        if hit is None:
            return
        book, note, siblings, _parent = hit
        if count_notes(self.data["books"]) <= 1:
            self.set_status("至少保留一篇笔记")
            messagebox.showinfo(APP_NAME, "至少要保留一篇笔记哦",
                                parent=self.root)
            return
        title = (note.get("title") or "无标题").strip()
        total = self._subtree_size(note)
        msg = f"确定删除笔记「{title}」？"
        if total > 1:
            msg += f"\n将连同 {total - 1} 篇子笔记一并删除，无法恢复。"
        else:
            msg += "\n删除后无法恢复。"
        if not messagebox.askyesno(APP_NAME, msg, parent=self.root):
            return
        # 若当前笔记在被删子树里，先挪走
        cur = self.data.get("active_note")
        if cur and (cur == nid or self._in_subtree(note, cur)):
            self.data["active_note"] = None
        siblings.remove(note)
        if self.data.get("active_note") is None:
            nid2 = storage.first_note_id(self.data["books"])
            self.data["active_note"] = nid2
            hit2 = find_note(self.data["books"], nid2)
            if hit2:
                self.data["active_book"] = hit2[0]["id"]
        if self._note_view == "list":
            self._render_note_cards()
        else:
            self._load_notes()
        self.schedule_save()
        self.set_status("已删除")

    def _in_subtree(self, note, nid):
        for c in (note.get("children") or []):
            if c["id"] == nid or self._in_subtree(c, nid):
                return True
        return False

    def _delete_book(self, book):
        if len(self.data["books"]) <= 1:
            messagebox.showinfo(APP_NAME, "至少要保留一个知识库哦",
                                parent=self.root)
            return
        cnt = storage.count_book_notes(book)
        name = (book.get("name") or "未命名").strip()
        msg = f"确定删除知识库「{name}」？"
        if cnt:
            msg += f"\n其中 {cnt} 篇笔记会一并删除，无法恢复。"
        if not messagebox.askyesno(APP_NAME, msg, parent=self.root):
            return
        was_active = self.data.get("active_book") == book["id"]
        self.data["books"].remove(book)
        if was_active:
            self.data["active_book"] = self.data["books"][0]["id"]
            nid = storage.first_note_id(self.data["books"])
            self.data["active_note"] = nid
            if nid is None:
                # 全空了：给新知识库补一篇空笔记
                bk = self.data["books"][0]
                nt = storage.new_note("", "")
                bk["notes"].append(nt)
                self.data["active_note"] = nt["id"]
        self.data["active_note"] = self.data.get("active_note") or \
            storage.first_note_id(self.data["books"])
        self._show_note_list()
        self.schedule_save()
        self.set_status(f"已删除知识库「{name}」")

    def rename_note(self):
        """重命名当前笔记（供外部调用，如未来加按钮）"""
        n = self.note
        if n is not None:
            self._rename_note_obj(n)

    def clear_note(self):
        if messagebox.askyesno(APP_NAME, "清空当前笔记的全部内容？",
                               parent=self.root):
            self.txt.delete("1.0", "end")
