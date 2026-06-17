"""
skin_generator.py
특징 JSON → Pillow 픽셀 조작 → 64×64 마인크래프트 스킨 PNG
"""

import re
import numpy as np
from PIL import Image
from pathlib import Path
from colorsys import rgb_to_hsv, hsv_to_rgb

# ── numpy 벡터화 HSV 변환 ──────────────────────────────────────────
def _np_rgb2v(rgb_u8: np.ndarray) -> np.ndarray:
    """(H,W,3) uint8 → (H,W) V float32"""
    f = rgb_u8.astype(np.float32) / 255.0
    return f.max(axis=-1)

BRIGHTNESS_BOOST = 1.30  # 의상·머리 밝기 배율 (1.0 = 원본, 높을수록 밝아짐)

def _np_hsv_recolor(rgb_u8: np.ndarray, alpha: np.ndarray,
                    t_h: float, t_s: float,
                    ref_v: np.ndarray, max_v: float,
                    t_v: float, shade_map: np.ndarray = None,
                    v_floor: float = 0.0) -> np.ndarray:
    """ref_v 밝기를 유지하며 HSV 색조를 (t_h, t_s)로 교체. (H,W,3) uint8 반환.
    shade_map: 면별 음영 배율 (None이면 미적용). 밝은 의상(흰색 등)이 밝기
    보정으로 saturate되어 음영이 사라지는 것을 면별 셰이드로 보정.
    v_floor: 레퍼런스 명암 대비 압축 하한 (0=원본). 일부 레퍼런스의 몸통
    양옆 깊은 그림자가 흰옷에서 검정 세로 줄로 남는 것을 [v_floor,1]로 압축해 완화."""
    norm_v = np.clip(ref_v / max(max_v, 0.01), 0.0, 1.0)
    if v_floor > 0.0:
        norm_v = v_floor + (1.0 - v_floor) * norm_v
    final_v = norm_v * max(t_v, 0.15) * BRIGHTNESS_BOOST
    if shade_map is not None:
        final_v = final_v * shade_map
    final_v = np.clip(final_v, 0.0, 1.0)

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
    (28, 16,  8,  4, 0.92),  # body bottom (몸통 하단면 — 다리 접합부, 엉덩이 선 최소화)
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
    # 가랑이 그림자: 다리 안쪽 면 상단 3행 (앞면은 건드리지 않음)
    ( 8, 20,  4,  3, 0.55),  # 오른 다리 안쪽(좌면) 상단
    (24, 52,  4,  3, 0.55),  # 왼 다리 안쪽(우면) 상단
    # 의상 앞면 가장자리 AO — 텍스처가 평평한 레퍼런스(민무늬)도 모서리 음영으로
    # 입체감을 갖도록. 몸통·팔 앞면의 좌우 끝열을 살짝 어둡게.
    (20, 20,  1, 12, 0.80),  # 몸통 앞면 좌단
    (27, 20,  1, 12, 0.80),  # 몸통 앞면 우단
    (21, 20,  1, 12, 0.91),  # 몸통 앞면 좌 안쪽
    (26, 20,  1, 12, 0.91),  # 몸통 앞면 우 안쪽
    (44, 20,  1, 12, 0.84),  # 오른팔 앞면 좌단
    (47, 20,  1, 12, 0.84),  # 오른팔 앞면 우단
    (36, 52,  1, 12, 0.84),  # 왼팔 앞면 좌단
    (39, 52,  1, 12, 0.84),  # 왼팔 앞면 우단
]

def _build_shade_map() -> np.ndarray:
    shade_map = np.ones((64, 64), dtype=np.float32)
    for (x, y, w, h, f) in _SHADE_REGIONS:
        shade_map[y:y+h, x:x+w] = f
    return shade_map

_SHADE_MAP = _build_shade_map()


def _build_pleat_darken_map() -> np.ndarray:
    """치마/바지 주름 수직 줄무늬 다크닝 맵 (ref8/9 패턴 기반).
    1.0=원본, 낮을수록 어둡게. UV 면 내부 열 위치로 주름 음영 표현.
    y 범위를 지정해 BODY(y=16..32)와 LLEG(y=48..64)의 x 겹침 방지."""
    m = np.ones((64, 64), dtype=np.float32)

    def _stripe(y0, y1, x_start, cols_darken):
        """cols_darken: [(col_offset, factor), ...]"""
        for col, f in cols_darken:
            m[y0:y1, x_start + col] = np.minimum(m[y0:y1, x_start + col], f)

    # ── y=16..32 영역: BODY(x=16..40) + RLEG(x=0..16) ────────────
    # Body front (8px wide): ref9 패턴 — 중앙 cols 3,4 진하게, 2,5 중간
    _stripe(16, 32, 20, [(2, 0.82), (3, 0.70), (4, 0.70), (5, 0.82)])
    _stripe(16, 32, 16, [(1, 0.82), (2, 0.82)])   # body right  (4px)
    _stripe(16, 32, 28, [(1, 0.82), (2, 0.82)])   # body left   (4px)
    _stripe(16, 32, 32, [(2, 0.82), (3, 0.70), (4, 0.70), (5, 0.82)])  # body back (8px)
    _stripe(16, 32,  4, [(1, 0.86), (2, 0.86)])   # rleg front  (4px)
    _stripe(16, 32,  0, [(1, 0.86), (2, 0.86)])   # rleg right  (4px)
    _stripe(16, 32,  8, [(1, 0.86), (2, 0.86)])   # rleg left   (4px)
    _stripe(16, 32, 12, [(1, 0.86), (2, 0.86)])   # rleg back   (4px)

    # ── y=48..64 영역: LLEG(x=16..32) ───────────────────────────
    _stripe(48, 64, 20, [(1, 0.86), (2, 0.86)])   # lleg front  (4px)
    _stripe(48, 64, 16, [(1, 0.86), (2, 0.86)])   # lleg left   (4px)
    _stripe(48, 64, 24, [(1, 0.86), (2, 0.86)])   # lleg right  (4px)
    _stripe(48, 64, 28, [(1, 0.86), (2, 0.86)])   # lleg back   (4px)

    return m

_PLEAT_DARKEN_MAP = _build_pleat_darken_map()


def _load_skirt_shade_map(fname: str):
    """치마 전용 베이스 V맵 로드.
    비투명 픽셀 → raw V값, 투명 픽셀 → NaN, 파일 없으면 None 반환."""
    p = BASESKIN_DIR / fname
    if not p.exists():
        return None
    m = np.full((64, 64), np.nan, dtype=np.float32)
    img = np.array(Image.open(p).convert("RGBA"), dtype=np.uint8)
    has_pixel = img[:, :, 3] > 10
    v = _np_rgb2v(img[:, :, :3])
    m[has_pixel] = v[has_pixel]
    return m

_SHORT_SKIRT_SHADE = _load_skirt_shade_map("base_short_skirt.png")
_LONG_SKIRT_SHADE  = _load_skirt_shade_map("base_long_skirt.png")

# 다리 UV 서브 마스크 (밑단 행 동적 계산용)
_RLEG_UV = np.zeros((64, 64), dtype=bool)
_RLEG_UV[16:32, 0:16] = True
_LLEG_UV = np.zeros((64, 64), dtype=bool)
_LLEG_UV[48:64, 16:32] = True


# ── 마스크 파일 선택 ───────────────────────────────────────────────
# (top 키워드, bottom 키워드, 파일명) — 위에 있을수록 우선
# top/bot 키워드 모두 비어있으면 무조건 매칭 (폴백 역할)
MASK_STYLE_MAP = [
    # 자켓/코트/카디건/아우터 — 하의별 전용 마스크
    (["자켓","jacket","코트","블레이저","카디건","가디건","cardigan","니트","스웨터","집업","점퍼","후드집업"],
     ["반바지","shorts","쇼츠","핫팬츠","bermuda","짧은 바지","짧은바지","short pants"],  "mask_jacket_shorts.png"),
    (["자켓","jacket","코트","블레이저","카디건","가디건","cardigan","니트","스웨터","집업","점퍼","후드집업"],
     ["롱스커트","긴 스커트","맥시","원피스","드레스"],                                   "mask_jacket_longskirt.png"),
    (["자켓","jacket","코트","블레이저","카디건","가디건","cardigan","니트","스웨터","집업","점퍼","후드집업"],
     ["스커트","치마","미니"],                                                           "mask_jacket_skirt.png"),
    (["자켓","jacket","코트","블레이저","카디건","가디건","cardigan","니트","스웨터","집업","점퍼","후드집업"],
     [],                                                                               "mask_jacket.png"),
    # 오프숄더 / 크롭 (숄더리스) — 반바지 먼저, 치마, 롱스커트, 폴백 순
    (["오프숄더","off-shoulder"],  ["반바지","shorts","쇼츠","핫팬츠","bermuda","짧은바지","short pants"], "mask_crop_shorts_shorderless.png"),
    (["오프숄더","off-shoulder"],  ["롱스커트","긴 스커트","맥시","원피스","드레스"], "mask_crop_long_shorderless.png"),
    (["오프숄더","off-shoulder"],  ["스커트","치마","미니"],                          "mask_crop_shorts_shorderless.png"),
    (["오프숄더","off-shoulder"],  [],                                                "mask_crop_long_shorderless.png"),
    # 크롭탑
    (["크롭","crop"], ["롱스커트","긴 스커트","맥시","원피스","드레스"],              "mask_crop_skirt.png"),
    (["크롭","crop"], ["스커트","치마","미니"],                                        "mask_crop_skirt.png"),
    (["크롭","crop"], ["반바지","shorts","쇼츠","핫팬츠","bermuda","짧은 바지","짧은바지","short pants"], "mask_crop_shorts.png"),
    (["크롭","crop"], [],                                                              "mask_crop_long.png"),
    # 민소매
    (["민소매","나시","sleeveless","탱크"], ["롱스커트","긴 스커트","맥시","원피스","드레스"], "mask_sleeveless_longskirt.png"),
    (["민소매","나시","sleeveless","탱크"], ["스커트","치마","미니"],                        "mask_sleeveless_skirt.png"),
    (["민소매","나시","sleeveless","탱크"], ["반바지","shorts","쇼츠","핫팬츠","bermuda","짧은 바지","짧은바지","short pants"], "mask_sleeveless_shorts.png"),
    (["민소매","나시","sleeveless","탱크"], [],                                             "mask_sleeveless.png"),
    # 반팔
    (["반팔","short sleeve","반소매","반팔티","t-shirt","tshirt","티셔츠","tee","polo"], ["롱스커트","긴 스커트","맥시","원피스","드레스"],    "mask_shortsleeve_longskirt.png"),
    (["반팔","short sleeve","반소매","반팔티","t-shirt","tshirt","티셔츠","tee","polo"], ["스커트","치마","미니스커트"],                       "mask_shortsleeve_skirt.png"),
    (["반팔","short sleeve","반소매","반팔티","t-shirt","tshirt","티셔츠","tee","polo"], ["반바지","shorts","쇼츠","핫팬츠","bermuda","짧은 바지","짧은바지","short pants"], "mask_shortsleeve_shorts.png"),
    (["반팔","short sleeve","반소매","반팔티","t-shirt","tshirt","티셔츠","tee","polo"], [],                                                   "mask_shortsleeve.png"),
    # 긴팔 (나머지)
    ([], ["롱스커트","긴 스커트","맥시","원피스","드레스"],                                  "mask_longsleeve_longskirt.png"),
    ([], ["스커트","치마","미니스커트"],                                                     "mask_longsleeve_skirt.png"),
    ([], ["반바지","shorts","쇼츠","핫팬츠","bermuda","짧은 바지","짧은바지","short pants"], "mask_longsleeve_shorts.png"),
]
MASK_FALLBACK = "mask_longsleeve.png"

