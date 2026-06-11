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
                    t_v: float) -> np.ndarray:
    """ref_v 밝기를 유지하며 HSV 색조를 (t_h, t_s)로 교체. (H,W,3) uint8 반환"""
    norm_v = np.clip(ref_v / max(max_v, 0.01), 0.0, 1.0)
    final_v = np.clip(norm_v * max(t_v, 0.15) * BRIGHTNESS_BOOST, 0.0, 1.0)

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
# (top 키워드, bottom 키워드, 파일명) — 위에 있을수록 우선
# top/bot 키워드 모두 비어있으면 무조건 매칭 (폴백 역할)
MASK_STYLE_MAP = [
    # 자켓/코트/카디건/아우터 (반바지 조합 먼저)
    (["자켓","jacket","코트","블레이저","카디건","가디건","cardigan","니트","스웨터","집업","점퍼","후드집업"],
     ["반바지","shorts","쇼츠","핫팬츠","bermuda","짧은 바지","짧은바지","short pants"],  "mask_jacket.png"),
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
    (["한복", "저고리", "치마저고리"],                      [],   "reference (62).png"),
    (["경찰", "police", "군복", "유니폼", "제복"],          [],   "reference (5).png"),
    (["웨딩", "웨딩드레스", "wedding"],                     [],   "reference (33).png"),
    (["수영복", "비키니", "swimsuit"],                       [],   "reference (35).png"),
    (["스포츠", "운동복", "트레이닝", "sport", "gym"],      [],   "reference (66).png"),
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

    gender_map = {"여성적": "여성", "남성적": "남성", "중성적": "중성"}
    if gender_map.get(gender_exp) == ref_gender:
        score += 5.0

    top_rgb = parse_color(features.get("top_color") or "#888888")
    ref_top_rgb = _hex_to_rgb(tag.get("top_color") or "#888888")
    t = np.array(top_rgb, dtype=np.float32)
    color_dist = float(np.sum((ref_top_rgb - t) ** 2))
    score += max(0.0, 10.0 - color_dist / 3000.0)
    return score


_SHORTS_SYNONYMS = {
    "반바지","쇼츠","shorts","핫팬츠","bermuda","짧은바지","short pants",
    "hot pants","cutoff","denim shorts","데님 쇼츠","cargo short",
    "5부 바지","7부 바지","5부","반팬츠","체크 쇼츠","짧은 팬츠",
    "short","ショーツ",
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

    gender_map = {"여성적": "여성", "남성적": "남성", "중성적": "중성"}
    if gender_map.get(gender_exp) == ref_gender:
        score += 5.0

    bot_rgb = parse_color(features.get("bottom_color") or "#888888")
    ref_bot_rgb = _hex_to_rgb(tag.get("bottom_color") or "#888888")
    b = np.array(bot_rgb, dtype=np.float32)
    color_dist = float(np.sum((ref_bot_rgb - b) ** 2))
    score += max(0.0, 10.0 - color_dist / 3000.0)
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


def _load_ref(fname: str) -> np.ndarray:
    if fname not in _REF_SKIN_CACHE:
        path = BASESKIN_DIR / fname
        if not path.exists():
            path = BASESKIN_DIR / _REF_FALLBACK
        _REF_SKIN_CACHE[fname] = np.array(Image.open(path).convert("RGBA"), dtype=np.uint8)
    return _REF_SKIN_CACHE[fname]


def _select_ref_components(features: dict) -> dict:
    """
    4-way 레퍼런스 + 헤드 컴포넌트 선택.
    반환: {"body": arr, "arm": arr, "leg": arr, "head_comp": arr|None}
    """
    top_style = (features.get("top_style", "") or "").lower()
    bot_style = (features.get("bottom_style", "") or "").lower()

    # 특수 스타일: 상하의 동일 레퍼런스 강제
    for top_kws, bot_kws, fname in _STYLE_REF_MAP:
        top_ok = (not top_kws) or any(k in top_style for k in top_kws)
        bot_ok = (not bot_kws) or any(k in bot_style for k in bot_kws)
        if top_ok and bot_ok and (BASESKIN_DIR / fname).exists():
            arr = _load_ref(fname)
            print(f"[ref_select] special → {fname} (all zones)")
            return {"body": arr, "arm": arr, "leg": arr, "head_comp": None}

    all_refs = sorted(BASESKIN_DIR.glob("reference (*).png"))

    best_body = (_REF_FALLBACK, -1.0)
    best_arm  = (_REF_FALLBACK, -1.0)
    best_leg  = (_REF_FALLBACK, -1.0)
    best_hair = (None, -1.0)

    for p in all_refs:
        fname = p.name
        t_score = _score_ref_top(fname, features)
        a_score = _score_ref_arm(fname, features)
        b_score = _score_ref_bot(fname, features)

        if t_score > best_body[1]: best_body = (fname, t_score)
        if a_score > best_arm[1]:  best_arm  = (fname, a_score)
        if b_score > best_leg[1]:  best_leg  = (fname, b_score)

        if _COMP_INDEX:
            m = re.search(r'reference \((\d+)\)', fname)
            if m:
                ref_num = m.group(1)
                h_score = _score_ref_hair(ref_num, features)
                if h_score > best_hair[1]:
                    best_hair = (ref_num, h_score)

    print(f"[ref_select] body={best_body[0]}({best_body[1]:.1f}) "
          f"arm={best_arm[0]}({best_arm[1]:.1f}) "
          f"leg={best_leg[0]}({best_leg[1]:.1f}) "
          f"hair_ref={best_hair[0]}")

    head_comp = None
    if _COMP_INDEX and best_hair[0]:
        head_comp = _load_component(best_hair[0], "head")

    return {
        "body":      _load_ref(best_body[0]),
        "arm":       _load_ref(best_arm[0]),
        "leg":       _load_ref(best_leg[0]),
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
            combined = zmask & bot_valid
            rv = bot_v
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


def _paint_mask(arr, mask_arr, body_ref, bot_ref, zone_colors, zone_maxv,
                arm_ref=None):
    """존별로 다른 레퍼런스 텍스처를 사용해 HSV 색조 변환 적용.
    팔 UV 영역은 arm_ref, 몸통은 body_ref, 다리/신발은 bot_ref 사용."""
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

        has_ref = zmask_sub & ref_valid
        no_ref  = zmask_sub & ~ref_valid

        if has_ref.any():
            rgb_out = _np_hsv_recolor(arr[:, :, :3], arr[:, :, 3],
                                      t_h, t_s, ref_v_map, mv, t_v)
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
            _paint_zone_pixels(zmask, bot_v, bot_valid, target_rgb, mv)
        elif zone in _TOP_ZONES:
            # 팔 UV: sleeve 색이 별도로 있으면 그것 사용, 없으면 target_rgb
            sleeve_rgb = zone_colors.get("sleeve", target_rgb)
            _paint_zone_pixels(zmask & _ARM_UV_MASK,  arm_v,  arm_valid,  sleeve_rgb, mv)
            _paint_zone_pixels(zmask & ~_ARM_UV_MASK, body_v, body_valid, target_rgb, mv)
        else:
            _paint_zone_pixels(zmask, body_v, body_valid, target_rgb, mv)


def apply_mask_clothing(arr: np.ndarray, features: dict,
                        _comps: dict = None):
    """스타일별 레퍼런스 스킨 텍스처 + HSV 색조 변환으로 의상 적용.
    _comps: _select_ref_components() 결과를 외부에서 전달 (캐싱용)"""
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

    # 반바지: 긴바지 레퍼런스를 반바지 높이로 가상 크롭 (허벅지 텍스처만 사용)
    bot_style_raw = (features.get("bottom_style", "") or "").lower()
    if _bottom_category(bot_style_raw) == "shorts":
        leg_ref = _trim_ref_for_shorts(leg_ref)

    zone_maxv = _zone_stats_split(body_ref, leg_ref, mask_arr, arm_ref)

    # 자켓 스타일: 하의에 맞는 베이스 마스크를 먼저 깔고 jacket 오버레이 덮기
    if "jacket" in mask_path.name:
        bot = (features.get("bottom_style", "") or "").lower()
        if any(k in bot for k in _SHORTS_SYNONYMS | {"짧은 바지","short pant"}):
            base_mask_name = "mask_longsleeve_shorts.png"
        elif any(k in bot for k in ["롱스커트","긴 스커트","맥시","원피스","드레스"]):
            base_mask_name = "mask_longsleeve_longskirt.png"
        elif any(k in bot for k in ["스커트","치마","미니스커트"]):
            base_mask_name = "mask_longsleeve_skirt.png"
        else:
            base_mask_name = "mask_longsleeve.png"

        base_mask_path = BASESKIN_DIR / base_mask_name
        if not base_mask_path.exists():
            base_mask_path = BASESKIN_DIR / "mask_longsleeve.png"
        if base_mask_path.exists():
            shirt_rgb = parse_color(features.get("shirt_color") or "#f0f0f0")
            shirt_zone_colors = {**zone_colors, "top": shirt_rgb, "jacket": shirt_rgb}
            base_mask = np.array(Image.open(base_mask_path).convert("RGBA"), dtype=np.uint8)
            base_maxv = _zone_stats_split(body_ref, leg_ref, base_mask, arm_ref)
            tmp_mask  = base_mask.copy()
            tmp_mask[mask_arr[:, :, 3] > 10, 3] = 0
            _paint_mask(arr, tmp_mask, body_ref, leg_ref, shirt_zone_colors, base_maxv, arm_ref)

    _paint_mask(arr, mask_arr, body_ref, leg_ref, zone_colors, zone_maxv, arm_ref)

    # 악세서리 오버레이 적용
    for acc_path in pick_acc_overlays(features):
        acc_arr  = np.array(Image.open(acc_path).convert("RGBA"), dtype=np.uint8)
        acc_maxv = _zone_stats_split(body_ref, leg_ref, acc_arr, arm_ref)
        _paint_mask(arr, acc_arr, body_ref, leg_ref, zone_colors, acc_maxv, arm_ref)


def _trim_ref_for_shorts(leg_ref: np.ndarray) -> np.ndarray:
    """긴바지 레퍼런스를 반바지 높이로 가상 크롭.
    다리 하단(y=26..32 / y=58..64)을 투명화 → 상단 절반 텍스처만 사용.
    레퍼런스에 반바지가 없어도 긴바지 허벅지 부분을 반바지처럼 쓸 수 있음."""
    mod = leg_ref.copy()
    mod[26:32, 0:16, 3] = 0    # 오른다리 레이어1 하단 제거
    mod[58:64, 16:32, 3] = 0   # 왼다리 레이어1 하단 제거
    return mod


def _fill_back_faces(arr: np.ndarray):
    """뒷면 UV가 단색(std<18)이면 앞면 패턴을 좌우반전+어둡게 복사해 텍스처 추가.
    팔은 제외 — 팔 뒤면을 통으로 채우면 부자연스러운 회색 블록이 됨."""
    # (앞면 x,y,w,h), (뒷면 x,y,w,h), 어둡기 배율
    PAIRS = [
        ((20, 20, 8, 12), (32, 20, 8, 12), 0.68),   # 몸통만 (팔/다리 제외)
    ]
    for (fx, fy, fw, fh), (bx, by, bw, bh), shade in PAIRS:
        back = arr[by:by+bh, bx:bx+bw, :]
        valid_back = back[:, :, 3] > 10
        if not valid_back.any():
            continue
        # 공간적 표준편차 계산 — 픽셀마다 RGB 변화량 (채널별 평균)
        back_rgb = back[:, :, :3].astype(float)
        spatial_std = float(max(
            back_rgb[:, :, 0][valid_back].std(),
            back_rgb[:, :, 1][valid_back].std(),
            back_rgb[:, :, 2][valid_back].std(),
        ))
        if spatial_std >= 18:
            continue  # 이미 충분한 텍스처
        # 앞면 좌우반전 + shade
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


def recolor_hair_base(hair_arr: np.ndarray, target_rgb: tuple) -> np.ndarray:
    """numpy 벡터화: 헤어 베이스 V값으로 타겟 색상 밝기 스케일"""
    valid = hair_arr[:, :, 3] > 10
    v_map = _np_rgb2v(hair_arr[:, :, :3])
    max_v = float(v_map[valid].max()) if valid.any() else 1.0
    if max_v < 0.01:
        max_v = 1.0

    brightness = np.clip(v_map / max_v * BRIGHTNESS_BOOST, 0.0, 1.0)  # (64,64)
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


def draw_hair_from_ref(arr: np.ndarray, head_comp: np.ndarray,
                       hair_rgb: tuple, skin_base: np.ndarray):
    """레퍼런스 헤드 컴포넌트를 이용한 고품질 머리카락 렌더링.

    head_comp : mine_assets.py로 추출한 ref{N}_head.png (64×64 RGBA)
    hair_rgb  : 목표 머리카락 RGB
    skin_base : 피부톤 적용 직후 arr 복사본 (피부 픽셀 복원용)
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
        gray = (rgb_f[:,:,0]*0.299 + rgb_f[:,:,1]*0.587 + rgb_f[:,:,2]*0.114)

        # UV 면별 위치 명암 (레퍼런스가 평면 텍스처여도 입체감 유지)
        _HEAD_FACE_SHADE = np.ones((16, 32), dtype=np.float32)
        _HEAD_FACE_SHADE[0:8,  8:16] = 0.88   # 머리 윗면
        _HEAD_FACE_SHADE[8:16, 0:8]  = 0.78   # 오른 옆면
        _HEAD_FACE_SHADE[8:16, 16:24]= 0.78   # 왼 옆면
        _HEAD_FACE_SHADE[8:16, 24:32]= 0.62   # 뒷면

        max_gray = float(gray[is_hair].max())
        # 레퍼런스 밝기 × 면 위치 명암 합산
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


def draw_eyes(arr: np.ndarray, eye_shape: str, eye_rgb: tuple):
    """눈 형태 적용 + 홍채 색상 재채색"""
    fname = EYE_SHAPE_MAP.get((eye_shape or "").strip(), EYE_FALLBACK)
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
        # 홍채 범위 (윤곽·하이라이트 제외)
        if 15 < gray < 160:
            factor = max(0.3, gray / 80.0)
            result[y, x, 0] = min(255, int(er * factor))
            result[y, x, 1] = min(255, int(eg * factor))
            result[y, x, 2] = min(255, int(eb * factor))
    _composite_layer(arr, result)


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

    hair_rgb   = parse_color(features.get("hair_color", "검정"))
    hair_style = features.get("hair_style", "")
    hair_bangs = features.get("hair_bangs", "")
    eye_rgb    = parse_color(features.get("eye_color") or "#2c2c2c")
    eye_shape  = features.get("eye_shape", "일반")
    body_type  = (features.get("body_type") or "normal").lower()

    # 1. 근육 오버레이 (피부 위, 의상 아래)
    if body_type in ("athletic", "muscular"):
        draw_muscle(arr)

    # 2. 눈 (피부 위)
    draw_eyes(arr, eye_shape, eye_rgb)

    # 눈 적용 후 백업 — draw_hair_from_ref가 face 복원 시 눈 픽셀도 보존됨
    skin_base = arr.copy()

    # 3. 레퍼런스 컴포넌트 선택 (body/arm/leg/head_comp)
    comps = _select_ref_components(features)

    # 4. 의상
    apply_mask_clothing(arr, features, _comps=comps)

    # 4-1. 뒷면 텍스처 보강 (단색 → 앞면 패턴 미러링)
    _fill_back_faces(arr)

    # 5. 머리카락
    head_comp = comps.get("head_comp")
    if head_comp is not None:
        # 레퍼런스 헤드 컴포넌트 기반 — 헤드 UV 전체 처리
        draw_hair_from_ref(arr, head_comp, hair_rgb, skin_base)

    # 몸통 연장 (장발만) — 단발/숏컷은 HAIR_BODY_MAP[key]=None 이라 자동 스킵
    draw_hair_body_only(arr, hair_rgb, hair_style)
    # 앞머리 레이어는 항상 최상단 (대머리 방지)
    draw_hair_bangs_only(arr, hair_rgb, hair_bangs)

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
    draw_hair_body_only(arr, hair_rgb, hair_style)
    draw_hair_bangs_only(arr, hair_rgb, hair_bangs)
    _mirror_clothing_to_layer2(arr)

    if features.get("glasses", False):
        draw_glasses(arr)

    return Image.fromarray(arr, "RGBA")
