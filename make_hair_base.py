"""
make_hair_base.py
기준 색상으로 머리카락 베이스 PNG 생성 (64x64 RGBA)
실행 후 baseskin/base_hair.png 가 생성된다.
"""

from PIL import Image
import numpy as np
from pathlib import Path

# ── 기준색: 밝은 따뜻한 중성 갈색 ─────────────────────────────────
# HSV 기반 톤 변경이 잘 되도록 채도를 약간 넣은 neutral warm
BASE_H, BASE_S, BASE_V = 28, 0.40, 0.82   # (hue도, sat, val)

from colorsys import hsv_to_rgb

def mk(brightness: float, sat_scale: float = 1.0) -> list:
    h = BASE_H / 360
    s = min(1.0, BASE_S * sat_scale)
    v = max(0.0, min(1.0, BASE_V * brightness))
    r, g, b = hsv_to_rgb(h, s, v)
    return [int(r*255), int(g*255), int(b*255), 255]

def mk_a(brightness: float, alpha: int) -> list:
    px = mk(brightness)
    return px[:3] + [alpha]

# ── 패턴 함수들 ────────────────────────────────────────────────────

def strand_pattern(w, h, base_bright=1.0, back=False):
    """수직 가닥 텍스처 8×8 패턴"""
    pattern = []
    for y in range(h):
        row = []
        for x in range(w):
            # 3픽셀 주기로 밝기 변화 → 머리카락 가닥 표현
            cycle = x % 3
            if cycle == 0:
                b = 0.72 if back else 0.78   # 그림자 가닥
            elif cycle == 1:
                b = 0.96 if back else 1.02   # 밝은 가닥
            else:
                b = 0.85 if back else 0.91   # 중간 가닥

            # 아래로 갈수록 약간 어두워짐 (머리카락 끝)
            b *= 0.95 + 0.05 * (1 - y / (h - 1))
            row.append(mk(b * base_bright))
        pattern.append(row)
    return pattern


def top_pattern():
    """머리 위쪽 — 빛이 정수리에서 퍼지는 모양"""
    p = []
    for y in range(8):
        row = []
        for x in range(8):
            # 중앙(3~4)이 가장 밝음, 가장자리는 어두움
            dist = abs(x - 3.5) / 3.5          # 0.0(중앙) ~ 1.0(가장자리)
            b = 1.02 - dist * 0.18
            # 앞쪽(y 작을수록) 약간 밝게
            b *= 0.96 + 0.04 * (1 - y / 7)
            # 가닥 효과
            if x % 3 == 0:
                b *= 0.84
            elif x % 3 == 1:
                b *= 1.0
            row.append(mk(b))
        p.append(row)
    return p


def bangs_pattern():
    """앞머리 (모자 오버레이 front) — 자연스러운 앞머리 모양"""
    # 8×8 중 위 3줄만 사용, 나머지 투명
    visible = [
        [1,1,1,1,1,1,1,1],   # y=8  가장 굵은 줄
        [0,1,1,1,1,1,1,0],   # y=9  약간 안쪽
        [0,0,1,1,1,1,0,0],   # y=10 더 좁게
        [0,0,0,1,1,0,0,0],   # y=11 얇게
    ]
    p = []
    for row_idx, mask in enumerate(visible):
        row = []
        for col_idx, vis in enumerate(mask):
            if not vis:
                row.append([0, 0, 0, 0])
            else:
                b = 1.02 if col_idx % 3 == 1 else (0.90 if col_idx % 3 == 0 else 0.95)
                row.append(mk(b))
        p.append(row)
    # 나머지 4줄 투명
    for _ in range(4):
        p.append([[0,0,0,0]] * 8)
    return p


def overlay_strand(w, h, base_bright=1.0):
    """오버레이 레이어용 — 약간 반투명"""
    p = []
    for y in range(h):
        row = []
        for x in range(w):
            cycle = x % 3
            b = 0.75 if cycle == 0 else (0.97 if cycle == 1 else 0.86)
            b *= 0.95 + 0.05 * (1 - y / (h-1))
            px = mk(b * base_bright)
            px[3] = 220   # 약간 반투명
            row.append(px)
        p.append(row)
    return p


# ── 이미지 조립 ────────────────────────────────────────────────────

def fill(arr, x, y, pattern):
    for ry, row in enumerate(pattern):
        for rx, px in enumerate(row):
            arr[y + ry, x + rx] = px


arr = np.zeros((64, 64, 4), dtype=np.uint8)

# ─ 머리 레이어 1 ──────────────────────────────────────────────────
fill(arr, 8,  0,  top_pattern())                         # 머리 윗면
fill(arr, 0,  8,  strand_pattern(8, 8, 1.0))             # 오른쪽 측면
fill(arr, 16, 8,  strand_pattern(8, 8, 1.0))             # 왼쪽 측면
fill(arr, 24, 8,  strand_pattern(8, 8, 0.88, back=True)) # 뒷면

# ─ 모자 오버레이 레이어 2 ─────────────────────────────────────────
fill(arr, 40, 0,  top_pattern())                         # 오버레이 윗면
fill(arr, 32, 8,  overlay_strand(8, 8, 1.0))             # 오버레이 오른쪽
fill(arr, 40, 8,  bangs_pattern())                       # 앞머리 (bangs)
fill(arr, 48, 8,  overlay_strand(8, 8, 1.0))             # 오버레이 왼쪽
fill(arr, 56, 8,  overlay_strand(8, 8, 0.88))            # 오버레이 뒷면

out_path = Path(__file__).parent / "baseskin" / "base_hair.png"
Image.fromarray(arr, "RGBA").save(out_path)
print(f"saved: {out_path}")

preview = Image.fromarray(arr, "RGBA").resize((256, 256), Image.NEAREST)
preview_path = Path(__file__).parent / "baseskin" / "base_hair_preview.png"
preview.save(preview_path)
print(f"preview: {preview_path}")