# 악세서리 키워드 → 오버레이 마스크
ACC_OVERLAY_MAP = [
    (["시계","watch"],                        "mask_acc_watch.png"),
    (["목걸이","necklace","체인"],             "mask_acc_necklace.png"),
    (["귀걸이","earring","이어링"],            "mask_acc_earrings.png"),
    (["벨트","belt"],                          "mask_acc_belt.png"),
    (["부츠","boots"],                         "mask_acc_boots.png"),
]


def pick_mask(features: dict) -> Path:
    top = (features.get("top_style",    "") or "").lower()
    bot = (features.get("bottom_style", "") or "").lower()

    # 반바지 여부를 _SHORTS_SYNONYMS 전체로 판단 (MASK_STYLE_MAP 키워드보다 넓음)
    is_shorts = any(k in bot for k in _SHORTS_SYNONYMS)

    for top_kws, bot_kws, filename in MASK_STYLE_MAP:
        top_ok = (not top_kws) or any(k in top for k in top_kws)
        # 반바지 키워드가 bot_kws에 있는 행이면 is_shorts로 대체 판단
        has_shorts_kw = any(k in ["반바지","shorts","쇼츠"] for k in bot_kws)
        if has_shorts_kw:
            bot_ok = is_shorts
        else:
            bot_ok = (not bot_kws) or any(k in bot for k in bot_kws)
        if top_ok and bot_ok:
            p = BASESKIN_DIR / filename
            if p.exists():
                return p
    return BASESKIN_DIR / MASK_FALLBACK


def pick_acc_overlays(features: dict) -> list[Path]:
    """악세서리 텍스트에서 오버레이 마스크 파일 목록 반환"""
    acc = (features.get("accessories", "") or "").lower()
    if not acc or acc == "없음":
        return []
    overlays = []
    for kws, filename in ACC_OVERLAY_MAP:
        if any(k in acc for k in kws):
            p = BASESKIN_DIR / filename
            if p.exists():
                overlays.append(p)
    # 신발 스타일 기반 부츠 처리
    shoes = (features.get("shoes_color", "") or "").lower() + (features.get("bottom_style", "") or "").lower()
    if any(k in shoes for k in ["부츠","boots"]):
        p = BASESKIN_DIR / "mask_acc_boots.png"
        if p.exists() and p not in overlays:
            overlays.append(p)
    return overlays


_REF_SKIN_CACHE: dict = {}

# ── 스타일 키워드 → 레퍼런스 스킨 매핑 ──────────────────────────────
# 우선순위 높은 것부터 (특수 의상만 등록, 나머지는 색상 자동 매칭)
_STYLE_REF_MAP = [
    # (상의 키워드, 하의 키워드, 레퍼런스 파일)
    (["교복", "school uniform", "세일러", "교복치마"],      [],   "reference (10).png"),
    (["정장", "suit", "비즈니스", "포멀", "자켓", "블레이저", "jacket"], ["슬랙스", "정장", ""], "reference (22).png"),
    (["한복", "저고리", "치마저고리"],                      [],   "reference (65).png"),
    (["경찰", "police", "군복", "유니폼", "제복"],          [],   "reference (5).png"),
    (["웨딩", "웨딩드레스", "wedding"],                     [],   "reference (33).png"),
    (["드레스", "원피스", "dress"],                          [],   "reference (58).png"),
    ([], ["드레스", "원피스", "dress"],                            "reference (58).png"),
    (["수영복", "비키니", "swimsuit"],                       [],   "reference (35).png"),
    (["스포츠", "운동복", "트레이닝", "sport", "gym"],      [],   "reference (62).png"),
    (["후드", "hoodie", "sweatshirt"],                      [],   "reference (56).png"),
]
_REF_FALLBACK = "reference (14).png"

# ── 레퍼런스 태그 사전 (모듈 로드 시 1회 로드) ───────────────────────
import json as _json

_REF_TAGS: dict = {}

def _load_ref_tags():
    tags_path = BASESKIN_DIR / "reference_tags.json"
    if tags_path.exists():
        try:
            _REF_TAGS.update(_json.loads(tags_path.read_text(encoding="utf-8")))
        except Exception:
            pass

_load_ref_tags()

# ── 컴포넌트 라이브러리 (mine_assets.py 실행 후 활성화) ──────────────
_COMP_CACHE: dict = {}
_COMP_INDEX: dict = {}

def _load_comp_index():
    idx_path = BASESKIN_DIR / "components" / "component_index.json"
    if idx_path.exists():
        try:
            _COMP_INDEX.update(_json.loads(idx_path.read_text(encoding="utf-8")))
        except Exception:
            pass

_load_comp_index()


def _load_component(ref_num: str, comp_name: str):
    """baseskin/components/ref{N}_{comp}.png 로드 (캐시)"""
    key = f"{ref_num}_{comp_name}"
    if key not in _COMP_CACHE:
        p = BASESKIN_DIR / "components" / f"ref{ref_num}_{comp_name}.png"
        _COMP_CACHE[key] = np.array(Image.open(p).convert("RGBA"), dtype=np.uint8) if p.exists() else None
    return _COMP_CACHE[key]


def _hex_to_rgb(hex_str) -> np.ndarray:
    if not hex_str:
        return np.array([128, 128, 128], dtype=np.float32)
    h = str(hex_str).lstrip("#")
    if len(h) == 6:
        return np.array([int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)], dtype=np.float32)
    return np.array([128, 128, 128], dtype=np.float32)


# 의상 패턴 키워드 — 민무늬 입력에 패턴 레퍼런스가 선택되는 것을 막기 위함.
# 레퍼런스 텍스처의 체크·줄무늬는 HSV 재채색 후에도 격자 음영으로 남아
# 흰색 등 단색 의상을 더럽힌다.
_PATTERN_KWS = [
    "체크", "플래드", "plaid", "check", "스트라이프", "stripe", "줄무늬",
    "격자", "타탄", "tartan", "도트", "폴카", "물방울", "아가일", "argyle",
    "패턴", "pattern", "꽃무늬", "floral", "레이어드",
]

def _has_pattern(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in _PATTERN_KWS)


def _score_ref_top(fname: str, features: dict) -> float:
    """상의 기준 유사도 점수"""
    tag = _REF_TAGS.get(fname, {})
    if not tag:
        return 0.0
    score = 0.0
    top_style  = (features.get("top_style", "") or "").lower()
    gender_exp = (features.get("gender_expression", "") or "").lower()
    ref_tags   = [t.lower() for t in tag.get("style_tags", [])]
    ref_top    = (tag.get("top_style", "") or "").lower()
    ref_gender = (tag.get("gender", "") or "").lower()

    for rt in ref_tags:
        if rt in top_style:
            score += 15.0
    for word in top_style.split():
        if len(word) > 1 and word in ref_top:
            score += 10.0

    # 의상 레퍼런스는 성별 무관 — 카테고리(반소매/긴소매/치마 등)만 매칭
    # 성별 가중치 제거: 남성 입력에 여성 레퍼런스 의상 텍스처를 써도 문제없음

    top_rgb = parse_color(features.get("top_color") or "#888888")
    ref_top_rgb = _hex_to_rgb(tag.get("top_color") or "#888888")
    t = np.array(top_rgb, dtype=np.float32)
    color_dist = float(np.sum((ref_top_rgb - t) ** 2))
    score += max(0.0, 10.0 - color_dist / 3000.0)

    # 패턴 회피: 입력이 민무늬인데 레퍼런스가 체크·줄무늬 등 패턴이면 큰 페널티.
    input_has_pattern = _has_pattern(top_style)
    ref_has_pattern   = _has_pattern(ref_top) or any(_has_pattern(rt) for rt in ref_tags)
    if ref_has_pattern and not input_has_pattern:
        score -= 50.0  # 민무늬 입력에 패턴 레퍼런스 강력 억제

    # 민무늬 보너스: 입력이 민무늬이고 레퍼런스도 민무늬면 +10
    _PLAIN_KWS = ["티셔츠", "tshirt", "t-shirt", "tee", "민무늬", "plain", "단색", "솔리드",
                  "solid", "기본", "베이직", "basic"]
    input_is_plain = (not input_has_pattern) and any(k in top_style for k in _PLAIN_KWS)
    if input_is_plain and not ref_has_pattern:
        score += 10.0
    return score


_SHORTS_SYNONYMS = {
    "반바지","쇼츠","shorts","핫팬츠","bermuda","짧은바지","짧은 바지","short pants",
    "hot pants","cutoff","denim shorts","데님 쇼츠","cargo short",
    "5부 바지","7부 바지","5부","반팬츠","체크 쇼츠","짧은 팬츠",
    "short","ショーツ","쇼트 팬츠","short pants","반 바지",
}
_SKIRT_SYNONYMS  = {"치마","스커트","skirt","미니스커트","롱스커트"}
_PANTS_SYNONYMS  = {"바지","슬랙스","청바지","pants","slacks","trousers","leggings"}

def _bottom_category(style: str) -> str:
    s = style.lower()
    # shorts 먼저 — "short sleeve" 같은 상의 설명에 "short"가 있을 수 있으므로
    # 명확한 하의 키워드 우선, 그 다음 "short" 단어 단독 체크
    specific_shorts = _SHORTS_SYNONYMS - {"short"}
    if any(k in s for k in specific_shorts): return "shorts"
    if any(k in s for k in _SKIRT_SYNONYMS):  return "skirt"
    if any(k in s for k in _PANTS_SYNONYMS):  return "pants"
    # "short"가 bottom_style에 단독으로 있는 경우 (ex: "grey short")
    words = s.split()
    if "short" in words or "shorts" in words: return "shorts"
    return "unknown"

