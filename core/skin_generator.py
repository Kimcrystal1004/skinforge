"""
skin_generator.py
특징 JSON → Pillow 픽셀 조작 → 64×64 마인크래프트 스킨 PNG
Gemini 이미지 생성 없이 베이스 스킨에 직접 색상을 입힌다.
"""

import numpy as np
from PIL import Image
from pathlib import Path
from colorsys import rgb_to_hsv, hsv_to_rgb
from .recolor_skin import load_base, apply_skin_tone

HAIR_BASE_PATH = Path(__file__).parent.parent / "baseskin" / "base_hair.png"


def load_hair_base() -> np.ndarray:
    img = Image.open(HAIR_BASE_PATH).convert("RGBA")
    return np.array(img, dtype=np.uint8)


def recolor_hair_base(hair_arr: np.ndarray, target_rgb: tuple) -> np.ndarray:
    """베이스 헤어의 H·S를 target_rgb 톤으로 교체하고 V(명암)는 유지"""
    th, ts, _ = rgb_to_hsv(target_rgb[0]/255, target_rgb[1]/255, target_rgb[2]/255)
    result = hair_arr.copy()
    for y in range(64):
        for x in range(64):
            r, g, b, a = hair_arr[y, x]
            if a < 10:
                continue
            _, _, v = rgb_to_hsv(r/255, g/255, b/255)
            nr, ng, nb = hsv_to_rgb(th, ts, v)
            result[y, x] = [int(nr*255), int(ng*255), int(nb*255), a]
    return result

# ── 색상 사전 (한국어 → RGB) ──────────────────────────────────────
COLOR_MAP = {
    "검정": (28, 28, 28), "블랙": (28, 28, 28),
    "흰색": (238, 238, 238), "흰": (238, 238, 238), "화이트": (238, 238, 238),
    "회색": (130, 130, 130), "그레이": (130, 130, 130), "밝은 회색": (180, 180, 180),
    "빨강": (190, 45, 45), "레드": (190, 45, 45),
    "파랑": (50, 90, 190), "블루": (50, 90, 190),
    "네이비": (25, 35, 95), "남색": (25, 35, 95),
    "하늘": (90, 155, 215), "하늘색": (90, 155, 215),
    "초록": (50, 130, 60), "그린": (50, 130, 60),
    "카키": (90, 100, 60),
    "갈색": (110, 65, 35), "브라운": (110, 65, 35),
    "금발": (205, 165, 75), "금색": (205, 165, 75),
    "노랑": (215, 195, 55), "옐로우": (215, 195, 55),
    "주황": (210, 110, 40), "오렌지": (210, 110, 40),
    "분홍": (215, 120, 145), "핑크": (215, 120, 145),
    "보라": (115, 55, 155), "퍼플": (115, 55, 155),
    "베이지": (210, 185, 155),
    "아이보리": (230, 220, 195),
    "민트": (100, 200, 170),
    "연두": (140, 195, 90),
    "자주": (140, 35, 70), "버건디": (115, 25, 45),
    "카멜": (185, 135, 75),
    "청바지": (70, 100, 150), "데님": (70, 100, 150),
    "교복": (30, 40, 100),
}

DEFAULT_COLOR = (100, 100, 100)


def parse_color(text: str) -> tuple:
    """색상 텍스트에서 RGB 추출"""
    if not text:
        return DEFAULT_COLOR
    text = str(text).strip()
    for key, rgb in COLOR_MAP.items():
        if key in text:
            return rgb
    return DEFAULT_COLOR


def shade(rgb: tuple, factor: float) -> tuple:
    """명암 적용"""
    return tuple(max(0, min(255, int(c * factor))) for c in rgb)


