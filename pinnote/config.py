# -*- coding: utf-8 -*-
"""常量与配色。改主题只需要动这个文件。"""

import sys

APP_NAME = "PinNote"
APP_TITLE = "我的便签"
IS_WIN = sys.platform.startswith("win")

# 配色：暖米白纸感
C = {
    "border":   "#E2DCCF",  # 窗口描边
    "bg":       "#FBF9F4",  # 主背景
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

# 窗口尺寸（逻辑像素）
MIN_W, MIN_H = 228, 190
DEF_W, DEF_H = 330, 450
HDR_H = 36
TAB_H = 30
STA_H = 22

FONT_FAMILY = "Segoe UI"

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
