# -*- coding: utf-8 -*-
"""便签页：列表视图 + 编辑视图。

以 Mixin 形式混入 PinNote 主类，与主窗口共享
self.data / self.root / self.schedule_save() 等。
"""

import tkinter as tk
from tkinter import messagebox, simpledialog

from .config import APP_NAME, C
from .storage import new_id, stamp
from .widgets import FlatButton, Tooltip


class NotePageMixin:
    """便签页的界面构建与业务逻辑"""

    # ------------------------------------------------------------------ #
    # 界面
    # ------------------------------------------------------------------ #
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
            lambda e: self.notes_canvas.itemconfigure(self.notes_win,
                                                      width=e.width))

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
        self.data["active_note"] = nid
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
            self.txt.mark_set("insert", "1.0")
            self.txt.see("1.0")
            self.lbl_note_time.configure(text=n.get("updated", ""))
        finally:
            self._loading = False

    def sync_note(self):
        """把编辑器里的内容写回数据模型"""
        if self._loading:
            return
        n = self.note
        n["content"] = self.txt.get("1.0", "end-1c")
        n["title"] = self.var_note_title.get().strip()
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
    # 卡片列表
    # ------------------------------------------------------------------ #
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
                     wraplength=240, justify="left").pack(anchor="w", padx=6,
                                                         pady=16)
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
                        highlightbackground=(C["accent_s"] if active
                                             else C["border"]))
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

        dele = FlatButton(card, "✕",
                          command=lambda: self._delete_note_id(n["id"]),
                          bg=C["card"], fg=C["faint"], hover="#F3D9D4",
                          font=self.f_small, padx=7, pady=0)
        dele.pack(side="right", fill="y", padx=(2, 2))

        for w in (card, body):
            w.bind("<Button-1>", lambda e, i=n["id"]: self._open_note(i))
        for w in body.winfo_children():
            w.bind("<Button-1>", lambda e, i=n["id"]: self._open_note(i))

    # ------------------------------------------------------------------ #
    # 增删改
    # ------------------------------------------------------------------ #
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
        cur = self.var_note_title.get()
        name = simpledialog.askstring("重命名", "便签名称：",
                                      initialvalue=cur, parent=self.root)
        if name is not None:
            self.var_note_title.set(name.strip() or "无标题")

    def delete_note(self):
        if len(self.data["notes"]) <= 1:
            messagebox.showinfo(APP_NAME, "至少要保留一个便签哦",
                                parent=self.root)
            return
        title = (self.note.get("title") or "无标题").strip()
        if not messagebox.askyesno(APP_NAME,
                                   f"确定删除便签「{title}」？\n删除后无法恢复。",
                                   parent=self.root):
            return
        self._delete_note_id(self.data["active_note"])
        self._show_note_list()
        self.set_status("已删除便签")

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

    def clear_note(self):
        if messagebox.askyesno(APP_NAME, "清空当前便签的全部内容？",
                               parent=self.root):
            self.txt.delete("1.0", "end")
