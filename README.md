# PinJot · 钉记

> 把想法钉在屏幕上。

PinJot 是一个 Windows 桌面悬浮便签：一个无边框的小窗口，可以像图钉一样
钉在所有窗口最上层，随手记笔记、列计划。无第三方依赖，装好 Python 就能跑。

---

## 功能

### 外观
- 6 套内置配色主题：**暖纸、素灰、深色、护眼绿、樱花、海蓝**
- 右键 → `🎨 颜色主题` 即时切换，不用重启
- 主题选择会记住，下次打开还是它

### 窗口
- 无边框小巧悬浮窗，可拖标题栏移动、拖右下角 `◢` 缩放
- 📌 一键置顶，钉在所有窗口最上层
- 点 `—` 隐藏到系统托盘，桌面不留痕迹；点托盘图标唤回
- 位置、大小、透明度、字号全部自动记忆
- Win11 下自动圆角

### 保存
- 停止输入 0.6 秒后自动落盘，不需要手动保存
- 隐藏到托盘、退出程序时都会再保存一次
- 另有 30 秒定时兜底，异常中断最多丢 30 秒内的改动
- 状态栏会显示「已保存 · 时间」，`Ctrl + S` 可手动立即保存

### 托盘
- 左键点托盘图标：显示 / 隐藏窗口（等同于 `Ctrl + Alt + N`）
- 右键点托盘图标：菜单可保存、打开数据目录、退出
- 托盘用纯 ctypes 调 Win32 实现，没有引入 pystray 等依赖
- 若图标被 Win11 折叠进 `^` 溢出区，把它拖到任务栏上即可常驻

### 便签
- 多便签管理：列表卡片视图（标题 / 摘要 / 更新时间），点卡片进入编辑
- 卡片上直接删除，编辑视图内也可删除
- 边打字边自动保存，关掉再打开还在
- 主文件损坏时自动从备份恢复

### 计划
- 每行就是一个输入框，回车在下方插入新行并自动跳过去
- 自动编号，双击序号可重新编辑已提交的条目
- 圆形勾选框，完成的条目变灰加删除线
- 进度条 + 完成计数，一键清空已完成
- 空行退格删除该行

---

## 快速开始

```bash
# 依赖：Python 3.8+（仅标准库 tkinter，无需 pip install）
python pin_note.py       # 直接运行
python -m pinjot         # 或者以模块方式运行
```

Windows 下也可以双击 `启动便签.bat`（用 `pyw` 启动，不弹控制台窗口）。

---

## 打包成独立应用

不想装 Python 的话，可以打包成单个 exe：

```bash
build.bat                 # 或手动执行下面两步
pip install pyinstaller pillow
python tools/make_icon.py
pyinstaller --onefile --noconsole --name PinJot --icon assets/pinjot.ico pin_note.py
```

产物在 `dist\PinJot.exe`，约 11 MB，双击即用，拷到别的 Windows 电脑上也能跑。

- 图标由 `tools/make_icon.py` 用代码绘制（配色和 `config.py` 一致），
  改主题后重新跑一次即可生成新图标
- 打包后的数据仍存在 `%APPDATA%\PinJot\`，和脚本版共用同一份数据

---

## 快捷键

| 按键 | 作用 |
| --- | --- |
| `Ctrl + Alt + N` | 全局显示 / 隐藏窗口 |
| `Ctrl + N` | 新建便签 |
| `Ctrl + S` | 立即保存 |
| `Ctrl + Z` | 撤销输入 |
| `Ctrl + 滚轮` | 调整正文字号 |

> `Ctrl + Alt + N` 是系统级热键，窗口隐藏时也能唤回。

---

## 项目结构

```
pinjot/
  __init__.py        包说明，导出 PinJot / main
  __main__.py        支持 python -m pinjot
  config.py          常量与配色 ← 想换主题只动这里
  storage.py         数据读写 / 原子写入 / 备份恢复 / 旧版迁移
  widgets.py         通用小部件（FlatButton / Tooltip）
  tray.py            系统托盘图标（纯 ctypes 调 Win32）
  notes_page.py      便签页（NotePageMixin）
  plan_page.py       计划页（PlanPageMixin）
  window.py          主窗口 PinJot：骨架、窗口行为、保存调度
pin_note.py          启动入口
tools/make_icon.py   用代码绘制应用图标
assets/              图标文件（.ico / 预览 .png）
启动便签.bat          Windows 双击启动
build.bat             一键打包 exe
```

分层原则：`config` / `storage` / `widgets` 是底层，不依赖页面；
两个页面以 Mixin 形式混入主类（tkinter 页面逻辑强依赖共享状态）；
`window.py` 只负责骨架与窗口行为，不含业务细节。新增功能请放进
对应的模块，不要往 `window.py` 里堆。

---

## 数据存储

数据保存在 JSON 里，路径：

```
%APPDATA%\PinJot\data.json
```

- 每次保存前会把上一份备份为 `data.json.bak`
- 主文件损坏时启动会自动回退到备份
- 旧版本（数据在 `%APPDATA%\PinNote`）首次启动会自动迁移，无需手动处理

## 换主题 / 加主题

内置主题都在 `pinjot/config.py` 的 `THEMES` 字典里，每套 13 个色值。
想加一套：往 `THEMES` 加一项、往 `THEME_LIST` 加一行即可，其他文件不用动。

```python
"mytheme": {
    "border": "#...", "bg": "#...", "card": "#...", "header": "#...",
    "text": "#...", "muted": "#...", "faint": "#...",
    "accent": "#...", "accent_s": "#...", "pin": "#...",
    "ok": "#...", "danger": "#...", "hover": "#...",
}
```

切换主题时程序会保留位置、尺寸、当前标签页和便签编辑状态，原地重建界面。

---

## 设计取舍

- **为什么用 tkinter 而不是 Electron / Qt？**
  目标是一个 300×450 的小工具，标准库零依赖意味着拷过去就能跑，启动也快。
- **为什么页面用 Mixin 而不是独立类？**
  页面逻辑强依赖窗口的共享状态（数据、保存调度、字体），Mixin 能让
  页面代码像写在主类里一样自然，同时文件边界依然清晰。
- **为什么计划页不用下拉添加框？**
  「输入 → 回车 → 下一行」更接近纸笔习惯，省一次聚焦切换。

---

## License

MIT