def fill_region(arr: np.ndarray, x: int, y: int, w: int, h: int,
                rgb: tuple, alpha_mask: bool = True,
                skip_rows_top: int = 0, skip_rows_bottom: int = 0):
    """UV 영역에 색상 채우기. alpha_mask=True면 투명 픽셀은 건너뜀."""
    r, g, b = rgb
    for py in range(y + skip_rows_top, y + h - skip_rows_bottom):
        for px in range(x, x + w):
            if alpha_mask and arr[py, px, 3] < 10:
                continue
            arr[py, px] = [r, g, b, 255]


def fill_region_overlay(arr: np.ndarray, x: int, y: int, w: int, h: int, rgb: tuple):
    """오버레이 레이어 영역을 투명으로 초기화 후 색상 채우기"""
    for py in range(y, y + h):
        for px in range(x, x + w):
            arr[py, px] = [0, 0, 0, 0]


def draw_hair(arr: np.ndarray, hair_rgb: tuple, hair_style: str):
    """base_hair.png를 목표 색으로 재채색해 스킨에 합성"""
    hair_base = load_hair_base()
    colored = recolor_hair_base(hair_base, hair_rgb)

    # 기본 합성: 헤어 베이스의 불투명 픽셀을 스킨 위에 덮음
    for y in range(64):
        for x in range(64):
            a = int(colored[y, x, 3])
            if a < 10:
                continue
            if a >= 255:
                arr[y, x] = colored[y, x]
            else:
                # 알파 블렌딩 (오버레이 반투명 영역)
                src = colored[y, x, :3].astype(float)
                dst = arr[y, x, :3].astype(float)
                fa = a / 255
                arr[y, x, :3] = (src * fa + dst * (1 - fa)).astype(np.uint8)
                arr[y, x, 3] = 255

    # 긴 머리 — 재킷 뒷면 위쪽 2줄에 머리카락 연장
    style_lower = hair_style.lower() if hair_style else ""
    if any(k in style_lower for k in ["긴", "롱", "웨이브", "컬"]):
        ext_rgb = shade(hair_rgb, 0.60)
        for py in range(36, 38):
            for px in range(32, 40):
                arr[py, px] = [*ext_rgb, 255]


