# -*- coding: utf-8 -*-
"""常量与配色。加主题只需要动这个文件。

C 是「当前主题」的字典，各模块用 `from .config import C` 拿到的是同一个对象，
所以切换主题时用 C.clear() + C.update() 原地修改即可全局生效。
"""

import sys
from pathlib import Path

APP_NAME = "PinJot"      # 同时作为数据目录名（%APPDATA%\PinJot）
APP_TITLE = "钉记"
IS_WIN = sys.platform.startswith("win")

# --------------------------------------------------------------------------- #
# 主题
# --------------------------------------------------------------------------- #
# 每个主题必须包含完全相同的键，否则切主题会有地方漏色
THEMES = {
    "paper": {
        "border":   "#E2DCCF", "bg":     "#FBF9F4", "card":  "#FFFFFF",
        "header":   "#F4F0E6", "text":   "#2E2C28", "muted": "#9C9587",
        "faint":    "#CFC8B9", "accent": "#4C7CF3", "accent_s": "#E9F0FE",
        "pin":      "#E8833A", "ok":     "#3FA96B", "danger": "#E05B4B",
        "hover":    "#ECE6D9",
    },
    "gray": {
        "border":   "#DCDEE3", "bg":     "#F6F7F9", "card":  "#FFFFFF",
        "header":   "#EEF0F3", "text":   "#24272E", "muted": "#8A9099",
        "faint":    "#C4C9D1", "accent": "#4C7CF3", "accent_s": "#E8EFFE",
        "pin":      "#E8833A", "ok":     "#34A853", "danger": "#E05B4B",
        "hover":    "#E4E7EC",
    },
    "dark": {
        "border":   "#2A2E36", "bg":     "#1E2126", "card":  "#272B32",
        "header":   "#22262C", "text":   "#E6E8EB", "muted": "#8B939E",
        "faint":    "#4A5058", "accent": "#6D9BFF", "accent_s": "#2C3A57",
        "pin":      "#F09A4E", "ok":     "#4CAF7D", "danger": "#E06C5B",
        "hover":    "#32373F",
    },
    "green": {
        "border":   "#D5E3D0", "bg":     "#EFF5EC", "card":  "#FBFDF9",
        "header":   "#E4EEE0", "text":   "#27332A", "muted": "#7F8F82",
        "faint":    "#BFCFC0", "accent": "#3E8E5A", "accent_s": "#DCEBDD",
        "pin":      "#D98B3A", "ok":     "#3E8E5A", "danger": "#C9564A",
        "hover":    "#DCE9D7",
    },
    "sakura": {
        "border":   "#F0DCE2", "bg":     "#FDF6F7", "card":  "#FFFFFF",
        "header":   "#FAEDF0", "text":   "#3A2C30", "muted": "#A98D95",
        "faint":    "#E0C8CF", "accent": "#E0678C", "accent_s": "#FBE4EB",
        "pin":      "#E0678C", "ok":     "#4CAF7D", "danger": "#D9534F",
        "hover":    "#F7E2E8",
    },
    "ocean": {
        "border":   "#CFDCE6", "bg":     "#F2F7FA", "card":  "#FFFFFF",
        "header":   "#E6EFF5", "text":   "#22303A", "muted": "#7C8FA0",
        "faint":    "#B8C9D6", "accent": "#2E7DB8", "accent_s": "#DFEDF8",
        "pin":      "#E8833A", "ok":     "#2F9E6E", "danger": "#D9534F",
        "hover":    "#DFEAF2",
    },
}

# 菜单里显示的顺序与中文名
THEME_LIST = [
    ("paper",  "暖纸"),
    ("gray",   "素灰"),
    ("dark",   "深色"),
    ("green",  "护眼绿"),
    ("sakura", "樱花"),
    ("ocean",  "海蓝"),
]
THEME_LABELS = dict(THEME_LIST)
DEFAULT_THEME = "paper"

# 当前主题（各模块共享此对象，切换时必须原地改）
C = dict(THEMES[DEFAULT_THEME])


def use_theme(name) -> str:
    """切换到指定主题，返回实际生效的主题名。"""
    if name not in THEMES:
        name = DEFAULT_THEME
    C.clear()
    C.update(THEMES[name])
    return name


# --------------------------------------------------------------------------- #
# 尺寸
# --------------------------------------------------------------------------- #
MIN_W, MIN_H = 228, 190
DEF_W, DEF_H = 330, 450
HDR_H = 36
TAB_H = 30
STA_H = 22

FONT_FAMILY = "Segoe UI"

WELCOME = """欢迎使用 PinJot 📌

点标题栏左边的图钉，可以把窗口钉在所有窗口最上层。
拖动顶部标题栏移动窗口，拖右下角的 ◢ 可以缩放大小。
点 — 可以把窗口藏进系统托盘，点托盘图标唤回。
写下的内容会自动保存，关掉再打开还在。

小技巧
Ctrl + Alt + N    显示 / 隐藏窗口
Ctrl + N          新建便签
Ctrl + S          立即保存
右键任意位置      设置（主题、透明度、字号）

把这里的内容删掉，开始写你自己的笔记吧。
"""


def resource_path(*parts) -> Path:
    """定位随程序分发的资源文件（打包成 exe 后从临时解压目录取）。"""
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parent.parent
    return root.joinpath(*parts)


ICON_PATH = resource_path("assets", "pinjot.ico")
