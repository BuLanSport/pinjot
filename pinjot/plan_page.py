# -*- coding: utf-8 -*-
"""计划页：行内编辑的待办清单。

以 Mixin 形式混入 PinNote 主类。
"""

import tkinter as tk

from .config import C, FONT_FAMILY
from .storage import new_id, stamp
from .widgets import FlatButton, Tooltip


class PlanPageMixin:
    """计划页的界面构建与业务逻辑"""

    TASK_PH = "添加新计划，按回车确认"

    # ------------------------------------------------------------------ #
    # 界面
    # ------------------------------------------------------------------ #
    def _build_plan_page(self, page):
        top = tk.Frame(page, bg=C["bg"])
        top.pack(fill="x", padx=10, pady=(8, 2))

        self.lbl_prog = tk.Label(top, text="0 / 0 已完成", bg=C["bg"],
                                 fg=C["muted"], font=self.f_small, anchor="w")
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

        # 任务列表（滚轮滚动，无滚动条保持简洁）
        self.task_canvas = tk.Canvas(page, bg=C["bg"], highlightthickness=0,
                                     bd=0)
        self.task_canvas.pack(fill="both", expand=True, padx=(8, 6),
                              pady=(0, 2))
        self.task_inner = tk.Frame(self.task_canvas, bg=C["bg"])
        self.task_win = self.task_canvas.create_window(
            (0, 0), window=self.task_inner, anchor="nw")
        self.task_inner.bind(
            "<Configure>",
            lambda e: self.task_canvas.configure(
                scrollregion=self.task_canvas.bbox("all")))
        self.task_canvas.bind(
            "<Configure>",
            lambda e: self.task_canvas.itemconfigure(self.task_win,
                                                     width=e.width))
        self.root.bind_all("<MouseWheel>", self._on_wheel, add="+")

    # ------------------------------------------------------------------ #
    # 渲染
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
            tasks.append(self._new_task(""))
        if tasks[-1]["text"]:
            tasks.append(self._new_task(""))     # 末尾常驻一个添加行
        n = 0
        for i, t in enumerate(tasks):
            if t["text"]:
                n += 1
            self._task_row(t, n, last=(i == len(tasks) - 1))
        self._update_progress()

    @staticmethod
    def _new_task(text=""):
        return {"id": new_id(), "text": text, "done": False,
                "created": stamp()}

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
            num.bind("<Double-Button-1>",
                     lambda e, t=task: self._unlock_row(t))
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
                           FONT_FAMILY, int(self.ui.get("font_size", 10)),
                           "overstrike"))
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
            ent.bind(seq,
                     lambda e, t=task, v=var, s=st: self._row_key(e, t, v, s))
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

    # ------------------------------------------------------------------ #
    # 业务逻辑
    # ------------------------------------------------------------------ #
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
            new = self._new_task("")
            idx = self.data["tasks"].index(task) + 1
            self.data["tasks"].insert(idx, new)
            self._focus_id = new["id"]
            self._render_tasks()
            return "break"
        if event.keysym == "BackSpace" and not text \
                and len(self.data["tasks"]) > 1:
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
