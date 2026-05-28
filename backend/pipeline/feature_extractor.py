#[Step 1] 사진 → 속성 JSON 추출
import google.generativeai as genai
import json
import re
import os
import sys
from PIL import Image

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from backend.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash-lite")


EXTRACTION_PROMPT = """
이 이미지를 보고 마인크래프트 스킨 제작에 필요한 시각적 특징을 JSON으로 추출해줘.

반드시 아래 JSON 형식만 출력해. 설명 없이 JSON만.

{
"skin_tone": "피부색 (예: light, medium, dark, pale)",
"hair_color": "머리카락 색 (예: black, brown, blonde, red, white, blue 등)",
"hair_style": "머리 스타일 (예: short, long, curly, straight, ponytail, bald 등)",
"eye_color": "눈 색깔 (예: brown, black, blue, green, red 등)",
"top_color": "상의 주색상 (예: navy, white, red 등)",
"top_style": "상의 스타일 (예: t-shirt, hoodie, jacket, suit, dress 등)",
"bottom_color": "하의 주색상 (예: blue, black, khaki 등)",
"bottom_style": "하의 스타일 (예: jeans, shorts, skirt, pants 등)",
"has_glasses": true or false,
"has_hat": true or false,
"accessories": "기타 악세서리 설명 (없으면 none)",
"overall_theme": "전체적인 분위기 한 단어 (예: casual, formal, fantasy, cyberpunk 등)"
}
"""


def extract_features_from_image(image: Image.Image) -> dict:
    """
    PIL Image를 받아 Gemini Vision으로 특징 추출 후 dict 반환
    """
    response = model.generate_content([EXTRACTION_PROMPT, image])
    raw = response.text.strip()

    # JSON 파싱
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        raise ValueError(f"JSON 추출 실패. 원본 응답:\n{raw}")

    features = json.loads(json_match.group())
    return features


def extract_features_from_path(image_path: str) -> dict:
    """
    이미지 파일 경로를 받아 특징 추출
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"이미지 파일 없음: {image_path}")

    image = Image.open(image_path).convert("RGB")
    return extract_features_from_image(image)


def extract_features_from_prompt(text_prompt: str) -> dict:
    """
    텍스트 프롬프트만으로 특징 추출 (이미지 없을 때)
    """
    prompt = f"""
마인크래프트 스킨 제작을 위해 아래 설명에서 시각적 특징을 JSON으로 추출해줘.
설명: "{text_prompt}"

반드시 아래 JSON 형식만 출력해. 설명 없이 JSON만.

{{
"skin_tone": "피부색",
"hair_color": "머리카락 색",
"hair_style": "머리 스타일",
"eye_color": "눈 색깔",
"top_color": "상의 주색상",
"top_style": "상의 스타일",
"bottom_color": "하의 주색상",
"bottom_style": "하의 스타일",
"has_glasses": true or false,
"has_hat": true or false,
"accessories": "기타 악세서리",
"overall_theme": "전체 분위기"
}}
"""
    response = model.generate_content(prompt)
    raw = response.text.strip()

    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        raise ValueError(f"JSON 추출 실패. 원본 응답:\n{raw}")

    features = json.loads(json_match.group())
    return features