"""
generate_masks.py
의상 마스크 PNG 자동 생성 (64×64 Minecraft UV)
로컬에서 한 번만 실행: python generate_masks.py
"""

import numpy as np
from PIL import Image
from pathlib import Path

OUT = Path("baseskin")

# ── 존 색상 ───────────────────────────────────────────────────────
TOP  = (0,   255, 0,   255)   # 상의  (green)
BOT  = (0,   0,   255, 255)   # 하의  (blue)
SHOE = (255, 255, 0,   255)   # 신발  (yellow)
ACC  = (255, 0,   255, 255)   # 악세서리 (magenta)

# ── 픽셀 헬퍼 ────────────────────────────────────────────────────
def new_mask():
    return np.zeros((64, 64, 4), dtype=np.uint8)

def fill(m, x, y, w, h, color):
    m[y:y+h, x:x+w] = color

def save(m, name):
    Image.fromarray(m, "RGBA").save(OUT / name)
    print(f"  saved {name}")

# ── UV 좌표 상수 ──────────────────────────────────────────────────
# 몸통 (Body layer1)
BODY = dict(top=(20,16,8,4), front=(20,20,8,12), right=(16,20,4,12),
            left=(28,20,4,12), back=(32,20,8,12))
# 오른팔 (Right Arm layer1)
RARM = dict(top=(44,16,4,4), front=(44,20,4,12), right=(40,20,4,12),
            left=(48,20,4,12), back=(52,20,4,12))
# 왼팔 (Left Arm layer1, y=48..64)
LARM = dict(top=(36,48,4,4), front=(36,52,4,12), left=(32,52,4,12),
            right=(40,52,4,12), back=(44,52,4,12))
# 오른다리 (Right Leg layer1)
RLEG = dict(top=(4,16,4,4), front=(4,20,4,12), right=(0,20,4,12),
            left=(8,20,4,12), back=(12,20,4,12))
# 왼다리 (Left Leg layer1, y=48..64)
LLEG = dict(top=(20,48,4,4), front=(20,52,4,12), left=(16,52,4,12),
            right=(24,52,4,12), back=(28,52,4,12))

def fill_part(m, part_dict, faces, color, y_clip_min=None, y_clip_max=None):
    """part_dict에서 faces 목록 fill. y_clip으로 세로 클리핑."""
    for face in faces:
        x, y, w, h = part_dict[face]
        if y_clip_min is not None:
            y_start = max(y, y_clip_min)
            h = h - (y_start - y)
            y = y_start
        if y_clip_max is not None:
            h = min(h, y_clip_max - y)
        if h > 0:
            fill(m, x, y, w, h, color)

ALL_FACES = ["top", "front", "right", "left", "back"]
SIDE_FACES = ["front", "right", "left", "back"]

# ── 상의 그리기 함수 ──────────────────────────────────────────────
def draw_longsleeve(m, shirt_bottom=32):
    """긴팔 셔츠: 몸통 + 전체 팔"""
    fill_part(m, BODY, ALL_FACES, TOP, y_clip_max=shirt_bottom)
    fill_part(m, RARM, ALL_FACES, TOP)
    fill_part(m, LARM, ALL_FACES, TOP)

def draw_shortsleeve(m, shirt_bottom=32):
    """반팔: 몸통 + 팔 절반"""
    fill_part(m, BODY, ALL_FACES, TOP, y_clip_max=shirt_bottom)
    # 오른팔: y=20..26 (절반)
    fill_part(m, RARM, ALL_FACES, TOP, y_clip_max=26)
    # 왼팔: y=52..58 (절반)
    fill_part(m, LARM, ALL_FACES, TOP, y_clip_max=58)

def draw_sleeveless(m, shirt_bottom=32):
    """민소매: 몸통만"""
    fill_part(m, BODY, ALL_FACES, TOP, y_clip_max=shirt_bottom)

