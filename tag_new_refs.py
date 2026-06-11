"""
tag_new_refs.py
reference_tags.json에 없는 레퍼런스 스킨을 Gemini Vision으로 자동 태깅.
실행: python tag_new_refs.py
"""

import os, json, io, time
from pathlib import Path
from PIL import Image
from google import genai
from google.genai import types

ROOT      = Path(__file__).parent
BASESKIN  = ROOT / "baseskin"
TAGS_FILE = BASESKIN / "reference_tags.json"

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

TAG_PROMPT = """
이 마인크래프트 스킨 이미지를 분석해서 다음 JSON 형식으로만 반환하세요.
설명 없이 JSON만 출력하세요.

{
  "top_style": "상의 스타일 간단 설명 (예: 흰 블라우스, 검정 재킷, 교복 셔츠)",
  "bottom_style": "하의 스타일 간단 설명 (예: 청바지, 회색 반바지, 베이지 치마). 반드시 한국어로.",
  "top_color": "#hex (상의 대표 색상)",
  "bottom_color": "#hex (하의 대표 색상)",
  "style_tags": ["스타일 키워드 3~6개 (한국어)"],
  "gender": "여성 | 남성 | 중성 (하나만 선택)",
  "formality": "캐주얼 | 세미캐주얼 | 포멀 | 유니폼 | 스포츠 (하나만)"
}

주의사항:
- gender는 반드시 "여성", "남성", "중성" 중 하나만 사용 (적 없이)
- 치마/원피스/여성스러운 의상 → gender: 여성
- 바지/넥타이/슈트/남성스러운 의상 → gender: 남성
- 중성적인 캐주얼 의상 → gender: 중성
- 반바지(쇼츠/짧은 바지)는 bottom_style에 반드시 "반바지" 포함
- 색상은 반드시 #rrggbb hex 형식
"""


def tag_skin(image_path: Path) -> dict | None:
    img = Image.open(image_path).convert("RGBA")
    # 픽셀이 너무 작아 Gemini가 못 볼 수 있으니 4× 업스케일
    w, h = img.size
    img_big = img.resize((w * 4, h * 4), Image.NEAREST)
    buf = io.BytesIO()
    img_big.save(buf, format="PNG")
    buf.seek(0)

    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=buf.read(), mime_type="image/png"),
                TAG_PROMPT,
            ],
        )
        text = resp.text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        # 필수 필드 보정
        if "gender" in data:
            g = data["gender"]
            # "여성적"→"여성" 등 변환
            if "여성" in g:  data["gender"] = "여성"
            elif "남성" in g: data["gender"] = "남성"
            else:            data["gender"] = "중성"
        return data
    except Exception as e:
        print(f"    오류: {e}")
        return None


def main():
    with open(TAGS_FILE, encoding="utf-8") as f:
        tags: dict = json.load(f)

    all_pngs = sorted(BASESKIN.glob("reference*.png"),
                      key=lambda p: p.name)
    untagged = [p for p in all_pngs if p.name not in tags]

    if not untagged:
        print("새로 태깅할 파일이 없습니다.")
        return

    print(f"총 {len(untagged)}개 파일 태깅 시작")
    print("-" * 50)

    ok = err = 0
    for i, path in enumerate(untagged, 1):
        print(f"[{i:3d}/{len(untagged)}] {path.name} ...", end=" ", flush=True)
        result = tag_skin(path)
        if result:
            tags[path.name] = result
            g = result.get("gender", "?")
            ts = result.get("top_style", "")[:20]
            bs = result.get("bottom_style", "")[:15]
            print(f"OK  {g} | {ts} / {bs}")
            ok += 1
        else:
            print("FAIL")
            err += 1

        # rate limit 방지
        if i % 10 == 0:
            print("  ... 잠시 대기 ...")
            time.sleep(3)

        # 10개마다 중간 저장 (API 오류 시 손실 방지)
        if i % 10 == 0 or i == len(untagged):
            with open(TAGS_FILE, "w", encoding="utf-8") as f:
                json.dump(tags, f, ensure_ascii=False, indent=2)
            print(f"  → 저장 완료 ({i}개 처리)")

    print(f"\n완료: 성공 {ok}개, 실패 {err}개")
    print(f"총 태그 수: {len(tags)}개")

    # 성별 통계
    genders = [v.get("gender", "?") for v in tags.values()]
    from collections import Counter
    cnt = Counter(genders)
    print(f"성별 분포: 남성={cnt.get('남성',0)}, 여성={cnt.get('여성',0)}, 중성={cnt.get('중성',0)}, 기타={len(genders)-cnt.get('남성',0)-cnt.get('여성',0)-cnt.get('중성',0)}")


if __name__ == "__main__":
    main()
