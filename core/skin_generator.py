"""
skin_generator.py
특징 JSON → Pillow 픽셀 조작 → 64×64 마인크래프트 스킨 PNG
"""

import numpy as np
from PIL import Image
from pathlib import Path
from colorsys import rgb_to_hsv, hsv_to_rgb
from .recolor_skin import load_base, apply_skin_tone

BASESKIN_DIR = Path(__file__).parent.parent / "baseskin"

# ── 마스크 색상 → 존 매핑 ──────────────────────────────────────────
# 각 픽셀 색상을 "top" / "bottom" / "shoes" / "jacket" / "skip" 로 분류

def detect_zone(r: int, g: int, b: int) -> str:
    if r < 30 and g > 200 and b < 40:    return "top"      # 초록
    if r < 30 and g < 30  and b > 200:   return "bottom"   # 파랑
    if r > 200 and g > 200 and b < 40:   return "shoes"    # 노랑
    if r > 200 and g < 30  and b > 200:  return "acc"      # 마젠타
    if r < 30 and g > 200 and b > 200:   return "jacket"   # 시안
    return "skip"  # 피부 노출 마커 or 기타 → 베이스 스킨 그대로


# ── UV 면별 명암 테이블 ────────────────────────────────────────────
# (x, y, w, h, shade_factor)
_SHADE_REGIONS = [
    # 몸통
    (20, 16,  8,  4, 0.90),  # body top
    (16, 20,  4, 12, 0.80),  # body right
    (20, 20,  8, 12, 1.00),  # body front
    (28, 20,  4, 12, 0.80),  # body left
    (32, 20,  8, 12, 0.65),  # body back
    # 재킷 오버레이
    (16, 36,  4, 12, 0.80),
    (20, 36,  8, 12, 1.00),
    (28, 36,  4, 12, 0.80),
    (32, 36,  8, 12, 0.65),
    # 오른팔
    (44, 16,  4,  4, 0.90),
    (40, 20,  4, 12, 0.80),
    (44, 20,  4, 12, 1.00),
    (48, 20,  4, 12, 0.80),
    (52, 20,  4, 12, 0.65),
    # 왼팔 (2레이어)
    (36, 48,  4,  4, 0.90),
    (32, 52,  4, 12, 0.80),
    (36, 52,  4, 12, 1.00),
    (40, 52,  4, 12, 0.80),
    (44, 52,  4, 12, 0.65),
    # 오른 다리
    ( 4, 16,  4,  4, 0.90),
    ( 0, 20,  4, 12, 0.80),
    ( 4, 20,  4, 12, 1.00),
    ( 8, 20,  4, 12, 0.80),
    (12, 20,  4, 12, 0.65),
    # 왼 다리 (2레이어)
    (20, 48,  4,  4, 0.90),
    (16, 52,  4, 12, 0.80),
    (20, 52,  4, 12, 1.00),
    (24, 52,  4, 12, 0.80),
    (28, 52,  4, 12, 0.65),
]

def _build_shade_map() -> np.ndarray:
    shade_map = np.ones((64, 64), dtype=np.float32)
    for (x, y, w, h, f) in _SHADE_REGIONS:
        shade_map[y:y+h, x:x+w] = f
    return shade_map

_SHADE_MAP = _build_shade_map()


