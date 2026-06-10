"""
skin_generator.py
recolor된 베이스 스킨 + 레퍼런스 스킨 + 특징 JSON → Gemini API → 64×64 PNG
"""

import os
import io
from pathlib import Path
from PIL import Image
from google import genai
from google.genai import types

from .recolor_skin import load_base, apply_skin_tone

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

REFERENCE_DIR = Path(__file__).parent.parent / "reference"

SKIN_GEN_PROMPT = """
You are a Minecraft skin pixel artist. Generate a EXACTLY 64×64 pixel Minecraft Java Edition skin texture (UV map).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 CRITICAL FORMAT REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Exactly 64×64 pixels, PNG with RGBA
- Hard pixel art edges — NO anti-aliasing, NO blur, NO gradients
- Every pixel is solid color

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📐 UV MAP LAYOUT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Head layer1: top(8,0,8,8) right(0,8,8,8) front(8,8,8,8) left(16,8,8,8) back(24,8,8,8)
Hat overlay: top(40,0,8,8) right(32,8,8,8) front(40,8,8,8) left(48,8,8,8) back(56,8,8,8)
Body: top(20,16,8,4) right(16,20,4,12) front(20,20,8,12) left(28,20,4,12) back(32,20,8,12)
Jacket: right(16,36,4,12) front(20,36,8,12) left(28,36,4,12) back(32,36,8,12)
Right arm: top(44,16,4,4) right(40,20,4,12) front(44,20,4,12) left(48,20,4,12) back(52,20,4,12)
Left arm: top(36,48,4,4) right(32,52,4,12) front(36,52,4,12) left(40,52,4,12) back(44,52,4,12)
Right leg: top(4,16,4,4) right(0,20,4,12) front(4,20,4,12) left(8,20,4,12) back(12,20,4,12)
Left leg: top(20,48,4,4) right(16,52,4,12) front(20,52,4,12) left(24,52,4,12) back(28,52,4,12)
Unused areas: fully transparent (alpha=0)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎨 SHADING RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Front=100%, Top=90%, Sides=80%, Back=65%, Bottom=60%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 CHARACTER TO GENERATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{character_description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Output EXACTLY 64×64 pixels
2. NO anti-aliasing
3. All UV regions must be filled
4. Unused areas must be transparent
5. Layer 2 (hat/jacket/arm overlays) must have meaningful content
6. Match the reference skin images provided in pixel art style
"""


def _build_character_description(features: dict) -> str:
    return f"""
Skin tone: {features.get('skin_tone', 'warm_bright')} — use the provided base skin as the skin color reference
Hair: {features.get('hair_color', '검정')} / {features.get('hair_style', '짧은 직모')}
Top: {features.get('top_color', '흰색')} {features.get('top_style', '셔츠')}
Bottom: {features.get('bottom_color', '네이비')} {features.get('bottom_style', '슬랙스')}
Shoes: {features.get('shoes_color', '검정')}
Accessories: {features.get('accessories', '없음')}
Glasses: {features.get('glasses', False)}
Gender expression: {features.get('gender_expression', '중성적')}

Keep the base skin's face structure (eyes, blush, shading) as-is.
Add ONLY: hair, clothing, shoes, accessories on top.
""".strip()


def _load_references() -> list:
    parts = []
    for p in sorted(REFERENCE_DIR.glob("*.png"))[:4]:
        with open(p, "rb") as f:
            parts.append(types.Part.from_bytes(data=f.read(), mime_type="image/png"))
    return parts


def generate_skin(features: dict) -> Image.Image:
    tone_key = features.get("skin_tone", "warm_bright")
    base_img = load_base(tone_key)
    recolored_base = apply_skin_tone(base_img, tone_key)

    buf = io.BytesIO()
    recolored_base.save(buf, format="PNG")
    buf.seek(0)
    base_part = types.Part.from_bytes(data=buf.read(), mime_type="image/png")

    ref_parts = _load_references()

    char_desc = _build_character_description(features)
    prompt = SKIN_GEN_PROMPT.format(character_description=char_desc)

    response = client.models.generate_content(
        model="gemini-2.0-flash-preview-image-generation",
        contents=[*ref_parts, base_part, prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            temperature=0.2,
        ),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image"):
            img = Image.open(io.BytesIO(part.inline_data.data)).convert("RGBA")
            return img

    raise ValueError("Gemini가 이미지를 반환하지 않았습니다.")