def _score_ref_bot(fname: str, features: dict) -> float:
    """하의 기준 유사도 점수"""
    tag = _REF_TAGS.get(fname, {})
    if not tag:
        return 0.0
    score = 0.0
    bot_style  = (features.get("bottom_style", "") or "").lower()
    gender_exp = (features.get("gender_expression", "") or "").lower()
    ref_tags   = [t.lower() for t in tag.get("style_tags", [])]
    ref_bot    = (tag.get("bottom_style", "") or "").lower()
    ref_gender = (tag.get("gender", "") or "").lower()

    # 하의 카테고리(반바지/치마/바지) 일치 여부 (가장 중요)
    input_cat = _bottom_category(bot_style)
    ref_cat   = _bottom_category(ref_bot)
    if input_cat != "unknown" and input_cat == ref_cat:
        score += 25.0
    elif input_cat != "unknown" and ref_cat != "unknown" and input_cat != ref_cat:
        score -= 10.0  # 카테고리 불일치 페널티

    # 반바지 목표: 레퍼런스의 다리 하단이 피부색에 가까울수록 가산점
    # (짧은 옷/맨다리를 가진 레퍼런스가 반바지 허벅지 텍스처로 적합)
    if input_cat == "shorts":
        ref_arr = _load_ref(fname)
        # 오른다리 하단 3행 (y=29..32, x=4..8) 평균 색
        leg_lower = ref_arr[29:32, 4:8, :]
        valid = leg_lower[:, :, 3] > 10
        if valid.any():
            lower_rgb = leg_lower[valid, :3].astype(float).mean(axis=0)
            # 피부색 추정: 노랑/빨강 채널이 높고 파랑 낮으면 피부
            r, g, b = lower_rgb
            is_skin_like = r > 150 and g > 120 and b < 180 and r > b
            if is_skin_like:
                score += 15.0  # 하단이 맨살 → 반바지 레퍼런스

    for rt in ref_tags:
        if rt in bot_style:
            score += 15.0
    for word in bot_style.split():
        if len(word) > 1 and word in ref_bot:
            score += 10.0

    # 의상 레퍼런스는 성별 무관 — 치마/바지/반바지 카테고리만 매칭

    bot_rgb = parse_color(features.get("bottom_color") or "#888888")
    ref_bot_rgb = _hex_to_rgb(tag.get("bottom_color") or "#888888")
    b = np.array(bot_rgb, dtype=np.float32)
    color_dist = float(np.sum((ref_bot_rgb - b) ** 2))
    score += max(0.0, 10.0 - color_dist / 3000.0)

    # 청바지 입력 시 다리 UV 텍스처 풍부도(std) 보너스 — 디테일 많은 레퍼런스 우선
    _JEANS_KWS = ["청바지", "데님", "denim", "jean", "jeans"]
    if any(k in bot_style for k in _JEANS_KWS):
        ref_arr = _load_ref(fname)
        rleg = ref_arr[20:32, 0:16]
        lleg = ref_arr[52:64, 16:32]
        all_px: list = []
        if (rleg[:, :, 3] > 10).any():
            all_px.append(rleg[rleg[:, :, 3] > 10, :3].astype(float))
        if (lleg[:, :, 3] > 10).any():
            all_px.append(lleg[lleg[:, :, 3] > 10, :3].astype(float))
        if all_px:
            px = np.concatenate(all_px)
            leg_std = float(px.max(axis=1).std() / 255.0)
            score += leg_std * 25.0

    return score


def _score_ref_arm(fname: str, features: dict) -> float:
    """팔 컴포넌트 — 소매 길이 일치 시 +20, 불일치 -10"""
    score = _score_ref_top(fname, features)
    tag = _REF_TAGS.get(fname, {})
    if not tag:
        return score

    top_style = (features.get("top_style", "") or "").lower()
    ref_top   = (tag.get("top_style", "") or "").lower()

    _SLEEVE_SHORT     = ["반팔","short sleeve","반소매","반팔티"]
    _SLEEVE_NONE      = ["민소매","sleeveless","나시","탱크","오프숄더"]

    def sleeve_type(s: str) -> str:
        if any(k in s for k in _SLEEVE_NONE):  return "none"
        if any(k in s for k in _SLEEVE_SHORT): return "short"
        return "long"

    if sleeve_type(top_style) == sleeve_type(ref_top):
        score += 20.0
    else:
        score -= 10.0
    return score


def _score_ref_hair(ref_num: str, features: dict) -> float:
    """헤드 컴포넌트 기준 헤어 유사도 (성별 + 머리 윗면 대표색)"""
    tag = _COMP_INDEX.get(ref_num, {})
    score = 0.0

    gender_exp = (features.get("gender_expression", "") or "").lower()
    ref_gender = (tag.get("gender", "") or "").lower()
    gender_map = {"여성적": "여성", "남성적": "남성", "중성적": "중성"}
    if gender_map.get(gender_exp) == ref_gender:
        score += 10.0

    head_comp = _load_component(ref_num, "head")
    if head_comp is not None:
        # 머리 윗면 (UV y=0..8, x=8..16) 대표색 ≈ 헤어 대표색
        top_face = head_comp[0:8, 8:16, :]
        valid = top_face[:, :, 3] > 10
        if valid.any():
            dominant = top_face[valid, :3].astype(float).mean(axis=0)
            target   = _hex_to_rgb(features.get("hair_color") or "#2b1a0e")
            dist     = float(np.sum((dominant - target) ** 2))
            score   += max(0.0, 20.0 - dist / 1200.0)
    return score


def _best_ref(score_fn, features: dict, fallback: str) -> str:
    all_refs = sorted(BASESKIN_DIR.glob("reference (*).png"))
    best_fname = fallback
    best_score = -1.0
    for p in all_refs:
        s = score_fn(p.name, features)
        if s > best_score:
            best_score = s
            best_fname = p.name
    return best_fname, best_score


# 의상이 칠해지는 UV 면 (앞/뒤/좌/우) — 레퍼런스 텍스처 정규화 대상
_CLOTH_FACES = [
    (20, 20, 8, 12), (32, 20, 8, 12), (16, 20, 4, 12), (28, 20, 4, 12),  # 몸통
    (44, 20, 4, 12), (52, 20, 4, 12), (40, 20, 4, 12), (48, 20, 4, 12),  # 오른팔
    (36, 52, 4, 12), (44, 52, 4, 12), (32, 52, 4, 12), (40, 52, 4, 12),  # 왼팔(L1)
    ( 4, 20, 4, 12), (12, 20, 4, 12), ( 0, 20, 4, 12), ( 8, 20, 4, 12),  # 오른다리
    (20, 52, 4, 12), (28, 52, 4, 12), (16, 52, 4, 12), (24, 52, 4, 12),  # 왼다리(L1)
]


def _normalize_ref_clothing(arr: np.ndarray) -> np.ndarray:
    """의상 UV 면별로 극단 이상치(가장자리 그림자·UV 경계 검정)의 밝기를 완화.
    단색 의상 재채색 시 검정 줄·점 아티팩트를 원천 차단하되, 정상 음영·
    체크무늬·진짜 검정 옷은 보존한다. 면별로:
    - 면 대부분(70%+)이 순검정이면 진짜 검정 옷 → 그대로 보존
    - 그 외엔 순검정(V<0.04) 노이즈를 정상 중앙값으로 끌어올림
    - 면이 밝으면(중앙값≥0.15) 중앙값의 45% 미만 그림자도 62%로 완화"""
    out = arr.copy()
    v = arr[:, :, :3].max(axis=-1).astype(np.float32) / 255.0
    for (x, y, w, h) in _CLOTH_FACES:
        valid = out[y:y+h, x:x+w, 3] > 10
        if int(valid.sum()) < 4:
            continue
        vv = v[y:y+h, x:x+w]
        nonblack = valid & (vv >= 0.04)
        if nonblack.sum() / max(int(valid.sum()), 1) < 0.30:
            continue  # 면 대부분 검정 = 진짜 검정 옷, 보존
        med = float(np.median(vv[nonblack]))
        # 밝은 면이면 그림자 이상치까지, 아니면 순검정 노이즈만 대상
        if med >= 0.15:
            thresh, floor = med * 0.45, med * 0.62
        else:
            thresh, floor = 0.04, med
        ys, xs = np.where(valid & (vv < thresh))
        for yy, xx in zip(ys, xs):
            gy, gx = y + yy, x + xx
            cur = float(v[gy, gx])
            if cur < 0.04:                      # 순검정 노이즈 → 무채색 회색
                g = int(np.clip(floor * 255, 0, 255))
                out[gy, gx, :3] = (g, g, g)
            else:                               # 어두운 이상치 → floor 밝기로 스케일
                sc = floor / cur
                out[gy, gx, :3] = np.clip(
                    out[gy, gx, :3].astype(np.float32) * sc, 0, 255).astype(np.uint8)
    return out


def _load_ref(fname: str) -> np.ndarray:
    if fname not in _REF_SKIN_CACHE:
        path = BASESKIN_DIR / fname
        if not path.exists():
            path = BASESKIN_DIR / _REF_FALLBACK
        arr = np.array(Image.open(path).convert("RGBA"), dtype=np.uint8)
        _REF_SKIN_CACHE[fname] = _normalize_ref_clothing(arr)
    return _REF_SKIN_CACHE[fname]