# ── 마스크 파일 선택 ───────────────────────────────────────────────
MASK_STYLE_MAP = [
    # (top 키워드, bottom 키워드, 파일명)  — 위에 있을수록 우선
    (["자켓", "jacket", "코트", "블레이저"],          [],                          "mask_jacket.png"),
    (["크롭", "crop"],  ["반바지", "shorts", "미니"],  "mask_crop_shorts.png"),
    (["크롭", "crop"],  [],                            "mask_crop_long.png"),
    (["크롭", "crop"],  ["반바지", "shorts", "미니"],  "mask_crop_shorts_shorderless.png"),  # 오프숄더 크롭+반바지
    (["오프숄더", "off-shoulder", "어깨"],             ["반바지", "shorts", "미니"],  "mask_crop_shorts_shorderless.png"),
    (["오프숄더", "off-shoulder", "어깨"],             [],                            "mask_crop_long_shorderless.png"),
    (["민소매", "나시", "sleeveless", "탱크"],         [],                            "mask_sleeveless.png"),
    ([],  ["롱스커트", "맥시", "긴 스커트", "원피스", "드레스"], "mask_longskirt.png"),
    ([],  ["스커트", "치마", "미니스커트"],                      "mask_shortsskirt.png"),
    ([],  ["반바지", "shorts", "미니"],                          "mask_shorts.png"),
    (["반팔", "short sleeve", "shortsleeve"],          [],        "mask_shortsleeve.png"),
]
MASK_FALLBACK = "mask_longsleeve.png"


def pick_mask(features: dict) -> Path:
    top   = (features.get("top_style",    "") or "").lower()
    bot   = (features.get("bottom_style", "") or "").lower()
    for top_kws, bot_kws, filename in MASK_STYLE_MAP:
        top_ok = (not top_kws) or any(k in top for k in top_kws)
        bot_ok = (not bot_kws) or any(k in bot for k in bot_kws)
        if top_ok and bot_ok:
            p = BASESKIN_DIR / filename
            if p.exists():
                return p
    return BASESKIN_DIR / MASK_FALLBACK


_REF_SKIN_CACHE: dict = {}

def _load_ref_skin() -> np.ndarray:
    """의상 텍스처 레퍼런스 스킨 로드 (캐시)"""
    key = "clothing_ref"
    if key not in _REF_SKIN_CACHE:
        path = BASESKIN_DIR / "기본수소.png"
        if not path.exists():
            # fallback: base_warm_bright
            path = BASESKIN_DIR / "base_warm_bright.png"
        _REF_SKIN_CACHE[key] = np.array(Image.open(path).convert("RGBA"), dtype=np.uint8)
    return _REF_SKIN_CACHE[key]


def _zone_max_v(ref_arr: np.ndarray, mask_arr: np.ndarray) -> dict:
    """존별 최대 밝기 계산 (정규화용)"""
    maxv: dict = {}
    for y in range(64):
        for x in range(64):
            mr, mg, mb, ma = mask_arr[y, x]
            if ma < 10:
                continue
            zone = detect_zone(int(mr), int(mg), int(mb))
            if zone == "skip":
                continue
            rr, rg, rb, ra = ref_arr[y, x]
            if ra < 10:
                continue
            _, _, v = rgb_to_hsv(rr/255, rg/255, rb/255)
            if v > maxv.get(zone, 0.0):
                maxv[zone] = v
    return maxv


def _paint_mask(arr, mask_arr, ref_arr, zone_colors, zone_maxv):
    """마스크 기반으로 레퍼런스 텍스처 재채색 후 arr에 합성"""
    for y in range(64):
        for x in range(64):
            mr, mg, mb, ma = mask_arr[y, x]
            if ma < 10:
                continue
            zone = detect_zone(int(mr), int(mg), int(mb))
            if zone == "skip":
                continue
            base_rgb = zone_colors.get(zone, DEFAULT_COLOR)

            # 레퍼런스 스킨의 해당 픽셀 밝기를 텍스처로 사용
            rr, rg, rb, ra = ref_arr[y, x]
            if ra > 10:
                _, _, v = rgb_to_hsv(rr/255, rg/255, rb/255)
                mv = zone_maxv.get(zone, 1.0)
                brightness = v / max(mv, 0.01)
            else:
                # 레퍼런스에 픽셀 없으면 shade_map 폴백
                brightness = float(_SHADE_MAP[y, x])

            arr[y, x] = [
                max(0, min(255, int(base_rgb[0] * brightness))),
                max(0, min(255, int(base_rgb[1] * brightness))),
                max(0, min(255, int(base_rgb[2] * brightness))),
                255,
            ]


