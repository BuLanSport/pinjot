# -*- coding: utf-8 -*-
"""PinNote —— 桌面悬浮便签

功能：
  · 无边框小巧悬浮窗，拖标题栏移动、右下角拖拽缩放
  · 📌 一键置顶，钉在所有窗口最上层
  · 「便签」多笔记管理：列表卡片 + 行内编辑，自动保存
  · 「计划」待办清单：序号、回车换行、勾选进度
  · 窗口位置、大小、折叠状态、透明度自动记忆
  · 全局快捷键 Ctrl+Alt+N 显示 / 隐藏

依赖：仅需 Python 3 自带的 tkinter，无需安装任何第三方库。

模块结构：
  config.py       常量与配色（改主题只动这里）
  storage.py      数据读写 / 备份
  widgets.py      通用小部件（FlatButton / Tooltip）
  notes_page.py   便签页（NotePageMixin）
  plan_page.py    计划页（PlanPageMixin）
  window.py       主窗口 PinNote 与程序入口
"""

from .window import PinJot, main

__all__ = ["PinJot", "main"]
__version__ = "1.1.0"
