"""
recolor_skin.py
베이스 스킨의 피부 영역을 HSV 변환으로 자연스럽게 recolor한다.
형태(명암 구조)는 유지하고 색조·채도·밝기만 조정.
"""

import numpy as np
from PIL import Image
from colorsys import rgb_to_hsv, hsv_to_rgb
from pathlib import Path

# UV 좌표 기반 피부 영역 (x, y, w, h)
SKIN_REGIONS = [
    (8,  0,  8,  8),  # head top
    (0,  8,  8,  8),  # head right
    (8,  8,  8,  8),  # head front (face)
    (16, 8,  8,  8),  # head left
    (24, 8,  8,  8),  # head back
    (16, 20, 4, 12),  # body right
    (20, 20, 8, 12),  # body front
    (28, 20, 4, 12),  # body left
    (32, 20, 8, 12),  # body back
    (44, 20, 4, 12),  # right arm front
    (40, 20, 4, 12),  # right arm right
    (48, 20, 4, 12),  # right arm left
    (36, 52, 4, 12),  # left arm front
    (32, 52, 4, 12),  # left arm right
    (40, 52, 4, 12),  # left arm left
    (4,  20, 4, 12),  # right leg front
    (0,  20, 4, 12),  # right leg right
    (8,  20, 4, 12),  # right leg left
    (20, 52, 4, 12),  # left leg front
    (16, 52, 4, 12),  # left leg right
    (24, 52, 4, 12),  # left leg left
    (20, 16, 8,  4),  # body top
    (4,  16, 4,  4),  # right leg top
    (20, 48, 4,  4),  # left leg top
    (44, 16, 4,  4),  # right arm top
    (36, 48, 4,  4),  # left arm top
]

# (h_shift, s_scale, v_scale, v_shift)
SKIN_TONE_PRESETS = {
    "warm_bright":           ( 0.002, 1.00, 1.00,  0.00),
    "warm_normal":           ( 0.002, 1.05, 0.88, -0.02),
    "warm_dark":             ( 0.005, 1.10, 0.72, -0.05),
    "cool_bright":           (-0.003, 0.95, 1.00,  0.00),
    "cool_normal":           (-0.003, 1.00, 0.88, -0.02),
    "cool_dark":             (-0.005, 1.05, 0.72, -0.05),
    # 추가 어두운 톤 (파일 그대로 사용, 미세 조정만)
    "warm_dark_dark":        ( 0.005, 1.10, 1.00,  0.00),
    "cool_dark_dark":        (-0.005, 1.05, 1.00,  0.00),
    "cool_dark_dark_dark":   (-0.005, 1.05, 1.00,  0.00),
    "cool_dark_dark_dark_dark": (-0.005, 1.00, 1.00, 0.00),
    # Gemini 라벨 → 내부 키 별칭
    "pale":        (-0.003, 0.90, 1.05,  0.02),   # cool_bright 파일 사용
    "warm_deeper": ( 0.005, 1.10, 1.00,  0.00),   # warm_dark_dark 파일 사용
    "cool_deeper": (-0.005, 1.05, 1.00,  0.00),   # cool_dark_dark 파일 사용
    "dark":        (-0.005, 1.05, 1.00,  0.00),   # cool_dark_dark_dark 파일 사용
    "very_dark":   (-0.005, 1.00, 1.00,  0.00),   # cool_dark_dark_dark_dark 파일 사용
}

# Gemini 라벨 → 실제 파일명 키
TONE_FILE_ALIAS = {
    "pale":        "cool_bright",
    "warm_deeper": "warm_dark_dark",
    "cool_deeper": "cool_dark_dark",
    "dark":        "cool_dark_dark_dark",
    "very_dark":   "cool_dark_dark_dark_dark",
}

BASE_DIR = Path(__file__).parent.parent / "baseskin"


def load_base(tone_key: str) -> Image.Image:
    """피부톤 키에 맞는 베이스 스킨 PNG 로드 (alias 자동 해석)"""
    file_key = TONE_FILE_ALIAS.get(tone_key, tone_key)
    path = BASE_DIR / f"base_{file_key}.png"
    if not path.exists():
        path = BASE_DIR / "base_warm_bright.png"
    return Image.open(path).convert("RGBA")


def build_skin_mask(img: Image.Image) -> np.ndarray:
    """UV 영역 내 피부 픽셀만 True로 마스킹 (눈·눈썹·홍조 제외)"""
    arr = np.array(img.convert("RGBA"), dtype=np.uint8)
    mask = np.zeros((64, 64), dtype=bool)
    for (rx, ry, rw, rh) in SKIN_REGIONS:
        for y in range(ry, ry + rh):
            for x in range(rx, rx + rw):
                r, g, b, a = arr[y, x]
                if a < 10:
                    continue
                if r > 220 and g > 210 and b > 205:  # 흰색 계열 제외
                    continue
                if r < 60 and g < 60 and b < 60:     # 검정 계열 제외
                    continue
                h, s, v = rgb_to_hsv(r / 255, g / 255, b / 255)
                if h > 0.88 and s > 0.3:             # 홍조 제외
                    continue
                if v < 0.25:                          # 매우 어두운 픽셀 제외
                    continue
                mask[y, x] = True
    return mask


def recolor_skin(
    base_img: Image.Image,
    h_shift: float = 0.0,
    s_scale: float = 1.0,
    v_scale: float = 1.0,
    v_shift: float = 0.0,
    mask: np.ndarray = None,
) -> Image.Image:
    """피부 마스크 영역에 HSV 변환 적용"""
    result = base_img.convert("RGBA").copy()
    arr = np.array(result, dtype=np.uint8)
    if mask is None:
        mask = build_skin_mask(base_img)
    for y in range(64):
        for x in range(64):
            if not mask[y, x]:
                continue
            r, g, b, a = arr[y, x]
            h, s, v = rgb_to_hsv(r / 255, g / 255, b / 255)
            h = (h + h_shift) % 1.0
            s = max(0.0, min(1.0, s * s_scale))
            v = max(0.0, min(1.0, v * v_scale + v_shift))
            nr, ng, nb = hsv_to_rgb(h, s, v)
            arr[y, x] = [int(nr * 255), int(ng * 255), int(nb * 255), a]
    return Image.fromarray(arr, "RGBA")


def apply_skin_tone(base_img: Image.Image, tone_key: str) -> Image.Image:
    """사전 정의된 프리셋으로 피부톤 변환."""
    preset = SKIN_TONE_PRESETS.get(tone_key, SKIN_TONE_PRESETS["warm_bright"])
    h_shift, s_scale, v_scale, v_shift = preset
    mask = build_skin_mask(base_img)
    return recolor_skin(base_img, h_shift, s_scale, v_scale, v_shift, mask)