def apply_mask_clothing(arr: np.ndarray, features: dict):
    """마스크 + 레퍼런스 스킨 텍스처 기반으로 의상 색상 적용"""
    top_rgb    = parse_color(features.get("top_color",    "흰색"))
    bottom_rgb = parse_color(features.get("bottom_color", "네이비"))
    shoes_rgb  = parse_color(features.get("shoes_color",  "검정"))

    zone_colors = {
        "top":    top_rgb,
        "bottom": bottom_rgb,
        "shoes":  shoes_rgb,
        "jacket": top_rgb,
        "acc":    parse_color(features.get("accessories", "") or "검정"),
    }

    mask_path = pick_mask(features)
    mask_arr  = np.array(Image.open(mask_path).convert("RGBA"), dtype=np.uint8)
    ref_arr   = _load_ref_skin()
    zone_maxv = _zone_max_v(ref_arr, mask_arr)

    # 자켓 스타일: longsleeve를 먼저 깔고 jacket 오버레이 덮기
    if "jacket" in mask_path.name:
        base_mask_path = BASESKIN_DIR / "mask_longsleeve.png"
        if base_mask_path.exists():
            base_mask = np.array(Image.open(base_mask_path).convert("RGBA"), dtype=np.uint8)
            base_maxv = _zone_max_v(ref_arr, base_mask)
            # jacket이 칠하지 않는 영역만 longsleeve로 채움
            tmp_mask = base_mask.copy()
            for y in range(64):
                for x in range(64):
                    if mask_arr[y, x, 3] > 10:
                        tmp_mask[y, x, 3] = 0  # 재킷이 덮을 부분은 제외
            _paint_mask(arr, tmp_mask, ref_arr, zone_colors, base_maxv)

    _paint_mask(arr, mask_arr, ref_arr, zone_colors, zone_maxv)


# ── 머리카락 ──────────────────────────────────────────────────────
# (키워드 목록, 파일명 or [파일명 리스트])  — 위에 있을수록 우선
# 리스트인 경우 순서대로 겹쳐 합성 (뒤 레이어 → 앞 레이어)
HAIR_STYLE_MAP = [
    # 양갈래
    (["짧은양갈래_웨이브"],  ["base_hair_twin_wave_short_back.png",     "base_hair_twin_wave_front.png"]),
    (["짧은양갈래_생머리"],  ["base_hair_twin_straight_short_back.png", "base_hair_twin_straight_short_front.png"]),
    (["양갈래_웨이브"],      ["base_hair_twin_wave_back.png",           "base_hair_twin_wave_front.png"]),
    (["양갈래_생머리", "양갈래"],  ["base_hair_twin_straight_back.png", "base_hair_twin_straight_front.png"]),
    # 묶음
    (["짧은꽁지"],   "base_hair_short_ponytail.png"),
    (["꽁지머리"],   "base_hair_ponytail.png"),
    (["사이드테일"], "base_hair_sidetail.png"),
    # 장발
    (["장발_웨이브"],   "base_hair_long_wave.png"),
    (["장발_생머리"],   "base_hair_long_straight.png"),
    # 중장발
    (["중장발_웨이브"], "base_hair_mid_wave.png"),
    (["중장발_생머리"], "base_hair_mid_straight.png"),
    # 단발 (앞머리 스타일)
    (["단발_사이드뱅"], "base_hair_bangs_side.png"),
    (["단발_노뱅"],     "base_hair_bangs_none.png"),
    (["단발_가르마"],   "base_hair_bangs_curtain.png"),
    (["단발_일자뱅"],   "base_hair_bangs_full.png"),
]
HAIR_BASE_FALLBACK = "base_hair_bangs_full.png"


