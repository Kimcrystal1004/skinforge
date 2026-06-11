"""
mine_assets.py
레퍼런스 스킨에서 UV 컴포넌트 추출 → baseskin/components/
로컬에서 한 번만 실행: python mine_assets.py

출력:
  baseskin/components/ref{N}_head.png   — 머리 전체 (헤어+피부, 필터 없음)
  baseskin/components/ref{N}_body.png   — 몸통 의상 픽셀만
  baseskin/components/ref{N}_rarm.png   — 오른팔 의상 픽셀만
  baseskin/components/ref{N}_larm.png   — 왼팔 의상 픽셀만
  baseskin/components/ref{N}_rleg.png   — 오른다리 의상 픽셀만
  baseskin/components/ref{N}_lleg.png   — 왼다리 의상 픽셀만
  baseskin/components/component_index.json
"""

import json, re, time
import numpy as np
from PIL import Image
from pathlib import Path

ROOT     = Path(__file__).parent
BASESKIN = ROOT / "baseskin"
COMP_DIR = BASESKIN / "components"
TAGS_FILE = BASESKIN / "reference_tags.json"

# ── 마스크 선택 (skin_generator.pick_mask 인라인, API 키 불필요) ──────
# (top_kws, bot_kws, 파일명) 형식 — skin_generator.MASK_STYLE_MAP과 동기화
_MASK_STYLE_MAP = [
    (["자켓","jacket","코트","블레이저","카디건","가디건","cardigan","니트","스웨터","집업","점퍼","후드집업"],
     ["반바지","shorts","쇼츠","핫팬츠","bermuda","짧은 바지","짧은바지","short pants"], "mask_jacket_shorts.png"),
    (["자켓","jacket","코트","블레이저","카디건","가디건","cardigan","니트","스웨터","집업","점퍼","후드집업"],
     ["롱스커트","긴 스커트","맥시","원피스","드레스"],                                  "mask_jacket_longskirt.png"),
    (["자켓","jacket","코트","블레이저","카디건","가디건","cardigan","니트","스웨터","집업","점퍼","후드집업"],
     ["스커트","치마","미니"],                                                          "mask_jacket_skirt.png"),
    (["자켓","jacket","코트","블레이저","카디건","가디건","cardigan","니트","스웨터","집업","점퍼","후드집업"],
     [], "mask_jacket.png"),
    (["오프숄더","off-shoulder"], ["롱스커트","긴 스커트","맥시","원피스","드레스"], "mask_crop_long_shorderless.png"),
    (["오프숄더","off-shoulder"], ["스커트","치마","미니"],                          "mask_crop_shorts_shorderless.png"),
    (["오프숄더","off-shoulder"], [],                                                "mask_crop_long_shorderless.png"),
    (["크롭","crop"], ["롱스커트","긴 스커트","맥시","원피스","드레스"],             "mask_crop_skirt.png"),
    (["크롭","crop"], ["스커트","치마","미니"],                                       "mask_crop_skirt.png"),
    (["크롭","crop"], ["반바지","shorts","쇼츠","핫팬츠","bermuda","짧은 바지","짧은바지","short pants"], "mask_crop_shorts.png"),
    (["크롭","crop"], [],                                                             "mask_crop_long.png"),
    (["민소매","나시","sleeveless","탱크"], ["롱스커트","긴 스커트","맥시","원피스","드레스"], "mask_sleeveless_longskirt.png"),
    (["민소매","나시","sleeveless","탱크"], ["스커트","치마","미니"],                        "mask_sleeveless_skirt.png"),
    (["민소매","나시","sleeveless","탱크"], ["반바지","shorts","쇼츠","핫팬츠","bermuda","짧은 바지","짧은바지","short pants"], "mask_sleeveless_shorts.png"),
    (["민소매","나시","sleeveless","탱크"], [],                                              "mask_sleeveless.png"),
    (["반팔","short sleeve","반소매","반팔티","t-shirt","tshirt"], ["롱스커트","긴 스커트","맥시","원피스","드레스"],    "mask_shortsleeve_longskirt.png"),
    (["반팔","short sleeve","반소매","반팔티","t-shirt","tshirt"], ["스커트","치마","미니스커트"],                       "mask_shortsleeve_skirt.png"),
    (["반팔","short sleeve","반소매","반팔티","t-shirt","tshirt"], ["반바지","shorts","쇼츠","핫팬츠","bermuda","짧은 바지","짧은바지","short pants"], "mask_shortsleeve_shorts.png"),
    (["반팔","short sleeve","반소매","반팔티","t-shirt","tshirt"], [],                                                   "mask_shortsleeve.png"),
    ([], ["롱스커트","긴 스커트","맥시","원피스","드레스"],                                  "mask_longsleeve_longskirt.png"),
    ([], ["스커트","치마","미니스커트"],                                                     "mask_longsleeve_skirt.png"),
    ([], ["반바지","shorts","쇼츠","핫팬츠","bermuda","짧은 바지","짧은바지","short pants"], "mask_longsleeve_shorts.png"),
]
_MASK_FALLBACK = "mask_longsleeve.png"

def pick_mask(features: dict) -> Path:
    top = (features.get("top_style", "") or "").lower()
    bot = (features.get("bottom_style", "") or "").lower()
    for top_kws, bot_kws, filename in _MASK_STYLE_MAP:
        top_ok = (not top_kws) or any(k in top for k in top_kws)
        bot_ok = (not bot_kws) or any(k in bot for k in bot_kws)
        if top_ok and bot_ok:
            p = BASESKIN / filename
            if p.exists():
                return p
    return BASESKIN / _MASK_FALLBACK

