"""
skin_generator.py
특징 JSON → Pillow 픽셀 조작 → 64×64 마인크래프트 스킨 PNG
"""

import numpy as np
from PIL import Image
from pathlib import Path
from colorsys import rgb_to_hsv, hsv_to_rgb

# ── numpy 벡터화 HSV 변환 ──────────────────────────────────────────
def _np_rgb2v(rgb_u8: np.ndarray) -> np.ndarray:
    """(H,W,3) uint8 → (H,W) V float32"""
    f = rgb_u8.astype(np.float32) / 255.0
    return f.max(axis=-1)

def _np_hsv_recolor(rgb_u8: np.ndarray, alpha: np.ndarray,
                    t_h: float, t_s: float,
                    ref_v: np.ndarray, max_v: float,
                    t_v: float) -> np.ndarray:
    """ref_v 밝기를 유지하며 HSV 색조를 (t_h, t_s)로 교체. (H,W,3) uint8 반환"""
    norm_v = np.clip(ref_v / max(max_v, 0.01), 0.0, 1.0)
    final_v = np.clip(norm_v * max(t_v, 0.15), 0.0, 1.0)

    v = final_v
    s = t_s
    hi = (t_h * 6.0).astype(np.float32) if isinstance(t_h, np.ndarray) else float(t_h) * 6.0
    hi_i = int(hi) % 6
    f = hi - int(hi)
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    lut = [(v, t, p, p, q, v), (t, v, v, q, p, p), (p, p, t, v, v, q)]
    r = lut[0][hi_i]; g = lut[1][hi_i]; b = lut[2][hi_i]
    out = np.stack([r, g, b], axis=-1)
    return np.clip(out * 255, 0, 255).astype(np.uint8)
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

# ── 스타일 키워드 → 레퍼런스 스킨 매핑 ──────────────────────────────
# 우선순위 높은 것부터
_STYLE_REF_MAP = [
    # (상의 키워드, 하의 키워드, 레퍼런스 파일)
    (["교복", "school uniform", "세일러"],  [],                     "reference (10).png"),
    (["정장", "suit", "비즈니스", "포멀"],  ["슬랙스", "정장"],      "reference (22).png"),
    (["자켓", "블레이저", "jacket"],        [],                     "reference (22).png"),
    (["한복"],                              [],                     "reference (62).png"),
    (["경찰", "police", "군복"],            [],                     "reference (5).png"),
    (["원피스", "드레스", "dress", "가운", "볼"],   [],                     "reference (62).png"),
    ([],                                         ["한복", "치마", "스커트", "롱스커트"], "reference (62).png"),
]
_REF_FALLBACK = "reference (62).png"


def _select_ref_skin(features: dict) -> np.ndarray:
    """의상 특징에 맞는 레퍼런스 스킨 선택 (캐시)"""
    top  = (features.get("top_style",    "") or "").lower()
    bot  = (features.get("bottom_style", "") or "").lower()

    chosen = _REF_FALLBACK
    for top_kws, bot_kws, fname in _STYLE_REF_MAP:
        top_ok = (not top_kws) or any(k in top for k in top_kws)
        bot_ok = (not bot_kws) or any(k in bot for k in bot_kws)
        if top_ok and bot_ok:
            p = BASESKIN_DIR / fname
            if p.exists():
                chosen = fname
                break

    if chosen not in _REF_SKIN_CACHE:
        path = BASESKIN_DIR / chosen
        if not path.exists():
            path = BASESKIN_DIR / _REF_FALLBACK
        _REF_SKIN_CACHE[chosen] = np.array(Image.open(path).convert("RGBA"), dtype=np.uint8)
    return _REF_SKIN_CACHE[chosen]