def pick_hair_files(hair_style: str) -> list:
    """헤어 스타일 → 파일 경로 리스트 반환 (순서대로 합성)"""
    s = (hair_style or "").strip()
    for keywords, files in HAIR_STYLE_MAP:
        if any(k in s for k in keywords):
            if isinstance(files, str):
                files = [files]
            paths = [BASESKIN_DIR / f for f in files if (BASESKIN_DIR / f).exists()]
            if paths:
                return paths
    return [BASESKIN_DIR / HAIR_BASE_FALLBACK]


def load_hair_base(hair_style: str = "") -> list:
    """파일 경로 리스트 → numpy 배열 리스트"""
    return [
        np.array(Image.open(p).convert("RGBA"), dtype=np.uint8)
        for p in pick_hair_files(hair_style)
    ]


def recolor_hair_base(hair_arr: np.ndarray, target_rgb: tuple) -> np.ndarray:
    """베이스 헤어 밝기를 기준으로 target_rgb를 곱셈 방식으로 적용.
    어두운 색(검정 등)도 자연스럽게 재현됨."""
    # 가장 밝은 픽셀의 V값을 기준으로 정규화
    max_v = 0.0
    for y in range(64):
        for x in range(64):
            r, g, b, a = hair_arr[y, x]
            if a < 10:
                continue
            _, _, v = rgb_to_hsv(r/255, g/255, b/255)
            if v > max_v:
                max_v = v
    if max_v < 0.01:
        max_v = 1.0

    result = hair_arr.copy()
    for y in range(64):
        for x in range(64):
            r, g, b, a = hair_arr[y, x]
            if a < 10:
                continue
            _, _, v = rgb_to_hsv(r/255, g/255, b/255)
            brightness = v / max_v  # 0.0 ~ 1.0
            result[y, x] = [
                max(0, min(255, int(target_rgb[0] * brightness))),
                max(0, min(255, int(target_rgb[1] * brightness))),
                max(0, min(255, int(target_rgb[2] * brightness))),
                int(a),
            ]
    return result


def _composite_layer(arr: np.ndarray, colored: np.ndarray):
    """colored 레이어를 arr 위에 알파 블렌딩으로 합성"""
    for y in range(64):
        for x in range(64):
            a = int(colored[y, x, 3])
            if a < 10:
                continue
            if a >= 255:
                arr[y, x] = colored[y, x]
            else:
                src = colored[y, x, :3].astype(float)
                dst = arr[y, x, :3].astype(float)
                fa = a / 255
                arr[y, x, :3] = (src * fa + dst * (1 - fa)).astype(np.uint8)
                arr[y, x, 3] = 255


def draw_hair(arr: np.ndarray, hair_rgb: tuple, hair_style: str):
    """헤어 베이스 파일들을 순서대로 재채색 후 합성"""
    for base_arr in load_hair_base(hair_style):
        colored = recolor_hair_base(base_arr, hair_rgb)
        _composite_layer(arr, colored)


def draw_long_hair_body(arr: np.ndarray, hair_rgb: tuple, hair_style: str):
    """긴 머리 — 의상 위에 몸통 뒷면까지 머리카락 덮기 (의상 적용 후 호출)"""
    style_lower = (hair_style or "").lower()
    is_long  = any(k in style_lower for k in ["긴", "롱", "long"])
    is_wavy  = any(k in style_lower for k in ["웨이브", "컬", "wave", "curl"])
    if not (is_long or is_wavy):
        return

    # 머리카락이 몸통 뒷면으로 내려오는 길이
    rows = 8 if is_wavy else 6   # 웨이브/컬이면 더 길게

    # 몸통 뒷면 base layer (32,20,8,12)
    for row_i in range(rows):
        fade = 1.0 - (row_i / rows) ** 0.7   # 위쪽이 더 진하게
        h_rgb = _shade_tuple(hair_rgb, 0.58 * fade)
        for px in range(32, 40):
            py = 20 + row_i
            if arr[py, px, 3] > 10:
                arr[py, px] = [*h_rgb, 255]

    # 재킷 오버레이 뒷면 (32,36,8,12)
    for row_i in range(min(rows, 8)):
        fade = 1.0 - (row_i / rows) ** 0.7
        h_rgb = _shade_tuple(hair_rgb, 0.55 * fade)
        for px in range(32, 40):
            py = 36 + row_i
            if arr[py, px, 3] > 10:
                arr[py, px] = [*h_rgb, 255]


