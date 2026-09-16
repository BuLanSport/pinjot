# -*- coding: utf-8 -*-
"""PinNote 启动入口（兼容旧的双击启动方式）。

真正的实现拆分在 pinnote/ 包里：
  pinnote/config.py    常量与配色
  pinnote/storage.py   数据读写
  pinnote/widgets.py   通用小部件
  pinnote/notes_page.py 便签页
  pinnote/plan_page.py   计划页
  pinnote/window.py      主窗口

启动方式：`python pin_note.py` 或 `python -m pinnote`
"""

from pinnote import main

if __name__ == "__main__":
    main()