def _build_zone_masks(mask_arr: np.ndarray) -> dict:
    """마스크 배열 → 존별 bool 마스크 (numpy 벡터화)"""
    valid = mask_arr[:, :, 3] > 10
    r = mask_arr[:, :, 0].astype(np.int16)
    g = mask_arr[:, :, 1].astype(np.int16)
    b = mask_arr[:, :, 2].astype(np.int16)
    return {
        "top":    valid & (r < 30) & (g > 200) & (b < 40),
        "bottom": valid & (r < 30) & (g < 30)  & (b > 200),
        "shoes":  valid & (r > 200) & (g > 200) & (b < 40),
        "acc":    valid & (r > 200) & (g < 30)  & (b > 200),
        "jacket": valid & (r < 30) & (g > 200)  & (b > 200),
    }


def _zone_stats(ref_arr: np.ndarray, mask_arr: np.ndarray) -> dict:
    """존별 최대 V 계산 (numpy 벡터화)"""
    ref_v = _np_rgb2v(ref_arr[:, :, :3])
    ref_valid = ref_arr[:, :, 3] > 10
    maxv: dict = {}
    for zone, zmask in _build_zone_masks(mask_arr).items():
        combined = zmask & ref_valid
        if combined.any():
            maxv[zone] = float(ref_v[combined].max())
    return maxv


def _paint_mask(arr, mask_arr, ref_arr, zone_colors, zone_maxv):
    """numpy 벡터화 HSV 색조 변환으로 레퍼런스 텍스처 재채색"""
    ref_v_map = _np_rgb2v(ref_arr[:, :, :3])          # (64,64) float32
    ref_valid  = ref_arr[:, :, 3] > 10
    zone_masks = _build_zone_masks(mask_arr)

    for zone, zmask in zone_masks.items():
        if not zmask.any():
            continue
        target_rgb = zone_colors.get(zone, DEFAULT_COLOR)
        tr, tg, tb = target_rgb
        t_h, t_s, t_v = rgb_to_hsv(tr/255, tg/255, tb/255)
        mv = zone_maxv.get(zone, 1.0)

        has_ref = zmask & ref_valid
        no_ref  = zmask & ~ref_valid

        if has_ref.any():
            rv = ref_v_map[has_ref]
            norm_v  = np.clip(rv / max(mv, 0.01), 0.0, 1.0)
            final_v = np.clip(norm_v * max(t_v, 0.15), 0.0, 1.0)
            rgb_out = _np_hsv_recolor(arr[:, :, :3], arr[:, :, 3],
                                      t_h, t_s, ref_v_map, mv, t_v)
            ys, xs = np.where(has_ref)
            arr[ys, xs, :3] = rgb_out[ys, xs]
            arr[ys, xs, 3]  = 255

        if no_ref.any():
            final_v = np.clip(t_v * (0.8 + 0.2 * _SHADE_MAP[no_ref]), 0.0, 1.0)
            v = final_v; s = t_s; hi_f = t_h * 6.0; hi_i = int(hi_f) % 6
            frac = hi_f - int(hi_f)
            p = v*(1-s); q = v*(1-frac*s); tv_ = v*(1-(1-frac)*s)
            lut_r = [v, q, p, p, tv_, v]; lut_g = [tv_, v, v, q, p, p]; lut_b = [p, p, tv_, v, v, q]
            r_out = np.clip(lut_r[hi_i] * 255, 0, 255).astype(np.uint8)
            g_out = np.clip(lut_g[hi_i] * 255, 0, 255).astype(np.uint8)
            b_out = np.clip(lut_b[hi_i] * 255, 0, 255).astype(np.uint8)
            ys, xs = np.where(no_ref)
            arr[ys, xs, 0] = r_out; arr[ys, xs, 1] = g_out; arr[ys, xs, 2] = b_out
            arr[ys, xs, 3] = 255


