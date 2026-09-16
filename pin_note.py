# -*- coding: utf-8 -*-
"""PinJot（钉记）—— 桌面悬浮便签 启动入口。

真正的实现拆分在 pinjot/ 包里：
  pinjot/config.py       常量与配色
  pinjot/storage.py      数据读写
  pinjot/widgets.py      通用小部件
  pinjot/notes_page.py   便签页
  pinjot/plan_page.py    计划页
  pinjot/window.py       主窗口

启动方式：`python pin_note.py` 或 `python -m pinjot`
"""

from pinjot import main

if __name__ == "__main__":
    main()
