# -*- coding: utf-8 -*-
"""生成应用图标 assets/pinjot.ico

用代码画而不是用图片素材，好处是配色和 pinjot/config.py 完全一致，
想改主题时同步改这里的色值重新跑一次即可。

用法：
    pip install pillow
    python tools/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

# 与 pinjot/config.py 保持一致
BG = (76, 124, 243, 255)        # accent  #4C7CF3
NOTE = (255, 255, 255, 255)     # card    #FFFFFF
NOTE_FOLD = (233, 240, 254, 255)  # accent_s
LINE = (201, 214, 245, 255)     # 浅蓝文字行
PIN = (232, 131, 58, 255)       # pin     #E8833A
PIN_DARK = (196, 104, 38, 255)

SIZE = 1024
OUT = Path(__file__).resolve().parent.parent / "assets" / "pinjot.ico"


def rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def build(size=SIZE):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = size / 1024.0          # 以 1024 为基准的缩放单位

    def s(v):
        return int(round(v * u))

    # 圆角底板
    rounded(d, (0, 0, size - 1, size - 1), s(230), BG)

    # 便签纸
    left, top, right, bottom = s(250), s(300), s(774), s(800)
    rounded(d, (left, top, right, bottom), s(48), NOTE)

    # 右下角折角
    fold = s(120)
    d.polygon([(right - fold, bottom), (right, bottom - fold),
               (right, bottom)], fill=NOTE_FOLD)

    # 文字行
    for i, w in enumerate((360, 300, 220)):
        y = s(470 + i * 95)
        rounded(d, (s(330), y, s(330) + s(w), y + s(34)), s(17), LINE)

    # 图钉：针身 + 钉帽
    cx = size // 2
    d.polygon([(cx - s(26), s(330)), (cx + s(26), s(330)),
               (cx + s(10), s(600)), (cx - s(10), s(600))], fill=PIN_DARK)
    d.ellipse((cx - s(120), s(210), cx + s(120), s(450)), fill=PIN)
    d.ellipse((cx - s(60), s(255), cx + s(10), s(325)),
              fill=(255, 255, 255, 110))
    return img


def main():
    img = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, format="ICO",
             sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                    (64, 64), (128, 128), (256, 256)])
    png = OUT.with_suffix(".png")
    img.resize((256, 256), Image.LANCZOS).save(png)
    print("已生成:", OUT)
    print("预览图:", png)


if __name__ == "__main__":
    main()