def _select_ref_components(features: dict) -> dict:
    """
    4-way 레퍼런스 + 헤드 컴포넌트 선택.
    반환: {"body": arr, "arm": arr, "leg": arr, "head_comp": arr|None}
    """
    top_style = (features.get("top_style", "") or "").lower()
    bot_style = (features.get("bottom_style", "") or "").lower()

    # 치마류 전용 leg 레퍼런스 — STYLE_REF_MAP보다 먼저 계산해서 모든 경로에 적용
    _MINI_KWS  = {"미니", "짧은치마", "short skirt", "miniskirt", "미니스커트", "미니 스커트"}
    _LONG_KWS  = {"롱스커트", "롱 스커트", "long skirt", "longskirt", "맥시", "플리츠롱", "롱드레스", "맥시드레스"}
    _SKIRT_KWS2 = {"치마", "스커트", "skirt", "드레스", "dress", "원피스", "플리츠", "프릴", "레이어드"}
    _is_mini   = any(k in bot_style for k in _MINI_KWS)
    _is_long   = any(k in bot_style for k in _LONG_KWS)
    _is_skirt2 = any(k in bot_style for k in _SKIRT_KWS2)
    _skirt_leg_ref: str | None = None
    if _is_mini or (_is_skirt2 and not _is_long):
        if (BASESKIN_DIR / "base_short_skirt.png").exists():
            _skirt_leg_ref = "base_short_skirt.png"
    elif _is_long or _is_skirt2:
        if (BASESKIN_DIR / "base_long_skirt.png").exists():
            _skirt_leg_ref = "base_long_skirt.png"

    # 특수 스타일: body/arm은 동일 레퍼런스, leg는 치마 전용 레퍼런스 우선 적용
    for top_kws, bot_kws, fname in _STYLE_REF_MAP:
        top_ok = (not top_kws) or any(k in top_style for k in top_kws)
        bot_ok = (not bot_kws) or any(k in bot_style for k in bot_kws)
        if top_ok and bot_ok and (BASESKIN_DIR / fname).exists():
            arr      = _load_ref(fname)
            leg_arr  = _load_ref(_skirt_leg_ref) if _skirt_leg_ref else arr
            print(f"[ref_select] special → {fname} (leg={_skirt_leg_ref or fname})")
            return {"body": arr, "arm": arr, "leg": leg_arr, "head_comp": None}

    all_refs = sorted(BASESKIN_DIR.glob("reference (*).png"))

    # 한복/전통의상 레퍼런스(59~66)는 관련 키워드 없으면 후보 제외
    _HANBOK_REF_NUMS = frozenset(range(59, 67))
    _HANBOK_KWS = {"한복", "저고리", "치마저고리", "유카타", "기모노", "치파오",
                   "전통의상", "hanbok", "yukata", "kimono", "cheongsam", "아시안"}
    _input_text = top_style + " " + bot_style
    _is_hanbok_input = any(k in _input_text for k in _HANBOK_KWS)

    best_body = (_REF_FALLBACK, -1.0)
    best_arm  = (_REF_FALLBACK, -1.0)
    best_leg  = (_REF_FALLBACK, -1.0)
    best_hair = (None, -1.0)

    for p in all_refs:
        fname = p.name
        _m = re.search(r'reference \((\d+)\)', fname)
        if _m and int(_m.group(1)) in _HANBOK_REF_NUMS and not _is_hanbok_input:
            continue  # 한복 레퍼런스는 관련 입력 없으면 스킵

        t_score = _score_ref_top(fname, features)
        a_score = _score_ref_arm(fname, features)
        b_score = _score_ref_bot(fname, features)

        if t_score > best_body[1]: best_body = (fname, t_score)
        if a_score > best_arm[1]:  best_arm  = (fname, a_score)
        if b_score > best_leg[1]:  best_leg  = (fname, b_score)

        if _COMP_INDEX:
            if _m:
                ref_num = _m.group(1)
                h_score = _score_ref_hair(ref_num, features)
                if h_score > best_hair[1]:
                    best_hair = (ref_num, h_score)

    leg_fname = _skirt_leg_ref if _skirt_leg_ref else best_leg[0]
    print(f"[ref_select] body={best_body[0]}({best_body[1]:.1f}) "
          f"arm={best_arm[0]}({best_arm[1]:.1f}) "
          f"leg={leg_fname} "
          f"hair_ref={best_hair[0]}")

    head_comp = None
    if _COMP_INDEX and best_hair[0]:
        head_comp = _load_component(best_hair[0], "head")

    return {
        "body":      _load_ref(best_body[0]),
        "arm":       _load_ref(best_arm[0]),
        "leg":       _load_ref(leg_fname),
        "head_comp": head_comp,
    }


def _select_ref_pair(features: dict) -> tuple:
    """하위 호환 래퍼 — (body_ref, leg_ref)"""
    comps = _select_ref_components(features)
    return comps["body"], comps["leg"]


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


_TOP_ZONES = {"top", "jacket", "acc"}
_BOT_ZONES = {"bottom", "shoes"}

# 팔 UV 영역 — top/jacket 존 중 팔에 속하는 픽셀 구분용
_ARM_UV_MASK = np.zeros((64, 64), dtype=bool)
_ARM_UV_MASK[16:32, 40:56] = True   # 오른팔 레이어1
_ARM_UV_MASK[48:64, 32:48] = True   # 왼팔 레이어1

# 다리 UV 영역 — BOT 존 중 실제 다리에 속하는 픽셀 구분용
# (몸통 하단 픽셀은 body_ref V, 다리 픽셀은 leg_ref V 사용 → 색 연결 일관성)
_LEG_UV_MASK = np.zeros((64, 64), dtype=bool)
_LEG_UV_MASK[16:32, 0:16]  = True   # 오른다리 레이어1
_LEG_UV_MASK[48:64, 16:32] = True   # 왼다리 레이어1


def _zone_stats_split(body_ref: np.ndarray, bot_ref: np.ndarray,
                      mask_arr: np.ndarray,
                      arm_ref: np.ndarray = None) -> dict:
    """존별 최대 V — body/arm/bot 참조를 각각 다른 ref로"""
    if arm_ref is None:
        arm_ref = body_ref
    body_v = _np_rgb2v(body_ref[:, :, :3])
    arm_v  = _np_rgb2v(arm_ref[:, :, :3])
    bot_v  = _np_rgb2v(bot_ref[:, :, :3])
    body_valid = body_ref[:, :, 3] > 10
    arm_valid  = arm_ref[:, :, 3] > 10
    bot_valid  = bot_ref[:, :, 3] > 10
    maxv: dict = {}
    for zone, zmask in _build_zone_masks(mask_arr).items():
        if zone in _BOT_ZONES:
            # 다리 UV는 bot_ref, 몸통 하단 UV는 body_ref → 통합 maxV로 일관 정규화
            leg_part  = zmask & _LEG_UV_MASK & bot_valid
            body_part = zmask & ~_LEG_UV_MASK & body_valid
            combined  = leg_part | body_part
            if combined.any():
                parts = []
                if leg_part.any():  parts.append(bot_v[leg_part])
                if body_part.any(): parts.append(body_v[body_part])
                all_v = np.concatenate(parts)
                maxv[zone] = float(all_v.max()) if len(all_v) > 0 else 1.0
            continue
        elif zone in _TOP_ZONES:
            arm_part  = zmask & _ARM_UV_MASK & arm_valid
            body_part = zmask & ~_ARM_UV_MASK & body_valid
            combined  = arm_part | body_part
            rv = np.where(_ARM_UV_MASK, arm_v, body_v)
        else:
            combined = zmask & body_valid
            rv = body_v
        if combined.any():
            maxv[zone] = float(rv[combined].max())
    return maxv


def _paint_bot_zone_flat(arr: np.ndarray, zmask: np.ndarray,
                         target_rgb: tuple, use_pleat: bool = False,
                         skirt_shade_map: np.ndarray = None) -> None:
    """BOT 존 전용: shade_map + 밑단 암화.
    skirt_shade_map: base_short/long_skirt.png 로드된 V맵 (NaN=투명)."""
    tr, tg, tb = target_rgb
    t_h, t_s, t_v = rgb_to_hsv(tr / 255, tg / 255, tb / 255)
    t_v = max(t_v, 0.15)
    if not zmask.any():
        return
    ys, xs = np.where(zmask)
    if skirt_shade_map is not None:
        # 치마: 마스크 범위(레이어1+2) 사용, 베이스 V를 상대 명암으로 정규화
        base_v = skirt_shade_map[ys, xs]   # NaN = 투명(base에 없는 위치)
        has_b  = ~np.isnan(base_v)
        if has_b.any():
            min_v   = float(base_v[has_b].min())
            max_v   = float(base_v[has_b].max())
            range_v = max(max_v - min_v, 0.01)
            # [min_v, max_v] → [0, 1] 정규화 후 power curve로 중간 명암 강조
            # floor 0.35: 가장 어두운 픽셀은 35% 밝기, 중간값은 power로 눌러줌
            linear = ((base_v - min_v) / range_v).clip(0, 1)
            norm  = np.where(has_b,
                             0.35 + 0.65 * (linear ** 2.5),
                             0.85).astype(np.float32)
        else:
            norm  = np.full(len(ys), 0.85, dtype=np.float32)
        final_v = np.clip(t_v * norm * BRIGHTNESS_BOOST, 0.0, 1.0)
    else:
        shades = _SHADE_MAP[ys, xs]
        pleat  = _PLEAT_DARKEN_MAP[ys, xs] if use_pleat else np.ones(len(ys), dtype=np.float32)

        hem = np.ones(len(ys), dtype=np.float32)
        for leg_uv in (_RLEG_UV, _LLEG_UV):
            in_leg = leg_uv[ys, xs]
            if in_leg.any():
                leg_ys = ys[in_leg]
                leg_y_max = int(leg_ys.max())
                if leg_y_max - int(leg_ys.min()) > 3:
                    in_hem = in_leg & (ys >= leg_y_max - 1)
                    hem[in_hem] = 0.74

        final_v = np.clip(t_v * shades * pleat * hem * BRIGHTNESS_BOOST, 0.0, 1.0)
    hi_f = t_h * 6.0; hi_i = int(hi_f) % 6; frac = hi_f - int(hi_f)
    p_v  = final_v * (1 - t_s)
    q_v  = final_v * (1 - frac * t_s)
    tv_  = final_v * (1 - (1 - frac) * t_s)
    lut  = [(final_v, q_v, p_v, p_v, tv_, final_v),
            (tv_, final_v, final_v, q_v, p_v, p_v),
            (p_v, p_v, tv_, final_v, final_v, q_v)]
    arr[ys, xs, 0] = np.clip(lut[0][hi_i] * 255, 0, 255).astype(np.uint8)
    arr[ys, xs, 1] = np.clip(lut[1][hi_i] * 255, 0, 255).astype(np.uint8)
    arr[ys, xs, 2] = np.clip(lut[2][hi_i] * 255, 0, 255).astype(np.uint8)
    arr[ys, xs, 3] = 255