def draw_clothing(arr: np.ndarray, top_rgb: tuple, bottom_rgb: tuple,
                  shoes_rgb: tuple):
    """의상 UV 영역에 색상 적용"""
    # ── 상의 (몸통) ──
    fill_region(arr, 20, 20, 8, 12, shade(top_rgb, 1.0))   # 앞
    fill_region(arr, 32, 20, 8, 12, shade(top_rgb, 0.65))  # 뒤
    fill_region(arr, 16, 20, 4, 12, shade(top_rgb, 0.8))   # 오른쪽
    fill_region(arr, 28, 20, 4, 12, shade(top_rgb, 0.8))   # 왼쪽
    fill_region(arr, 20, 16, 8, 4,  shade(top_rgb, 0.9))   # 위

    # ── 상의 재킷 오버레이 ──
    fill_region(arr, 20, 36, 8, 12, shade(top_rgb, 1.0))
    fill_region(arr, 32, 36, 8, 12, shade(top_rgb, 0.65))
    fill_region(arr, 16, 36, 4, 12, shade(top_rgb, 0.8))
    fill_region(arr, 28, 36, 4, 12, shade(top_rgb, 0.8))

    # ── 오른팔 ──
    fill_region(arr, 44, 20, 4, 12, shade(top_rgb, 1.0))   # 앞
    fill_region(arr, 40, 20, 4, 12, shade(top_rgb, 0.8))   # 오른쪽
    fill_region(arr, 48, 20, 4, 12, shade(top_rgb, 0.8))   # 왼쪽
    fill_region(arr, 52, 20, 4, 12, shade(top_rgb, 0.65))  # 뒤
    fill_region(arr, 44, 16, 4, 4,  shade(top_rgb, 0.9))   # 위

    # ── 왼팔 ──
    fill_region(arr, 36, 52, 4, 12, shade(top_rgb, 1.0))
    fill_region(arr, 32, 52, 4, 12, shade(top_rgb, 0.8))
    fill_region(arr, 40, 52, 4, 12, shade(top_rgb, 0.8))
    fill_region(arr, 44, 52, 4, 12, shade(top_rgb, 0.65))
    fill_region(arr, 36, 48, 4, 4,  shade(top_rgb, 0.9))

    # ── 하의 (바지) — 신발 영역 제외 ──
    shoe_rows = 3
    fill_region(arr, 4,  20, 4, 12, shade(bottom_rgb, 1.0), skip_rows_bottom=shoe_rows)
    fill_region(arr, 0,  20, 4, 12, shade(bottom_rgb, 0.8), skip_rows_bottom=shoe_rows)
    fill_region(arr, 8,  20, 4, 12, shade(bottom_rgb, 0.8), skip_rows_bottom=shoe_rows)
    fill_region(arr, 12, 20, 4, 12, shade(bottom_rgb, 0.65), skip_rows_bottom=shoe_rows)
    fill_region(arr, 4,  16, 4, 4,  shade(bottom_rgb, 0.9))

    fill_region(arr, 20, 52, 4, 12, shade(bottom_rgb, 1.0), skip_rows_bottom=shoe_rows)
    fill_region(arr, 16, 52, 4, 12, shade(bottom_rgb, 0.8), skip_rows_bottom=shoe_rows)
    fill_region(arr, 24, 52, 4, 12, shade(bottom_rgb, 0.8), skip_rows_bottom=shoe_rows)
    fill_region(arr, 28, 52, 4, 12, shade(bottom_rgb, 0.65), skip_rows_bottom=shoe_rows)
    fill_region(arr, 20, 48, 4, 4,  shade(bottom_rgb, 0.9))

    # ── 신발 (다리 하단 3줄) ──
    for leg_x, leg_w in [(0, 16), (16, 16)]:
        for py in range(29, 32):  # 오른 다리
            for px in range(leg_x, leg_x + leg_w):
                if arr[py, px, 3] > 10:
                    arr[py, px] = [*shade(shoes_rgb, 0.85 if px % 4 < 2 else 0.7), 255]
        for py in range(61, 64):  # 왼 다리
            for px in range(leg_x, leg_x + leg_w):
                if arr[py, px, 3] > 10:
                    arr[py, px] = [*shade(shoes_rgb, 0.85 if px % 4 < 2 else 0.7), 255]


def draw_glasses(arr: np.ndarray):
    """안경 픽셀 추가 (얼굴 front 영역 기준)"""
    # 얼굴 앞면: x=8~15, y=8~15
    # 눈 줄(y=10): 안경테 표시
    glass_color = [40, 40, 40, 255]
    for px in [8, 9, 12, 13, 14, 15]:
        arr[10, px] = glass_color
    arr[11, 8] = glass_color
    arr[11, 11] = glass_color
    arr[11, 15] = glass_color


VALID_TONES = {"warm_bright", "warm_normal", "warm_dark", "cool_bright", "cool_normal", "cool_dark"}


def generate_skin(features: dict) -> Image.Image:
    """특징 딕셔너리 → 64×64 마인크래프트 스킨 PNG"""
    tone_key = features.get("skin_tone", "warm_bright")
    if tone_key not in VALID_TONES:
        tone_key = "warm_bright"
    base_img = load_base(tone_key)
    skin_img = apply_skin_tone(base_img, tone_key)

    arr = np.array(skin_img, dtype=np.uint8).copy()

    hair_rgb   = parse_color(features.get("hair_color", "검정"))
    top_rgb    = parse_color(features.get("top_color", "흰색"))
    bottom_rgb = parse_color(features.get("bottom_color", "네이비"))
    shoes_rgb  = parse_color(features.get("shoes_color", "검정"))
    hair_style = features.get("hair_style", "")

    draw_hair(arr, hair_rgb, hair_style)
    draw_clothing(arr, top_rgb, bottom_rgb, shoes_rgb)

    if features.get("glasses", False):
        draw_glasses(arr)

    return Image.fromarray(arr, "RGBA")