def draw_crop(m):
    """크롭탑: 몸통 위 절반 + 반팔"""
    fill_part(m, BODY, ALL_FACES, TOP, y_clip_max=27)
    fill_part(m, RARM, ALL_FACES, TOP, y_clip_max=26)
    fill_part(m, LARM, ALL_FACES, TOP, y_clip_max=58)

def draw_crop_sleeveless(m):
    """오프숄더 크롭: 몸통 위 절반만"""
    fill_part(m, BODY, ALL_FACES, TOP, y_clip_max=27)

def draw_jacket(m):
    """재킷/코트/카디건: 몸통 y=16..28(허리선 위까지) + 전체 팔.
    body y=28..32는 비워 두어 하의(반바지/치마) BOT 존이 칠해지게 함."""
    fill_part(m, BODY, ALL_FACES, TOP, y_clip_max=28)
    fill_part(m, RARM, ALL_FACES, TOP)
    fill_part(m, LARM, ALL_FACES, TOP)

# ── 하의 그리기 함수 ──────────────────────────────────────────────
def draw_longpants(m):
    """긴바지: 몸통 하단 + 전체 다리(신발 바로 위까지), 신발"""
    fill_part(m, BODY, SIDE_FACES, BOT, y_clip_min=28)
    fill_part(m, RLEG, ALL_FACES,  BOT, y_clip_max=30)  # 30 = 신발(30..32) 시작점
    fill_part(m, LLEG, ALL_FACES,  BOT, y_clip_max=62)  # 62 = 신발(62..64) 시작점
    draw_shoes(m)

def draw_shorts(m):
    """반바지: 몸통 하단 + 다리 상단 4줄(허벅지 상부만), 신발"""
    fill_part(m, BODY, SIDE_FACES, BOT, y_clip_min=28)
    fill_part(m, RLEG, ALL_FACES,  BOT, y_clip_max=24)  # 4/12px — 허벅지 상부
    fill_part(m, LLEG, ALL_FACES,  BOT, y_clip_max=56)
    draw_shoes(m)

def draw_miniskirt(m):
    """짧은 치마: 몸통 하단 + 다리 최상단 2줄(치마 실루엣), 신발"""
    fill_part(m, BODY, SIDE_FACES, BOT, y_clip_min=27)
    fill_part(m, RLEG, ALL_FACES,  BOT, y_clip_max=22)  # 2/12px — 치마 실루엣만
    fill_part(m, LLEG, ALL_FACES,  BOT, y_clip_max=54)
    draw_shoes(m)

def draw_longskirt(m):
    """긴치마: 몸통 하단 + 전체 다리(신발 위까지), 신발"""
    fill_part(m, BODY, SIDE_FACES, BOT, y_clip_min=27)
    fill_part(m, RLEG, ALL_FACES,  BOT, y_clip_max=30)
    fill_part(m, LLEG, ALL_FACES,  BOT, y_clip_max=62)
    draw_shoes(m)

def draw_shoes(m):
    """신발: 다리 하단 2줄(y=30..32/62..64) + 발바닥(밑창)"""
    fill_part(m, RLEG, SIDE_FACES, SHOE, y_clip_min=30)
    fill_part(m, LLEG, SIDE_FACES, SHOE, y_clip_min=62)
    fill(m,  8, 16, 4, 4, SHOE)   # 오른발 밑창 (RLEG bottom face)
    fill(m, 24, 48, 4, 4, SHOE)   # 왼발 밑창 (LLEG bottom face)

def draw_boots(m):
    """부츠: 다리 하단 6줄 (발목까지)"""
    fill_part(m, RLEG, SIDE_FACES, SHOE, y_clip_min=26)
    fill_part(m, LLEG, SIDE_FACES, SHOE, y_clip_min=58)

# ── 악세서리 오버레이 함수 ───────────────────────────────────────
def acc_watch(m):
    """시계: 오른팔 손목 안쪽 1줄"""
    # 오른팔 front 하단 y=30..31
    fill(m, 44, 30, 4, 1, ACC)
    # 왼팔 front 하단 y=62..63
    fill(m, 36, 62, 4, 1, ACC)

