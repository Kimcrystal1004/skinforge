# -*- coding: utf-8 -*-
"""치히로 이름표(육각형 배지)를 레퍼런스로, 이름/색상별 PNG 생성.
- 배경 투명 / 육각형 이름표 배경 + 외곽선 / 이름별 색상 테마
"""
import os
from PIL import Image, ImageDraw, ImageFont

SS = 4  # supersampling
W, H = 470, 140
OUT_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
FONT_PATH = r"C:\Windows\Fonts\malgunbd.ttf"

# 이름별 테마: (파일명, 텍스트, 배경색, 외곽선색, 글자색)
THEMES = [
    ("nameplate_chihiro", "치히로", "#3D7EA6", "#63B6E6", "#FFFFFF"),
    ("nameplate_ppyu",     "쀼쀼",   "#CF80FF", "#EBBBFF", "#FFFFFF"),
    ("nameplate_hannu",    "한누",   "#FDA03E", "#FFD9A0", "#FFFFFF"),
]


def hx(x):
    return int(x[1:3], 16), int(x[3:5], 16), int(x[5:7], 16)


def hexpoly(w, h, tip, notch):
    """가로로 긴 육각형. tip: 좌우 뾰족 폭, notch: 위/아래 여백."""
    return [
        (tip, h / 2),
        (tip + notch, notch),
        (w - tip - notch, notch),
        (w - tip, h / 2),
        (w - tip - notch, h - notch),
        (tip + notch, h - notch),
    ]


def make(name, text, bg, outline, fg):
    w, h = W * SS, H * SS
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    border = 5 * SS
    poly = hexpoly(w, h, 20 * SS, 18 * SS)
    d.polygon(poly, fill=bg, outline=outline, width=border)

    # 상단 하이라이트 (안쪽 위 절반만 살짝 밝게)
    hl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(hl).polygon(poly, fill=(255, 255, 255, 38))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rectangle([0, 0, w, int(h * 0.42)], fill=255)
    img = Image.composite(Image.alpha_composite(img, hl), img, mask)
    d = ImageDraw.Draw(img)

    # 텍스트
    font = ImageFont.truetype(FONT_PATH, 58 * SS)
    sw = 3 * SS
    tb = d.textbbox((0, 0), text, font=font, stroke_width=sw)
    tx = (w - (tb[2] - tb[0])) / 2 - tb[0]
    ty = (h - (tb[3] - tb[1])) / 2 - tb[1]
    r, g, b = hx(bg)
    dark = (r // 3, g // 3, b // 3, 255)
    d.text((tx, ty), text, font=font, fill=fg, stroke_width=sw, stroke_fill=dark)

    img = img.resize((W, H), Image.LANCZOS)
    path = os.path.join(OUT_DIR, name + ".png")
    img.save(path)
    print("saved:", path)


for t in THEMES:
    make(*t)
