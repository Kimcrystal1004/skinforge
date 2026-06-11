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
주어진 인물·캐릭터 사진을 분석해 다음 항목을 JSON으로만 반환하세요. 설명 없이 JSON만 출력.
⚠️ 배경은 완전히 무시하고, 인물/캐릭터의 신체·의상·헤어·눈만 분석하세요.
⚠️ 색상 필드(hair_color, eye_color, top_color, shirt_color, bottom_color, shoes_color)는 반드시 HTML hex 코드(예: #2b1a0e)로만 반환하세요.

{
  "skin_tone": "아래 중 하나만: pale | warm_bright | warm_normal | warm_dark | cool_bright | cool_normal | cool_dark | warm_deeper | cool_deeper | dark | very_dark\n  (pale=창백/anime흰, warm_bright=밝은웜톤, warm_deeper=짙은웜톤/남아시아, cool_deeper=짙은쿨톤, dark=어두운갈색, very_dark=매우어두운피부)",
  "eye_shape": "아래 중 하나만: 큰눈 | 둥근눈 | 일반 | 아몬드눈 | 반쌍꺼풀 | 가는눈 | 좁은눈 | 작은눈\n  (실제사람 동양인→일반이 기본, 서양인→큰눈/아몬드눈, 캐릭터→눈 모양 맞게)",
  "eye_color": "#hex — 정확한 홍채 색상.\n  실사 동양인: 어두운 갈색/검정 계열 (#2c2c2c, #3d2b1f, #4a3020 등).\n  캐릭터·서양인·이국적 눈: 실제 눈 색 정확히 추출 (파랑=#4a90d9, 민트/청록=#39c5bb, 초록=#3daa4a, 붉은=#cc3333, 보라=#9b59b6, 노랑=#e8c327, 금색=#c8a83c).\n  ⚠️ 캐릭터의 눈이 특이한 색이라면 반드시 그 색의 hex를 반환하세요.",
  "hair_color": "#hex (머리카락의 대표 색상)",
  "hair_style": "아래 중 하나만: 장발_생머리 | 장발_웨이브 | 중장발_생머리 | 중장발_웨이브 | 꽁지머리 | 짧은꽁지 | 사이드테일 | 양갈래_생머리 | 양갈래_웨이브 | 짧은양갈래_생머리 | 짧은양갈래_웨이브 | 단발 | 숏컷\n  (숏컷=남성 짧은머리/버즈컷/크롭컷, 단발=턱 위 단발)",
  "hair_bangs": "아래 중 하나만: 일자뱅 | 사이드뱅 | 노뱅 | 가르마",
  "body_type": "slim | normal | athletic | muscular",
  "top_color": "#hex (가장 겉에 보이는 상의 몸통 색상 — 재킷/코트 착용 시 재킷 색)",
  "sleeve_color": "#hex (소매/팔 색상 — 몸통과 다를 경우 별도 추출. 같으면 top_color와 동일 hex. 예: 흰 셔츠에 검정 소매=검정, 장갑·암워머 있으면 그 색)",
  "shirt_color": "#hex (재킷·코트 안에 입은 셔츠/블라우스 색상, 없으면 top_color와 동일)",
  "top_style": "상의 스타일 (예: 흰 셔츠, 검정 후드, 교복, 검정 정장 재킷)",
  "bottom_color": "#hex (하의 대표 색상)",
  "bottom_style": "하의 스타일 — 반드시 한국어로. 예: 청바지, 검정 슬랙스, 회색 반바지, 베이지 치마, 검정 레깅스\n  ⚠️ 반바지·쇼츠는 반드시 '반바지'라는 단어를 포함시키세요.",
  "shoes_color": "#hex (신발 색상)",
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