def _paint_mask(arr, mask_arr, body_ref, bot_ref, zone_colors, zone_maxv,
                arm_ref=None, is_skirt=False, skirt_shade_map=None, is_denim=False):
    """존별로 다른 레퍼런스 텍스처를 사용해 HSV 색조 변환 적용.
    팔 UV 영역은 arm_ref, 몸통은 body_ref, 다리/신발은 bot_ref 사용.
    is_denim=True: 하의 bottom 존을 레퍼런스 V맵으로 재채색 (텍스처 보존)."""
    if arm_ref is None:
        arm_ref = body_ref

    body_v = _np_rgb2v(body_ref[:, :, :3])
    arm_v  = _np_rgb2v(arm_ref[:, :, :3])
    bot_v  = _np_rgb2v(bot_ref[:, :, :3])
    body_valid = body_ref[:, :, 3] > 10
    arm_valid  = arm_ref[:, :, 3] > 10
    bot_valid  = bot_ref[:, :, 3] > 10

    zone_masks = _build_zone_masks(mask_arr)

    def _paint_zone_pixels(zmask_sub, ref_v_map, ref_valid,
                           target_rgb, mv):
        """zmask_sub 영역을 ref_v 기반으로 HSV 재채색"""
        if not zmask_sub.any():
            return
        tr, tg, tb = target_rgb
        t_h, t_s, t_v = rgb_to_hsv(tr/255, tg/255, tb/255)

        # ref V<0.05 픽셀(레퍼런스 UV 경계 검정)은 has_ref에서 제외 → shade맵 경로로
        # 처리. 흰색 등 밝은 의상 재채색 시 pure-black 아티팩트(배경에 묻혀 단색처럼
        # 보이는 버그)를 팔·몸통·목 모든 존에서 일괄 차단.
        ref_ok  = ref_valid & (ref_v_map > 0.05)
        has_ref = zmask_sub & ref_ok
        no_ref  = zmask_sub & ~ref_ok

        if has_ref.any():
            rgb_out = _np_hsv_recolor(arr[:, :, :3], arr[:, :, 3],
                                      t_h, t_s, ref_v_map, mv, t_v,
                                      shade_map=_SHADE_MAP, v_floor=0.30)
            ys, xs = np.where(has_ref)
            arr[ys, xs, :3] = rgb_out[ys, xs]
            arr[ys, xs, 3]  = 255

        if no_ref.any():
            final_v = np.clip(t_v * (0.8 + 0.2 * _SHADE_MAP[no_ref]), 0.0, 1.0)
            v = final_v; s = t_s; hi_f = t_h * 6.0; hi_i = int(hi_f) % 6
            frac = hi_f - int(hi_f)
            p_v = v*(1-s); q_v = v*(1-frac*s); tv_ = v*(1-(1-frac)*s)
            lut_r = [v, q_v, p_v, p_v, tv_, v]
            lut_g = [tv_, v, v, q_v, p_v, p_v]
            lut_b = [p_v, p_v, tv_, v, v, q_v]
            r_out = np.clip(lut_r[hi_i] * 255, 0, 255).astype(np.uint8)
            g_out = np.clip(lut_g[hi_i] * 255, 0, 255).astype(np.uint8)
            b_out = np.clip(lut_b[hi_i] * 255, 0, 255).astype(np.uint8)
            ys, xs = np.where(no_ref)
            arr[ys, xs, 0] = r_out; arr[ys, xs, 1] = g_out; arr[ys, xs, 2] = b_out
            arr[ys, xs, 3] = 255

    for zone, zmask in zone_masks.items():
        if not zmask.any():
            continue
        target_rgb = zone_colors.get(zone, DEFAULT_COLOR)
        mv = zone_maxv.get(zone, 1.0)

        if zone in _BOT_ZONES:
            if zone == "bottom" and is_denim:
                # 청바지/청반바지: 레퍼런스 V맵으로 텍스처 재채색 (상의와 동일 방식)
                _paint_zone_pixels(zmask, bot_v, bot_valid, target_rgb, mv)
            else:
                _paint_bot_zone_flat(arr, zmask, target_rgb,
                                     use_pleat=(is_skirt and zone == "bottom"),
                                     skirt_shade_map=skirt_shade_map if (is_skirt and zone == "bottom") else None)
        elif zone in _TOP_ZONES:
            # 팔 UV: sleeve 색이 별도로 있으면 그것 사용, 없으면 target_rgb
            # (V<0.05 검정 픽셀 필터는 _paint_zone_pixels 내부에서 일괄 처리)
            sleeve_rgb = zone_colors.get("sleeve", target_rgb)
            _paint_zone_pixels(zmask & _ARM_UV_MASK,  arm_v,  arm_valid,  sleeve_rgb, mv)
            _paint_zone_pixels(zmask & ~_ARM_UV_MASK, body_v, body_valid, target_rgb, mv)
        else:
            _paint_zone_pixels(zmask, body_v, body_valid, target_rgb, mv)


def apply_mask_clothing(arr: np.ndarray, features: dict,
                        _comps: dict = None, _return_neck_painter: bool = False):
    """스타일별 레퍼런스 스킨 텍스처 + HSV 색조 변환으로 의상 적용.
    _comps: _select_ref_components() 결과를 외부에서 전달 (캐싱용)
    _return_neck_painter: True면 비재킷 넥 액세서리를 바로 칠하지 않고
        callable을 반환 — _fill_back_faces 이후에 호출해 뒷면 복사를 막는다."""
    top_rgb    = parse_color(features.get("top_color",    "흰색"))
    bottom_rgb = parse_color(features.get("bottom_color", "네이비"))
    shoes_rgb  = parse_color(features.get("shoes_color",  "검정"))
    # 소매 색 (몸통과 다를 경우 — 검정 소매, 장갑, 암워머 등)
    sleeve_raw = features.get("sleeve_color") or features.get("top_color") or "흰색"
    sleeve_rgb = parse_color(sleeve_raw)

    zone_colors = {
        "top":    top_rgb,
        "sleeve": sleeve_rgb,   # 팔 UV에 별도 적용 (_paint_mask 참조)
        "bottom": bottom_rgb,
        "shoes":  shoes_rgb,
        "jacket": top_rgb,
        "acc":    parse_color(features.get("accessories", "") or "검정"),
    }

    mask_path = pick_mask(features)
    mask_arr  = np.array(Image.open(mask_path).convert("RGBA"), dtype=np.uint8)

    if _comps is None:
        _comps = _select_ref_components(features)
    body_ref = _comps["body"]
    arm_ref  = _comps["arm"]
    leg_ref  = _comps["leg"]

    # 치마 여부 + 전용 그림자 맵 결정
    _SKIRT_KWS = {"치마", "스커트", "skirt", "드레스", "dress", "원피스", "롱스커트", "미니스커트"}
    _LONG_SKIRT_KWS = {"롱스커트", "롱 스커트", "long skirt", "맥시", "롱드레스"}
    bot_style_raw = (features.get("bottom_style", "") or "").lower()
    is_skirt = any(k in bot_style_raw for k in _SKIRT_KWS)
    if is_skirt:
        is_long = any(k in bot_style_raw for k in _LONG_SKIRT_KWS)
        skirt_shade_map = _LONG_SKIRT_SHADE if is_long else _SHORT_SKIRT_SHADE
    else:
        skirt_shade_map = None

    # 반바지: 긴바지 레퍼런스를 반바지 높이로 가상 크롭 (허벅지 텍스처만 사용)
    if _bottom_category(bot_style_raw) == "shorts":
        leg_ref = _trim_ref_for_shorts(leg_ref)

    zone_maxv = _zone_stats_split(body_ref, leg_ref, mask_arr, arm_ref)

    # 자켓 마스크(mask_jacket*.png)는 TOP(재킷)+BOT(하의)+SHOE 모두 포함.
    # 재킷 안 셔츠가 보이는 body y=28..32 영역은 BOT 존으로 처리되므로 별도 베이스 불필요.
    # 단, shirt_color가 top_color와 다른 경우 shirt 레이어를 jacket 아래에 깔아 줌.
    if "jacket" in mask_path.name:
        shirt_color_raw = (features.get("shirt_color") or "").strip()
        top_color_raw   = (features.get("top_color")   or "").strip()
        if shirt_color_raw.startswith("#") and shirt_color_raw.lower() != top_color_raw.lower():
            shirt_rgb = parse_color(shirt_color_raw)
            # 셔츠가 별도 색이면 jacket이 안 덮는 y=28..32 몸통 앞면에 셔츠색 선도포
            shirt_zone_colors = {**zone_colors, "top": shirt_rgb, "jacket": shirt_rgb,
                                 "sleeve": shirt_rgb}
            # 긴팔 기본 마스크로 셔츠 색 깔기 (재킷 픽셀은 곧 덮힘)
            base_path = BASESKIN_DIR / "mask_longsleeve.png"
            if base_path.exists():
                base_m = np.array(Image.open(base_path).convert("RGBA"), dtype=np.uint8)
                base_maxv = _zone_stats_split(body_ref, leg_ref, base_m, arm_ref)
                tmp = base_m.copy()
                tmp[mask_arr[:, :, 3] > 10, 3] = 0   # 재킷이 덮는 부분 제거
                _paint_mask(arr, tmp, body_ref, leg_ref, shirt_zone_colors, base_maxv, arm_ref,
                            is_skirt=is_skirt, skirt_shade_map=skirt_shade_map)

    _DENIM_KWS = ["청바지", "청반바지", "데님", "denim", "jean", "jeans"]
    is_denim = any(k in bot_style_raw for k in _DENIM_KWS)

    # 넥 액세서리(넥타이/리본/나비넥타이) 준비 — 자켓이면 자켓 전, 아니면 acc 단계
    _neck_acc_style = (features.get("neck_accessory") or "").strip().lower()
    _neck_acc_color = parse_color(features.get("neck_accessory_color") or "#000000")
    _NECK_ACC_FILES = {
        "넥타이":    "mask_acc_necktie.png",
        "나비넥타이": "mask_acc_bowtie.png",
        "리본":      "mask_acc_ribbon.png",
    }
    _neck_acc_path = None
    for _kw, _fn in _NECK_ACC_FILES.items():
        if _kw in _neck_acc_style:
            _p = BASESKIN_DIR / _fn
            if _p.exists():
                _neck_acc_path = _p
            break

    def _paint_neck_acc():
        if _neck_acc_path is None:
            return
        nacc_arr = np.array(Image.open(_neck_acc_path).convert("RGBA"), dtype=np.uint8)
        neck_zone_colors = {**zone_colors, "acc": _neck_acc_color}
        nacc_maxv = _zone_stats_split(body_ref, leg_ref, nacc_arr, arm_ref)
        _paint_mask(arr, nacc_arr, body_ref, leg_ref, neck_zone_colors, nacc_maxv, arm_ref,
                    is_skirt=is_skirt, skirt_shade_map=skirt_shade_map)

    # 자켓 마스크: 넥타이를 자켓 pass 전에 삽입 (겉옷 아래, 상의 위)
    if "jacket" in mask_path.name:
        _paint_neck_acc()

    _paint_mask(arr, mask_arr, body_ref, leg_ref, zone_colors, zone_maxv, arm_ref,
                is_skirt=is_skirt, skirt_shade_map=skirt_shade_map, is_denim=is_denim)

    # 악세서리 오버레이 적용
    # 벨트는 상의(셔츠/재킷)가 덮는 위치에선 가려지는 게 자연스럽다.
    # 일반 길이 셔츠 → 벨트 안 보임, 크롭탑처럼 짧으면 → 벨트 노출.
    _main_top = _build_zone_masks(mask_arr)
    _cover = _main_top["top"] | _main_top["jacket"]
    for acc_path in pick_acc_overlays(features):
        acc_arr  = np.array(Image.open(acc_path).convert("RGBA"), dtype=np.uint8)
        if "belt" in acc_path.name:
            acc_arr = acc_arr.copy()
            acc_arr[_cover, 3] = 0   # 셔츠가 덮는 벨트 픽셀 제거
        acc_maxv = _zone_stats_split(body_ref, leg_ref, acc_arr, arm_ref)
        _paint_mask(arr, acc_arr, body_ref, leg_ref, zone_colors, acc_maxv, arm_ref,
                    is_skirt=is_skirt, skirt_shade_map=skirt_shade_map)

    # 비자켓 outfit: 넥타이를 상의 위(acc 단계)에 적용
    # _return_neck_painter=True면 호출을 미루고 callable 반환 (뒷면 복사 후 실행용)
    if "jacket" not in mask_path.name:
        if _return_neck_painter:
            return _paint_neck_acc
        _paint_neck_acc()
    return None