def apply_mask_clothing(arr: np.ndarray, features: dict):
    """스타일별 레퍼런스 스킨 텍스처 + HSV 색조 변환으로 의상 적용"""
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
    ref_arr   = _select_ref_skin(features)
    zone_maxv = _zone_stats(ref_arr, mask_arr)

    # 자켓 스타일: longsleeve를 먼저 깔고 jacket 오버레이 덮기
    if "jacket" in mask_path.name:
        base_mask_path = BASESKIN_DIR / "mask_longsleeve.png"
        if base_mask_path.exists():
            base_mask = np.array(Image.open(base_mask_path).convert("RGBA"), dtype=np.uint8)
            base_maxv = _zone_stats(ref_arr, base_mask)
            tmp_mask = base_mask.copy()
            for y in range(64):
                for x in range(64):
                    if mask_arr[y, x, 3] > 10:
                        tmp_mask[y, x, 3] = 0
            _paint_mask(arr, tmp_mask, ref_arr, zone_colors, base_maxv)

    _paint_mask(arr, mask_arr, ref_arr, zone_colors, zone_maxv)


def _mirror_clothing_to_layer2(arr: np.ndarray):
    """Layer1 의상 픽셀을 Layer2(오버레이) 위치에 그대로 복사"""
    # (src_y, src_x, dst_y, dst_x, h, w)
    PAIRS = [
        (16, 16, 32, 16, 16, 24),  # 몸통
        (16, 40, 32, 40, 16, 16),  # 오른팔
        (48, 32, 48, 48, 16, 16),  # 왼팔
        (16,  0, 32,  0, 16, 16),  # 오른다리
        (48, 16, 48,  0, 16, 16),  # 왼다리
    ]
    for sy, sx, dy, dx, h, w in PAIRS:
        src = arr[sy:sy+h, sx:sx+w]
        alive = src[:, :, 3] > 10
        if alive.any():
            arr[dy:dy+h, dx:dx+w][alive] = src[alive]


# ── 머리카락 ──────────────────────────────────────────────────────
# 뱅(앞머리/머리 전체) 파일 — 항상 먼저 합성
HAIR_BANGS_MAP = {
    "일자뱅": "base_hair_bangs_full.png",
    "사이드뱅": "base_hair_bangs_side.png",
    "노뱅":    "base_hair_bangs_none.png",
    "가르마":  "base_hair_bangs_curtain.png",
}
HAIR_BANGS_FALLBACK = "base_hair_bangs_full.png"

# 몸통 연장 파일 — 뱅 위에 추가 합성 (단발은 None)
HAIR_BODY_MAP: dict = {
    "장발_생머리":      ["base_hair_long_straight.png"],
    "장발_웨이브":      ["base_hair_long_wave.png"],
    "중장발_생머리":    ["base_hair_mid_straight.png"],
    "중장발_웨이브":    ["base_hair_mid_wave.png"],
    "꽁지머리":         ["base_hair_ponytail.png"],
    "짧은꽁지":         ["base_hair_short_ponytail.png"],
    "사이드테일":       ["base_hair_sidetail.png"],
    "양갈래_생머리":    ["base_hair_twin_straight_back.png", "base_hair_twin_straight_front.png"],
    "양갈래_웨이브":    ["base_hair_twin_wave_back.png",     "base_hair_twin_wave_front.png"],
    "짧은양갈래_생머리":["base_hair_twin_straight_short_back.png", "base_hair_twin_straight_short_front.png"],
    "짧은양갈래_웨이브":["base_hair_twin_wave_short_back.png",     "base_hair_twin_wave_front.png"],
    "단발": None,
}


def pick_hair_files(hair_style: str, hair_bangs: str = "") -> list:
    """뱅 파일 + 몸통 연장 파일 리스트 반환"""
    # 1) 뱅/머리 레이어
    bangs_name = HAIR_BANGS_MAP.get((hair_bangs or "").strip(), HAIR_BANGS_FALLBACK)
    files = [BASESKIN_DIR / bangs_name]

    # 2) 몸통 연장 레이어 (단발 or 미지정이면 None)
    body = HAIR_BODY_MAP.get((hair_style or "").strip())
    if body:
        for fname in body:
            p = BASESKIN_DIR / fname
            if p.exists():
                files.append(p)

    return [p for p in files if p.exists()]


