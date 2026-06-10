"""
feature_extractor.py
사진 → 피부톤 / 헤어 / 의상 특징 JSON 추출
"""

import os
import json
import io
from google import genai
from google.genai import types
from PIL import Image

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

EXTRACT_PROMPT = """
주어진 인물 사진을 분석해 다음 항목을 JSON으로만 반환하세요. 설명 없이 JSON만 출력.

{
  "skin_tone": "warm_bright | warm_normal | warm_dark | cool_bright | cool_normal | cool_dark",
  "hair_color": "색상 설명 (예: 검정, 갈색, 금발, 흰색)",
  "hair_style": "스타일 설명 (예: 짧은 직모, 긴 웨이브, 단발)",
  "top_color": "상의 색상",
  "top_style": "상의 스타일 (예: 흰 셔츠, 검정 후드, 교복)",
  "bottom_color": "하의 색상",
  "bottom_style": "하의 스타일 (예: 청바지, 검정 슬랙스)",
  "shoes_color": "신발 색상",
  "accessories": "악세사리 설명 (없으면 없음)",
  "glasses": true,
  "gender_expression": "남성적 | 여성적 | 중성적"
}
"""


def extract_features(image: Image.Image) -> dict:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=buf.read(), mime_type="image/png"),
                EXTRACT_PROMPT,
            ],
        )
        text = response.text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        print(f"[feature_extractor] 분석 실패, 기본값 반환: {e}")
        return _default_features()


def _default_features() -> dict:
    return {
        "skin_tone": "warm_bright",
        "hair_color": "검정",
        "hair_style": "짧은 직모",
        "top_color": "흰색",
        "top_style": "흰 셔츠",
        "bottom_color": "네이비",
        "bottom_style": "슬랙스",
        "shoes_color": "검정",
        "accessories": "없음",
        "glasses": False,
        "gender_expression": "중성적",
    }