def _trim_ref_for_shorts(leg_ref: np.ndarray) -> np.ndarray:
    """긴바지 레퍼런스를 반바지 높이로 가상 크롭.
    다리 하단(y=26..32 / y=58..64)을 투명화 → 상단 절반 텍스처만 사용.
    레퍼런스에 반바지가 없어도 긴바지 허벅지 부분을 반바지처럼 쓸 수 있음."""
    mod = leg_ref.copy()
    mod[26:32, 0:16, 3] = 0    # 오른다리 레이어1 하단 제거
    mod[58:64, 16:32, 3] = 0   # 왼다리 레이어1 하단 제거
    return mod


def _fill_back_faces(arr: np.ndarray):
    """앞면 패턴을 좌우반전+어둡게 다른 면에 복사.
    팔(뒤/내측/외측)은 force=True → 무조건 앞면 복사 (단색 버그 근본 차단).
    몸통·다리 뒷면은 force=False → 단색(std<22)일 때만 복사 (정상 텍스처 보존)."""
    # (앞면 x,y,w,h), (대상면 x,y,w,h), 어둡기 배율, 강제복사 여부
    PAIRS = [
        ((20, 20, 8, 12), (32, 20, 8, 12), 0.68, False),  # 몸통 앞→뒤
        ((44, 20, 4, 12), (52, 20, 4, 12), 0.72, True),   # 오른팔 앞→뒤
        ((44, 20, 4, 12), (40, 20, 4, 12), 0.85, True),   # 오른팔 앞→내측
        ((44, 20, 4, 12), (48, 20, 4, 12), 0.85, True),   # 오른팔 앞→외측
        ((36, 52, 4, 12), (44, 52, 4, 12), 0.72, True),   # 왼팔  앞→뒤
        ((36, 52, 4, 12), (32, 52, 4, 12), 0.85, True),   # 왼팔  앞→내측
        ((36, 52, 4, 12), (40, 52, 4, 12), 0.85, True),   # 왼팔  앞→외측
        (( 4, 20, 4, 12), (12, 20, 4, 12), 0.72, False),  # 오른다리 앞→뒤
        ((20, 52, 4, 12), (28, 52, 4, 12), 0.72, False),  # 왼다리  앞→뒤
    ]
    for (fx, fy, fw, fh), (bx, by, bw, bh), shade, force in PAIRS:
        back = arr[by:by+bh, bx:bx+bw, :]
        valid_back = back[:, :, 3] > 10
        if not valid_back.any():
            continue
        if not force:
            back_rgb = back[:, :, :3].astype(float)
            spatial_std = float(max(
                back_rgb[:, :, 0][valid_back].std(),
                back_rgb[:, :, 1][valid_back].std(),
                back_rgb[:, :, 2][valid_back].std(),
            ))
            if spatial_std >= 22:
                continue  # 충분한 텍스처 있음 → 보존
        # 앞면 좌우반전 + shade 적용
        front = arr[fy:fy+fh, fx:fx+fw, :].copy()
        front_flip = front[:, ::-1, :]
        rgb = np.clip(front_flip[:, :, :3].astype(float) * shade, 0, 255).astype(np.uint8)
        valid_front = front_flip[:, :, 3] > 10
        arr[by:by+bh, bx:bx+bw][valid_front, :3] = rgb[valid_front]
        arr[by:by+bh, bx:bx+bw][valid_front, 3] = 255


def _mirror_clothing_to_layer2(arr: np.ndarray):
    """밑단·소맷단·칼라만 Layer2에 복사 — 팔·다리·바디 전체 복사 없음"""

    # Layer2 의상 영역 전체 투명화
    for dy, dx, h, w in [
        (32, 16, 16, 24),  # 몸통
        (32, 40, 16, 16),  # 오른팔
        (48, 48, 16, 16),  # 왼팔
        (32,  0, 16, 16),  # 오른다리
        (48,  0, 16, 16),  # 왼다리
    ]:
        arr[dy:dy+h, dx:dx+w, 3] = 0

    # (src_y, src_x, dst_y, dst_x, strip_h, w) — 엣지 스트립만 복사
    EDGE_STRIPS = [
        # ── 몸통 밑단 (hem) ── y=30..32 → layer2 y=46..48
        (30, 20, 46, 20, 2, 8),   # 앞면
        (30, 16, 46, 16, 2, 4),   # 오른면
        (30, 28, 46, 28, 2, 4),   # 왼면
        (30, 32, 46, 32, 2, 8),   # 뒷면
        # ── 몸통 칼라 (collar) ── y=20..21
        (20, 20, 36, 20, 1, 8),   # 앞면 상단
        # ── 오른팔 소맷단 (cuff) ── y=30..32 → layer2 y=46..48
        (30, 44, 46, 44, 2, 4),   # 앞면
        (30, 40, 46, 40, 2, 4),   # 오른면
        (30, 48, 46, 48, 2, 4),   # 왼면
        # ── 왼팔 소맷단 ── src y=62..64, x 범위; dst x+16
        (62, 36, 62, 52, 2, 4),   # 앞면
        (62, 32, 62, 48, 2, 4),   # 왼면
        (62, 40, 62, 56, 2, 4),   # 오른면
        # ── 오른다리 밑단 ── y=30..32 → layer2 y=46..48
        (30,  4, 46,  4, 2, 4),   # 앞면
        (30,  0, 46,  0, 2, 4),   # 오른면
        (30,  8, 46,  8, 2, 4),   # 왼면
        # ── 왼다리 밑단 ── src y=62..64; dst x-16
        (62, 20, 62,  4, 2, 4),   # 앞면
        (62, 16, 62,  0, 2, 4),   # 왼면
        (62, 24, 62,  8, 2, 4),   # 오른면
    ]

    for sy, sx, dy, dx, h, w in EDGE_STRIPS:
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
    "장발_생머리":      ["base_hair_long_wave.png"],     # 생머리도 웨이브가 더 자연스러움
    "장발_웨이브":      ["base_hair_long_wave.png"],
    "중장발_생머리":    ["base_hair_mid_wave.png"],      # 동일
    "중장발_웨이브":    ["base_hair_mid_wave.png"],
    "꽁지머리":         ["base_hair_ponytail.png"],
    "짧은꽁지":         ["base_hair_short_ponytail.png"],
    "사이드테일":       ["base_hair_sidetail.png"],
    "양갈래_생머리":    ["base_hair_twin_straight_back.png", "base_hair_twin_straight_front.png"],
    "양갈래_웨이브":    ["base_hair_twin_wave_back.png",     "base_hair_twin_wave_front.png"],
    "짧은양갈래_생머리":["base_hair_twin_straight_short_back.png", "base_hair_twin_straight_short_front.png"],
    "짧은양갈래_웨이브":["base_hair_twin_wave_short_back.png",     "base_hair_twin_wave_front.png"],
    "단발": None,
    "숏컷": None,   # 남성 짧은머리 — 몸통 연장 없음
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


def recolor_hair_base(hair_arr: np.ndarray, target_rgb: tuple,
                      v_floor: float = 0.0) -> np.ndarray:
    """numpy 벡터화: 헤어 베이스 V값으로 타겟 색상 밝기 스케일.
    v_floor: 명암 하한 (0=원본, 0.38=앞머리 권장). [v_floor, 1]로 압축해 그림자 완화."""
    valid = hair_arr[:, :, 3] > 10
    v_map = _np_rgb2v(hair_arr[:, :, :3])
    max_v = float(v_map[valid].max()) if valid.any() else 1.0
    if max_v < 0.01:
        max_v = 1.0

    norm_v = np.clip(v_map / max_v, 0.0, 1.0)
    if v_floor > 0.0:
        norm_v = v_floor + (1.0 - v_floor) * norm_v
    brightness = np.clip(norm_v * BRIGHTNESS_BOOST, 0.0, 1.0)
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


def _load_del_mask() -> tuple:
    """del.png의 마젠타 픽셀 좌표 (layer2 face 기준) 로드."""
    p = BASESKIN_DIR / "del.png"
    if not p.exists():
        return np.array([], dtype=int), np.array([], dtype=int)
    img = np.array(Image.open(p).convert("RGBA"), dtype=np.uint8)
    mask = (img[:,:,0] > 200) & (img[:,:,1] < 40) & (img[:,:,2] > 200) & (img[:,:,3] > 10)
    return np.where(mask)

_DEL_YS, _DEL_XS = _load_del_mask()


def _stamp_eyes_last(arr: np.ndarray, skin_base: np.ndarray) -> None:
    """del.png 마젠타 픽셀 위치(layer2 face)만 투명화 + 대응 layer1 복원.
    layer2 x=40..47 → layer1 x=8..15 (offset -32)."""
    if len(_DEL_YS) == 0:
        return
    arr[_DEL_YS, _DEL_XS]        = 0                               # layer2 투명화
    arr[_DEL_YS, _DEL_XS - 32]   = skin_base[_DEL_YS, _DEL_XS - 32]  # layer1 복원


# 목선 파임 픽셀 좌표 (body front UV: x=20..28, y=20..32)
_NECKLINE_PIXELS = {
    "브이넥":   [(20, 23), (20, 24), (21, 22), (21, 25), (22, 22), (22, 25)],
    "스퀘어넥": [(20, 22), (20, 23), (20, 24), (20, 25), (21, 22), (21, 25)],
    "홀터넥":   [(20, 22), (20, 23), (20, 24), (20, 25)],
    "라운드넥": [(20, 23), (20, 24)],
}

def _apply_neckline(arr: np.ndarray, skin_base: np.ndarray, neck_style: str):
    """목선 파임 — 몸통 앞면 상단 중앙에 베이스 스킨 복원"""
    pixels = _NECKLINE_PIXELS.get((neck_style or "").strip(), [])
    for (y, x) in pixels:
        arr[y, x] = skin_base[y, x]