def load_hair_base(hair_style: str = "", hair_bangs: str = "") -> list:
    return [
        np.array(Image.open(p).convert("RGBA"), dtype=np.uint8)
        for p in pick_hair_files(hair_style, hair_bangs)
    ]


def recolor_hair_base(hair_arr: np.ndarray, target_rgb: tuple) -> np.ndarray:
    """numpy 벡터화: 헤어 베이스 V값으로 타겟 색상 밝기 스케일"""
    valid = hair_arr[:, :, 3] > 10
    v_map = _np_rgb2v(hair_arr[:, :, :3])
    max_v = float(v_map[valid].max()) if valid.any() else 1.0
    if max_v < 0.01:
        max_v = 1.0

    brightness = np.clip(v_map / max_v, 0.0, 1.0)       # (64,64)
    result = hair_arr.copy()
    for c, col_val in enumerate(target_rgb):
        channel = np.clip(col_val * brightness, 0, 255).astype(np.uint8)
        result[:, :, c] = np.where(valid, channel, hair_arr[:, :, c])
    return result


def _composite_layer(arr: np.ndarray, colored: np.ndarray):
    """numpy 벡터화 알파 블렌딩"""
    a = colored[:, :, 3].astype(np.float32)
    opaque  = a >= 255
    partial = (a >= 10) & ~opaque

    # 완전 불투명 픽셀
    arr[opaque] = colored[opaque]

    # 반투명 픽셀
    if partial.any():
        fa = (a[partial] / 255.0)[:, np.newaxis]
        src = colored[partial, :3].astype(np.float32)
        dst = arr[partial, :3].astype(np.float32)
        arr[partial, :3] = np.clip(src * fa + dst * (1 - fa), 0, 255).astype(np.uint8)
        arr[partial, 3] = 255


def draw_hair_body_only(arr: np.ndarray, hair_rgb: tuple, hair_style: str):
    """몸통 연장 레이어만 합성 (의상 위에 덮기)"""
    body = HAIR_BODY_MAP.get((hair_style or "").strip())
    if not body:
        return
    for fname in body:
        p = BASESKIN_DIR / fname
        if p.exists():
            base_arr = np.array(Image.open(p).convert("RGBA"), dtype=np.uint8)
            colored = recolor_hair_base(base_arr, hair_rgb)
            _composite_layer(arr, colored)


def draw_hair_bangs_only(arr: np.ndarray, hair_rgb: tuple, hair_bangs: str):
    """앞머리(뱅) 레이어만 합성 (머리카락 최상단)"""
    bangs_name = HAIR_BANGS_MAP.get((hair_bangs or "").strip(), HAIR_BANGS_FALLBACK)
    p = BASESKIN_DIR / bangs_name
    if p.exists():
        base_arr = np.array(Image.open(p).convert("RGBA"), dtype=np.uint8)
        colored = recolor_hair_base(base_arr, hair_rgb)
        _composite_layer(arr, colored)


def draw_hair(arr: np.ndarray, hair_rgb: tuple, hair_style: str, hair_bangs: str = ""):
    """뱅(머리) + 몸통 연장 레이어 순서대로 재채색 후 합성"""
    for base_arr in load_hair_base(hair_style, hair_bangs):
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
    hair_bangs = features.get("hair_bangs", "")

    apply_mask_clothing(arr, features)               # 1. 의상
    draw_hair_body_only(arr, hair_rgb, hair_style)   # 2. 몸통 머리카락
    draw_hair_bangs_only(arr, hair_rgb, hair_bangs)  # 3. 앞머리 (최상단)
    _mirror_clothing_to_layer2(arr)                  # 4. 최종 레이어1 → 레이어2 복사

    if features.get("glasses", False):
        draw_glasses(arr)

    return Image.fromarray(arr, "RGBA")