# ── UV 컴포넌트 영역 정의 (x, y, w, h) ────────────────────────────
UV_REGIONS = {
    "head": [(0,  0,  32, 16)],   # 머리 레이어1 전체
    "body": [(16, 16, 24, 16)],   # 몸통 레이어1
    "rarm": [(40, 16, 16, 16)],   # 오른팔 레이어1
    "larm": [(32, 48, 16, 16)],   # 왼팔 레이어1
    "rleg": [(0,  16, 16, 16)],   # 오른다리 레이어1
    "lleg": [(16, 48, 16, 16)],   # 왼다리 레이어1
}

def _clothing_mask(mask_arr: np.ndarray) -> np.ndarray:
    """마스크 배열에서 의상 존 픽셀 위치를 bool 배열로 반환 (벡터화)"""
    ma = mask_arr[:, :, 3]
    mr = mask_arr[:, :, 0].astype(np.int16)
    mg = mask_arr[:, :, 1].astype(np.int16)
    mb = mask_arr[:, :, 2].astype(np.int16)
    valid = ma > 10
    is_top    = valid & (mr < 40)  & (mg > 200) & (mb < 40)    # 초록
    is_bot    = valid & (mr < 40)  & (mg < 40)  & (mb > 200)   # 파랑
    is_shoes  = valid & (mr > 200) & (mg > 200) & (mb < 40)    # 노랑
    is_jacket = valid & (mr < 40)  & (mg > 200) & (mb > 200)   # 시안
    is_acc    = valid & (mr > 200) & (mg < 40)  & (mb > 200)   # 마젠타
    return is_top | is_bot | is_shoes | is_jacket | is_acc


def extract_components(arr: np.ndarray, mask_arr: np.ndarray, ref_num: str) -> dict[str, str]:
    """레퍼런스 배열에서 컴포넌트 추출 및 저장 → {comp_name: filename}"""
    clothing = _clothing_mask(mask_arr)
    saved = {}

    for comp_name, regions in UV_REGIONS.items():
        out = np.zeros((64, 64, 4), dtype=np.uint8)
        for (x, y, w, h) in regions:
            sl = np.s_[y:y+h, x:x+w]
            if comp_name == "head":
                # 헤드: 필터 없이 모든 픽셀 (헤어+피부 포함)
                out[sl] = arr[sl]
            else:
                # 의상 컴포넌트: 마스크로 필터링된 픽셀만
                region_clothing = clothing[sl]
                region_arr      = arr[sl]
                patch = np.zeros_like(region_arr)
                patch[region_clothing] = region_arr[region_clothing]
                out[sl] = patch

        fname = f"ref{ref_num}_{comp_name}.png"
        Image.fromarray(out, "RGBA").save(COMP_DIR / fname)
        saved[comp_name] = fname

    return saved


def _fmt_time(secs: float) -> str:
    m, s = int(secs) // 60, int(secs) % 60
    return f"{m:02d}:{s:02d}"


def main():
    COMP_DIR.mkdir(exist_ok=True)

    with open(TAGS_FILE, encoding="utf-8") as f:
        tags: dict = json.load(f)

    entries = list(tags.items())
    total   = len(entries)
    start   = time.time()

    print(f"컴포넌트 추출 시작 ─ {total}개 레퍼런스 × {len(UV_REGIONS)}개 컴포넌트")
    print(f"저장 위치: {COMP_DIR}")
    print("─" * 65)

    index = {}
    done  = 0
    errors = 0

    for fname, tag in entries:
        ref_path = BASESKIN / fname
        if not ref_path.exists():
            done += 1
            errors += 1
            continue

        # 레퍼런스 PNG 로드
        arr = np.array(Image.open(ref_path).convert("RGBA"), dtype=np.uint8)

        # 해당 레퍼런스의 의상 마스크 결정
        try:
            mask_path = pick_mask({"top_style": tag.get("top_style",""),
                                   "bottom_style": tag.get("bottom_style","")})
            mask_arr = np.array(Image.open(mask_path).convert("RGBA"), dtype=np.uint8)
        except Exception:
            mask_arr = np.zeros((64, 64, 4), dtype=np.uint8)

        # 번호 추출: "reference (14).png" → "14"
        m = re.search(r'reference \((\d+)\)', fname)
        ref_num = m.group(1) if m else re.sub(r'[^0-9]', '', fname) or fname

        saved = extract_components(arr, mask_arr, ref_num)
        index[ref_num] = {**tag, "files": saved}

        done += 1
        elapsed   = time.time() - start
        per_item  = elapsed / done
        remaining = per_item * (total - done)
        pct       = done / total * 100
        filled    = int(pct / 5)
        bar       = "#" * filled + "." * (20 - filled)

        print(f"\r  [{bar}] {done:3d}/{total}  ({pct:5.1f}%)  "
              f"경과: {_fmt_time(elapsed)}  남은: {_fmt_time(remaining)}  "
              f"{'오류:'+str(errors) if errors else ''}",
              end="", flush=True)

    print()

    # 인덱스 저장
    with open(COMP_DIR / "component_index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start
    ok = done - errors
    print(f"\n완료: {ok}/{total}개 성공  {errors}개 누락")
    print(f"총 {ok * len(UV_REGIONS)}개 컴포넌트 파일 생성  ({_fmt_time(elapsed)})")
    print(f"  → {COMP_DIR / 'component_index.json'}")


if __name__ == "__main__":
    main()