_BANGS_V_FLOOR = 0.38  # 앞머리 명암 하한 — 그림자가 너무 진하지 않도록

def draw_hair_bangs_only(arr: np.ndarray, hair_rgb: tuple, hair_bangs: str):
    """앞머리(뱅) 레이어만 합성 (머리카락 최상단)"""
    bangs_name = HAIR_BANGS_MAP.get((hair_bangs or "").strip(), HAIR_BANGS_FALLBACK)
    p = BASESKIN_DIR / bangs_name
    if p.exists():
        base_arr = np.array(Image.open(p).convert("RGBA"), dtype=np.uint8)
        colored = recolor_hair_base(base_arr, hair_rgb, v_floor=_BANGS_V_FLOOR)
        _composite_layer(arr, colored)


def draw_hair(arr: np.ndarray, hair_rgb: tuple, hair_style: str, hair_bangs: str = ""):
    """뱅(머리) + 몸통 연장 레이어 순서대로 재채색 후 합성"""
    for base_arr in load_hair_base(hair_style, hair_bangs):
        colored = recolor_hair_base(base_arr, hair_rgb)
        _composite_layer(arr, colored)


def draw_hair_from_ref(arr: np.ndarray, head_comp: np.ndarray,
                       hair_rgb: tuple, skin_base: np.ndarray,
                       hair_style: str = ""):
    """레퍼런스 헤드 컴포넌트를 이용한 고품질 머리카락 렌더링.

    head_comp : mine_assets.py로 추출한 ref{N}_head.png (64×64 RGBA)
    hair_rgb  : 목표 머리카락 RGB
    skin_base : 피부톤 적용 직후 arr 복사본 (피부 픽셀 복원용)
    hair_style: 헤어 스타일 (숏컷이면 레퍼런스 텍스처 패턴 무시)
    """
    if head_comp is None:
        return

    # 헤드 UV 영역: y=0..16, x=0..32
    comp  = head_comp[0:16, 0:32, :]   # (16, 32, 4)
    valid = comp[:, :, 3] > 10

    if not valid.any():
        return

    # ── 레퍼런스 피부톤 추정: 얼굴 앞면 (y=8..16, x=8..16) 밝은 픽셀 평균
    face  = comp[8:16, 8:16, :]
    fv    = face[:, :, 3] > 10
    if fv.any():
        fp    = face[fv, :3].astype(float)
        brt   = fp.mean(axis=1)
        bmask = brt > brt.mean()
        ref_skin = fp[bmask].mean(axis=0) if bmask.any() else fp.mean(axis=0)
    else:
        ref_skin = np.array([180.0, 140.0, 110.0])  # 기본 피부색 추정

    # ── 각 픽셀 → 피부 or 헤어 분류 (벡터화)
    rgb_f = comp[:, :, :3].astype(float)          # (16,32,3)
    diff  = rgb_f - ref_skin[np.newaxis, np.newaxis, :]
    dist  = np.sqrt((diff ** 2).sum(axis=-1))     # (16,32)

    # ref_skin 밝기 기준으로 임계값 동적 조정 (밝은 피부→좀 더 관대하게)
    skin_brightness = float(ref_skin.mean())
    skin_thresh = max(35.0, skin_brightness * 0.30)

    # 얼굴 앞면(y=8..16, x=8..16)은 피부·눈 혼재 → 강제 피부 처리
    face_mask = np.zeros((16, 32), dtype=bool)
    face_mask[8:16, 8:16] = True

    is_skin = valid & ((dist < skin_thresh) | face_mask)
    is_hair = valid & (dist >= skin_thresh) & ~face_mask

    # ── 피부 픽셀 → 베이스 피부톤 복원
    ys_s, xs_s = np.where(is_skin)
    if len(ys_s) > 0:
        arr[ys_s, xs_s, :] = skin_base[ys_s, xs_s, :]

    # ── 헤어 픽셀 → HSV 방식 재채색 (면별 명암 + 색조·채도 교체)
    if is_hair.any():
        # UV 면별 위치 명암
        _HEAD_FACE_SHADE = np.ones((16, 32), dtype=np.float32)
        _HEAD_FACE_SHADE[0:8,  8:16] = 0.88   # 머리 윗면
        _HEAD_FACE_SHADE[8:16, 0:8]  = 0.78   # 오른 옆면
        _HEAD_FACE_SHADE[8:16, 16:24]= 0.78   # 왼 옆면
        _HEAD_FACE_SHADE[8:16, 24:32]= 0.62   # 뒷면

        _is_short = (hair_style or "").strip() in ("숏컷", "단발")
        if _is_short:
            # 숏컷/단발: 레퍼런스 텍스처 패턴 무시 → 면 셰이드만으로 flat 칠
            # 긴 머리 레퍼런스의 웨이브·층·패턴이 블리드스루되는 현상 방지
            v_base = _HEAD_FACE_SHADE
        else:
            gray   = (rgb_f[:,:,0]*0.299 + rgb_f[:,:,1]*0.587 + rgb_f[:,:,2]*0.114)
            max_gray = float(gray[is_hair].max())
            v_base = np.clip(gray / max(max_gray, 1.0), 0.0, 1.0) * _HEAD_FACE_SHADE

        # HSV 방식: 타겟 H, S 유지하며 V만 스케일
        tr_f, tg_f, tb_f = hair_rgb[0]/255.0, hair_rgb[1]/255.0, hair_rgb[2]/255.0
        t_h, t_s, t_v = rgb_to_hsv(tr_f, tg_f, tb_f)
        rgb_out = _np_hsv_recolor(arr[:, :, :3], arr[:, :, 3],
                                  t_h, t_s, v_base, 1.0, max(t_v, 0.20))

        ys_h, xs_h = np.where(is_hair)
        arr[ys_h, xs_h, :3] = rgb_out[ys_h, xs_h]
        arr[ys_h, xs_h, 3]  = 255


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
    "금발": (252, 239, 171), "금색": (252, 239, 171), "블론드": (252, 239, 171),
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
    # hex 코드 우선 파싱 (#rrggbb 또는 #rgb)
    import re
    m = re.search(r'#([0-9a-fA-F]{6})', text)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    m3 = re.search(r'#([0-9a-fA-F]{3})\b', text)
    if m3:
        h = m3.group(1)
        return (int(h[0]*2, 16), int(h[1]*2, 16), int(h[2]*2, 16))
    # 폴백: 한국어 색상명 매핑
    for key, rgb in COLOR_MAP.items():
        if key in text:
            return rgb
    return DEFAULT_COLOR

def _shade_tuple(rgb: tuple, f: float) -> tuple:
    return tuple(max(0, min(255, int(c * f))) for c in rgb)


# ── 메인 ─────────────────────────────────────────────────────────
# ── 눈 형태 매핑 ─────────────────────────────────────────────────
EYE_SHAPE_MAP = {
    "큰눈":     "base_eyes (1).png",
    "둥근눈":   "base_eyes (2).png",
    "일반":     "base_eyes (3).png",   # 기본값 (동양인 실사)
    "아몬드눈": "base_eyes (4).png",
    "반쌍꺼풀": "base_eyes (5).png",
    "가는눈":   "base_eyes (6).png",
    "좁은눈":   "base_eyes (7).png",
    "작은눈":   "base_eyes (8).png",
}
EYE_FALLBACK = "base_eyes (3).png"


_EYE_BOOST_FILE  = "base_eyes (4).png"   # 여성 기본 부스트 (아몬드눈)
_EYE_MALE_FILE   = "base_eyes (8).png"   # 남성 기본 (작은눈)
_EYE_ELDER_FILE  = "base_eyes (7).png"   # 노인 (좁은눈)
_EYE_BOOST_PROB  = 0.75

def draw_eyes(arr: np.ndarray, eye_shape: str, eye_rgb: tuple,
              gender: str = "중성적", age_group: str = "성인",
              shift_up: int = 0):
    """눈 형태 적용 + 홍채 색상 재채색 (성별·나이별 눈 선택)
    shift_up: 눈 위치를 위로 올릴 픽셀 수 (대머리 시 1).
    반환: 이동 후 비워진 (orphaned_ys, orphaned_xs) — 호출자가 피부색으로 복원."""
    import random
    fname = EYE_SHAPE_MAP.get((eye_shape or "").strip(), EYE_FALLBACK)

    if (age_group or "").strip() == "노인":
        fname = _EYE_ELDER_FILE
    elif (gender or "").strip() == "남성적":
        if fname != _EYE_MALE_FILE and random.random() < _EYE_BOOST_PROB:
            fname = _EYE_MALE_FILE
    elif (gender or "").strip() == "여성적":
        if fname != _EYE_BOOST_FILE and random.random() < _EYE_BOOST_PROB:
            fname = _EYE_BOOST_FILE
    p = BASESKIN_DIR / fname
    if not p.exists():
        p = BASESKIN_DIR / EYE_FALLBACK
    base = np.array(Image.open(p).convert("RGBA"), dtype=np.uint8)
    er, eg, eb = eye_rgb
    result = base.copy()
    valid = base[:, :, 3] > 10
    ys, xs = np.where(valid)
    for y, x in zip(ys, xs):
        r, g, b = int(base[y, x, 0]), int(base[y, x, 1]), int(base[y, x, 2])
        gray = int(r * 0.299 + g * 0.587 + b * 0.114)
        # 홍조 픽셀(핑크/살구빛) → 투명 처리
        if r > 150 and (r - g) > 18 and (r - b) > 15 and gray > 60:
            result[y, x, 3] = 0
            continue
        # 홍채 범위 (윤곽·하이라이트 제외)
        if 15 < gray < 160:
            factor = max(0.3, gray / 80.0)
            result[y, x, 0] = min(255, int(er * factor))
            result[y, x, 1] = min(255, int(eg * factor))
            result[y, x, 2] = min(255, int(eb * factor))

    if shift_up > 0:
        original_mask = result[:, :, 3] > 10
        shifted = np.zeros_like(result)
        shifted[:64 - shift_up, :] = result[shift_up:, :]
        result = shifted
        orphaned_ys, orphaned_xs = np.where(original_mask & (result[:, :, 3] == 0))
    else:
        orphaned_ys = orphaned_xs = np.array([], dtype=int)

    _composite_layer(arr, result)
    return orphaned_ys, orphaned_xs


def draw_muscle(arr: np.ndarray):
    """근육 음영 오버레이 (회색값 → 피부 위 multiply 어둡게)"""
    p = BASESKIN_DIR / "base_muscle.png"
    if not p.exists():
        return
    muscle = np.array(Image.open(p).convert("RGBA"), dtype=np.uint8)
    valid = muscle[:, :, 3] > 10
    ys, xs = np.where(valid)
    for y, x in zip(ys, xs):
        if arr[y, x, 3] < 10:
            continue
        factor = muscle[y, x, 0] / 255.0
        arr[y, x, 0] = min(255, int(arr[y, x, 0] * factor))
        arr[y, x, 1] = min(255, int(arr[y, x, 1] * factor))
        arr[y, x, 2] = min(255, int(arr[y, x, 2] * factor))