# ── 안경 ─────────────────────────────────────────────────────────
def draw_glasses(arr: np.ndarray):
    gc = [40, 40, 40, 255]
    for px in [8, 9, 12, 13, 14, 15]:
        arr[10, px] = gc
    arr[11, 8] = gc; arr[11, 11] = gc; arr[11, 15] = gc


# ── 유틸 ─────────────────────────────────────────────────────────
COLOR_MAP = {
    "검정": (28, 28, 28),   "블랙": (28, 28, 28),
    "흰색": (238, 238, 238),"흰": (238, 238, 238),   "화이트": (238, 238, 238),
    "회색": (130, 130, 130),"그레이": (130, 130, 130),"밝은 회색": (180, 180, 180),
    "빨강": (190, 45, 45),  "레드": (190, 45, 45),
    "파랑": (50, 90, 190),  "블루": (50, 90, 190),
    "네이비": (25, 35, 95), "남색": (25, 35, 95),
    "하늘": (90, 155, 215), "하늘색": (90, 155, 215),
    "초록": (50, 130, 60),  "그린": (50, 130, 60),
    "카키": (90, 100, 60),
    "갈색": (110, 65, 35),  "브라운": (110, 65, 35),
    "금발": (205, 165, 75), "금색": (205, 165, 75),
    "노랑": (215, 195, 55), "옐로우": (215, 195, 55),
    "주황": (210, 110, 40), "오렌지": (210, 110, 40),
    "분홍": (215, 120, 145),"핑크": (215, 120, 145),
    "보라": (115, 55, 155), "퍼플": (115, 55, 155),
    "베이지": (210, 185, 155),
    "아이보리": (230, 220, 195),
    "민트": (100, 200, 170),
    "연두": (140, 195, 90),
    "자주": (140, 35, 70),  "버건디": (115, 25, 45),
    "카멜": (185, 135, 75),
    "청바지": (70, 100, 150),"데님": (70, 100, 150),
    "교복": (30, 40, 100),
}
DEFAULT_COLOR = (100, 100, 100)

def parse_color(text: str) -> tuple:
    if not text:
        return DEFAULT_COLOR
    text = str(text).strip()
    for key, rgb in COLOR_MAP.items():
        if key in text:
            return rgb
    return DEFAULT_COLOR

def _shade_tuple(rgb: tuple, f: float) -> tuple:
    return tuple(max(0, min(255, int(c * f))) for c in rgb)


# ── 메인 ─────────────────────────────────────────────────────────
VALID_TONES = {"warm_bright", "warm_normal", "warm_dark",
               "cool_bright", "cool_normal", "cool_dark"}


def generate_skin(features: dict) -> Image.Image:
    tone_key = features.get("skin_tone", "warm_bright")
    if tone_key not in VALID_TONES:
        tone_key = "warm_bright"

    arr = np.array(apply_skin_tone(load_base(tone_key), tone_key), dtype=np.uint8).copy()

    hair_rgb   = parse_color(features.get("hair_color", "검정"))
    hair_style = features.get("hair_style", "")

    draw_hair(arr, hair_rgb, hair_style)
    apply_mask_clothing(arr, features)
    draw_long_hair_body(arr, hair_rgb, hair_style)  # 의상 위에 긴 머리 덮기

    if features.get("glasses", False):
        draw_glasses(arr)

    return Image.fromarray(arr, "RGBA")