def acc_necklace(m):
    """목걸이: 몸통 앞면 상단 가운데"""
    fill(m, 22, 20, 4, 1, ACC)   # 앞면 목 부분 1줄

def acc_earrings(m):
    """귀걸이: 헤드 사이드 하단"""
    fill(m, 0, 14, 2, 2, ACC)   # 왼쪽 귀
    fill(m, 14, 14, 2, 2, ACC)  # 오른쪽 귀

def acc_belt(m):
    """벨트: 몸통 앞면 허리 1줄"""
    fill(m, 20, 27, 8, 1, ACC)
    fill(m, 16, 27, 4, 1, ACC)
    fill(m, 28, 27, 4, 1, ACC)

# ── 마스크 생성 정의 ─────────────────────────────────────────────
MASKS = [
    # (파일명, 상의함수, 하의함수)
    # 재킷/카디건 — body y=28..32는 하의 BOT 존으로 비워 둠
    ("mask_jacket.png",              draw_jacket,           draw_longpants),
    ("mask_jacket_shorts.png",       draw_jacket,           draw_shorts),
    ("mask_jacket_skirt.png",        draw_jacket,           draw_miniskirt),
    ("mask_jacket_longskirt.png",    draw_jacket,           draw_longskirt),
    ("mask_longsleeve.png",          draw_longsleeve,       draw_longpants),
    ("mask_longsleeve_shorts.png",   draw_longsleeve,       draw_shorts),
    ("mask_longsleeve_skirt.png",    draw_longsleeve,       draw_miniskirt),
    ("mask_longsleeve_longskirt.png",draw_longsleeve,       draw_longskirt),
    ("mask_shortsleeve.png",         draw_shortsleeve,      draw_longpants),
    ("mask_shortsleeve_shorts.png",  draw_shortsleeve,      draw_shorts),
    ("mask_shortsleeve_skirt.png",   draw_shortsleeve,      draw_miniskirt),
    ("mask_shortsleeve_longskirt.png",draw_shortsleeve,     draw_longskirt),
    ("mask_sleeveless.png",          draw_sleeveless,       draw_longpants),
    ("mask_sleeveless_shorts.png",   draw_sleeveless,       draw_shorts),
    ("mask_sleeveless_skirt.png",    draw_sleeveless,       draw_miniskirt),
    ("mask_sleeveless_longskirt.png",draw_sleeveless,       draw_longskirt),
    ("mask_crop_long.png",           draw_crop,             draw_longpants),
    ("mask_crop_shorts.png",         draw_crop,             draw_shorts),
    ("mask_crop_skirt.png",          draw_crop,             draw_miniskirt),
    ("mask_crop_long_shorderless.png", draw_crop_sleeveless, draw_longpants),
    ("mask_crop_shorts_shorderless.png", draw_crop_sleeveless, draw_shorts),
    ("mask_shorts.png",              draw_shortsleeve,      draw_shorts),    # 기존 호환
    ("mask_shortsskirt.png",         draw_shortsleeve,      draw_miniskirt), # 기존 호환
    ("mask_longskirt.png",           draw_longsleeve,       draw_longskirt), # 기존 호환
]

# 악세서리 전용 오버레이 마스크 (의상 없이 ACC 픽셀만)
ACC_MASKS = [
    ("mask_acc_watch.png",     acc_watch),
    ("mask_acc_necklace.png",  acc_necklace),
    ("mask_acc_earrings.png",  acc_earrings),
    ("mask_acc_belt.png",      acc_belt),
    ("mask_acc_boots.png",     draw_boots),
]

if __name__ == "__main__":
    print("=== 의상 마스크 생성 ===")
    for fname, top_fn, bot_fn in MASKS:
        m = new_mask()
        top_fn(m)
        bot_fn(m)
        save(m, fname)

    print("\n=== 악세서리 마스크 생성 ===")
    for fname, acc_fn in ACC_MASKS:
        m = new_mask()
        acc_fn(m)
        save(m, fname)

    print(f"\n완료: {len(MASKS) + len(ACC_MASKS)}개 마스크 생성")