VALID_TONES = {
    "warm_bright", "warm_normal", "warm_dark",
    "cool_bright", "cool_normal", "cool_dark",
    "warm_dark_dark", "cool_dark_dark",
    "cool_dark_dark_dark", "cool_dark_dark_dark_dark",
    "pale", "warm_deeper", "cool_deeper", "dark", "very_dark",
}


def generate_skin(features: dict) -> Image.Image:
    tone_key = features.get("skin_tone", "warm_bright")
    if tone_key not in VALID_TONES:
        tone_key = "warm_bright"

    arr = np.array(apply_skin_tone(load_base(tone_key), tone_key), dtype=np.uint8).copy()

    hair_rgb    = parse_color(features.get("hair_color", "검정"))
    hair_style  = features.get("hair_style", "")
    hair_bangs  = features.get("hair_bangs", "")
    eye_rgb     = parse_color(features.get("eye_color") or "#2c2c2c")
    eye_shape   = features.get("eye_shape", "일반")
    body_type   = (features.get("body_type") or "normal").lower()
    gender      = (features.get("gender_expression") or "중성적").strip()
    age_group   = (features.get("age_group") or "성인").strip()
    is_bald     = str(features.get("is_bald", "false")).lower() in ("true", "1", "yes")
    neck_style  = (features.get("neck_style") or "").strip()

    # 1. 근육 오버레이 (피부 위, 의상 아래)
    if body_type in ("athletic", "muscular"):
        draw_muscle(arr)

    # 2. 눈 (피부 위, 성별·나이 반영 / 대머리면 1픽셀 위로)
    # pre_eyes: 눈 그리기 전 상태 — shift_up 시 잔여 픽셀 복원용
    pre_eyes = arr.copy() if is_bald else None
    orphaned_ys, orphaned_xs = draw_eyes(
        arr, eye_shape, eye_rgb, gender=gender, age_group=age_group,
        shift_up=1 if is_bald else 0)
    # 대머리 눈 shift: 비워진 맨 아래 행을 피부색으로 복원
    if is_bald and len(orphaned_ys) > 0:
        arr[orphaned_ys, orphaned_xs] = pre_eyes[orphaned_ys, orphaned_xs]

    # 눈 적용 후 백업 — draw_hair_from_ref가 face 복원 시 눈 픽셀도 보존됨
    skin_base = arr.copy()

    # 3. 레퍼런스 컴포넌트 선택 (body/arm/leg/head_comp)
    comps = _select_ref_components(features)

    # 4. 의상 (비재킷 넥타이는 뒷면 복사 후 칠하도록 deferred)
    _neck_painter = apply_mask_clothing(arr, features, _comps=comps,
                                        _return_neck_painter=True)

    # 4-1. 뒷면 텍스처 보강 (목파임 전에 실행 — 앞면 복사 시 목파임 픽셀 미포함)
    _fill_back_faces(arr)

    # 4-1a. 넥타이/리본: 뒷면 복사 완료 후 앞면에만 칠함 → 뒷면에 넥타이 전파 방지
    if _neck_painter is not None:
        _neck_painter()

    # 4-2. 목선 파임 (뒷면 복사 후 앞면만 처리 → 뒷면에 목파임 전파 방지)
    if neck_style in _NECKLINE_PIXELS:
        _apply_neckline(arr, skin_base, neck_style)

    # 5. 머리카락 (대머리면 모든 헤어 레이어 스킵)
    if not is_bald:
        head_comp = comps.get("head_comp")
        if head_comp is not None:
            draw_hair_from_ref(arr, head_comp, hair_rgb, skin_base, hair_style)
        draw_hair_body_only(arr, hair_rgb, hair_style)
        draw_hair_bangs_only(arr, hair_rgb, hair_bangs)

    # 눈/눈썹: 모든 헤어 완료 후 마지막으로 layer2 face에 stamp (항상 최상위 렌더링)
    _stamp_eyes_last(arr, skin_base)

    _mirror_clothing_to_layer2(arr)   # 6. 레이어2 엣지 복사

    if features.get("glasses", False):
        draw_glasses(arr)

    return Image.fromarray(arr, "RGBA")


# ── 사진 직접 매핑 ────────────────────────────────────────────────

def generate_skin_from_photo(photo: Image.Image, features: dict) -> Image.Image:
    """사진 픽셀을 직접 UV 위치에 매핑하여 스킨 생성"""
    tone_key = features.get("skin_tone", "warm_bright")
    if tone_key not in VALID_TONES:
        tone_key = "warm_bright"
    arr = np.array(apply_skin_tone(load_base(tone_key), tone_key), dtype=np.uint8).copy()

    # 사진을 RGBA로 변환, 세로가 긴 형태 보정
    img = photo.convert("RGBA")
    W, H = img.size
    # 너무 가로가 넓으면 중앙 크롭
    if W > H * 0.7:
        cx = W // 2
        half = int(H * 0.35)
        img = img.crop((cx - half, 0, cx + half, H))
        W, H = img.size

    img_np = np.array(img, dtype=np.uint8)

    def paste_region(dst_x, dst_y, dst_w, dst_h,
                     src_x_frac, src_y_frac, src_w_frac, src_h_frac,
                     darken=1.0):
        """사진의 비율 좌표 영역을 UV 위치에 리샘플링"""
        sx = int(W * src_x_frac)
        sy = int(H * src_y_frac)
        sw = max(1, int(W * src_w_frac))
        sh = max(1, int(H * src_h_frac))
        crop = img.crop((sx, sy, sx + sw, sy + sh))
        resized = crop.resize((dst_w, dst_h), Image.LANCZOS)
        patch = np.array(resized, dtype=np.uint8)
        if darken != 1.0:
            patch[:, :, :3] = np.clip(patch[:, :, :3] * darken, 0, 255).astype(np.uint8)
        arr[dst_y:dst_y+dst_h, dst_x:dst_x+dst_w] = patch

    cx_f = 0.5   # 사진 중앙 x 비율

    # ── 머리 ─────────────────────────────────────
    # 앞면 (8,8,8,8)
    paste_region(8, 8, 8, 8,   cx_f-0.15, 0.03, 0.30, 0.17)
    # 뒷면 (24,8,8,8)
    paste_region(24, 8, 8, 8,  cx_f-0.15, 0.03, 0.30, 0.17, darken=0.75)
    # 오른면 (0,8,4,8) / 왼면 (16,8,4,8)
    paste_region(0,  8, 4, 8,  cx_f-0.15, 0.03, 0.10, 0.17, darken=0.85)
    paste_region(16, 8, 4, 8,  cx_f+0.05, 0.03, 0.10, 0.17, darken=0.85)
    # 윗면 (8,0,8,8) — 머리 색으로 채움
    paste_region(8,  0, 8, 8,  cx_f-0.15, 0.03, 0.30, 0.10)

    # ── 몸통 ─────────────────────────────────────
    # 앞면 (20,20,8,12)
    paste_region(20, 20, 8, 12,  cx_f-0.22, 0.20, 0.44, 0.32)
    # 뒷면 (32,20,8,12)
    paste_region(32, 20, 8, 12,  cx_f-0.22, 0.20, 0.44, 0.32, darken=0.72)
    # 오른면 (16,20,4,12)
    paste_region(16, 20, 4, 12,  cx_f-0.22, 0.20, 0.12, 0.32, darken=0.80)
    # 왼면 (28,20,4,12)
    paste_region(28, 20, 4, 12,  cx_f+0.10, 0.20, 0.12, 0.32, darken=0.80)

    # ── 오른팔 ────────────────────────────────────
    # 앞면 (44,20,4,12)
    paste_region(44, 20, 4, 12,  cx_f-0.44, 0.20, 0.15, 0.32)
    # 뒷면 (52,20,4,12)
    paste_region(52, 20, 4, 12,  cx_f-0.44, 0.20, 0.15, 0.32, darken=0.72)
    # 옆면 (40,20,4,12)
    paste_region(40, 20, 4, 12,  cx_f-0.44, 0.20, 0.08, 0.32, darken=0.82)

    # ── 왼팔 (새 포맷 y=48~64 영역) ──────────────
    # 앞면 (36,52,4,12)
    paste_region(36, 52, 4, 12,  cx_f+0.29, 0.20, 0.15, 0.32)
    # 뒷면 (44,52,4,12)
    paste_region(44, 52, 4, 12,  cx_f+0.29, 0.20, 0.15, 0.32, darken=0.72)
    # 옆면 (32,52,4,12)
    paste_region(32, 52, 4, 12,  cx_f+0.29, 0.20, 0.08, 0.32, darken=0.82)

    # ── 오른다리 ──────────────────────────────────
    # 앞면 (4,20,4,12)
    paste_region(4,  20, 4, 12,  cx_f-0.22, 0.52, 0.18, 0.35)
    # 뒷면 (12,20,4,12)
    paste_region(12, 20, 4, 12,  cx_f-0.22, 0.52, 0.18, 0.35, darken=0.72)
    # 옆면 (0,20,4,12)
    paste_region(0,  20, 4, 12,  cx_f-0.22, 0.52, 0.08, 0.35, darken=0.82)

    # ── 왼다리 (새 포맷 y=48~64 영역) ────────────
    # 앞면 (20,52,4,12)
    paste_region(20, 52, 4, 12,  cx_f+0.04, 0.52, 0.18, 0.35)
    # 뒷면 (28,52,4,12)
    paste_region(28, 52, 4, 12,  cx_f+0.04, 0.52, 0.18, 0.35, darken=0.72)
    # 옆면 (16,52,4,12)
    paste_region(16, 52, 4, 12,  cx_f+0.04, 0.52, 0.08, 0.35, darken=0.82)

    # 머리카락 · 앞머리는 기존 방식 유지 (photo 색 위에 덮기)
    hair_rgb   = parse_color(features.get("hair_color", "검정"))
    hair_style = features.get("hair_style", "")
    hair_bangs = features.get("hair_bangs", "")
    is_bald    = str(features.get("is_bald", "false")).lower() in ("true", "1", "yes")
    skin_base_photo = arr.copy()
    if not is_bald:
        draw_hair_body_only(arr, hair_rgb, hair_style)
        draw_hair_bangs_only(arr, hair_rgb, hair_bangs)
    _stamp_eyes_last(arr, skin_base_photo)
    _mirror_clothing_to_layer2(arr)

    if features.get("glasses", False):
        draw_glasses(arr)

    return Image.fromarray(arr, "RGBA")
