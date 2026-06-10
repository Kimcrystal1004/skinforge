"""
tag_references.py
레퍼런스 스킨 83개를 Gemini Vision으로 분석해 reference_tags.json 생성
로컬에서 한 번만 실행: python tag_references.py
"""

import os, io, json, time
from pathlib import Path
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

BASESKIN_DIR = Path("baseskin")
OUTPUT_FILE  = BASESKIN_DIR / "reference_tags.json"

TAG_PROMPT = """
이 이미지는 64×64 마인크래프트 스킨 PNG입니다.
스킨의 의상 스타일을 분석해 JSON으로만 반환하세요. 설명 없이 JSON만 출력.

{
  "top_style": "상의 종류 (예: 교복 블라우스, 검정 크롭탑, 흰 셔츠, 후드티, 정장 재킷, 한복 저고리, 수영복, 운동복 상의, 경찰 제복)",
  "bottom_style": "하의 종류 (예: 네이비 치마, 청바지, 검정 슬랙스, 반바지, 롱스커트, 한복 치마, 수영복 하의)",
  "top_color": "#hex (상의 대표 색상)",
  "bottom_color": "#hex (하의 대표 색상)",
  "style_tags": ["태그 배열 (예: 교복, 여성적, 캐주얼, 정장, 한복, 스포츠, 수영복, 후드, 경찰, 웨딩, 드레스, 크롭, 반바지, 치마, 슬랙스)"],
  "gender": "여성 | 남성 | 중성",
  "formality": "캐주얼 | 세미포멀 | 포멀 | 유니폼 | 전통의상 | 스포츠"
}
"""

def tag_one(path: Path) -> dict:
    img = Image.open(path).convert("RGBA")
    # 4배 업스케일로 Gemini가 더 잘 인식하게
    img = img.resize((256, 256), Image.NEAREST)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=buf.read(), mime_type="image/png"),
            TAG_PROMPT,
        ],
    )
    text = response.text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def main():
    existing = {}
    if OUTPUT_FILE.exists():
        existing = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        print(f"기존 태그 {len(existing)}개 로드")

    refs = sorted(BASESKIN_DIR.glob("reference (*).png"),
                  key=lambda p: int(p.stem.split("(")[1].rstrip(")")))

    updated = 0
    for i, p in enumerate(refs, 1):
        fname = p.name
        if fname in existing:
            print(f"[{i:2}/{len(refs)}] SKIP  {fname}")
            continue
        try:
            tags = tag_one(p)
            existing[fname] = tags
            print(f"[{i:2}/{len(refs)}] OK    {fname} → {tags.get('style_tags')}")
            updated += 1
            # 중간 저장 (중단돼도 진행분 보존)
            OUTPUT_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(0.5)  # API 레이트 리밋 방지
        except Exception as e:
            print(f"[{i:2}/{len(refs)}] ERROR {fname}: {e}")
            existing[fname] = {"style_tags": [], "error": str(e)}
            OUTPUT_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n완료: {updated}개 새로 태깅, 총 {len(existing)}개")
    print(f"저장: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
