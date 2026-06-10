"""
app.py
Gradio UI — 사진 업로드 → 마인크래프트 스킨 생성 → 미리보기·다운로드
"""

import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image
import gradio as gr

load_dotenv()

from core.feature_extractor import extract_features
from core.skin_generator import generate_skin
from core.skin_validator import validate_and_fix
from utils.image_utils import scale_nearest, add_checkerboard_bg, pil_to_bytes

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def process(photo: Image.Image) -> tuple:
    """
    메인 파이프라인:
    사진 → 특징 추출 → 스킨 생성 → 검증/보정 → 미리보기·다운로드 경로 반환
    """
    if photo is None:
        return None, None, "⚠️ 사진을 업로드해 주세요."

    try:
        # 1. 특징 추출
        features = extract_features(photo)
        tone = features.get("skin_tone", "warm_bright")
        status = f"✅ 분석 완료 — 피부톤: {tone} | 헤어: {features.get('hair_color')} {features.get('hair_style')}"

        # 2. 스킨 생성
        skin_img = generate_skin(features)

        # 3. 검증·보정
        skin_img, is_valid, errors = validate_and_fix(skin_img)
        if not is_valid:
            status += f"\n⚠️ 보정 후에도 오류: {errors}"

        # 4. 미리보기 (8배 확대 + 체커보드)
        preview = add_checkerboard_bg(scale_nearest(skin_img, 8))

        # 5. 다운로드용 임시 파일
        tmp = tempfile.NamedTemporaryFile(
            suffix=".png", dir=OUTPUT_DIR, delete=False
        )
        skin_img.save(tmp.name, format="PNG")

        return preview, tmp.name, status

    except Exception as e:
        return None, None, f"❌ 오류 발생: {e}"


# ── Gradio UI ────────────────────────────────────────────
with gr.Blocks(title="📸 사진 → 마인크래프트 스킨 변환기") as demo:
    gr.Markdown(
        """
        # 📸 사진 → 마인크래프트 스킨 변환기
        인물 사진을 업로드하면 Gemini AI가 해당 인물의 특징을 반영한
        64×64 마인크래프트 스킨을 자동으로 생성합니다.
        """
    )

    with gr.Row():
        with gr.Column(scale=1):
            photo_input = gr.Image(
                type="pil",
                label="📷 인물 사진 업로드 (전신 권장)",
            )
            generate_btn = gr.Button("🎮 스킨 생성", variant="primary")

        with gr.Column(scale=1):
            preview_output = gr.Image(
                label="🖼️ 생성된 스킨 미리보기",
                interactive=False,
            )
            download_output = gr.File(label="⬇️ 스킨 PNG 다운로드")
            status_output = gr.Textbox(label="상태", interactive=False)

    generate_btn.click(
        fn=process,
        inputs=[photo_input],
        outputs=[preview_output, download_output, status_output],
    )

    gr.Markdown(
        """
        ---
        **사용 방법**: 전신 사진 업로드 → '스킨 생성' 클릭 → 미리보기 확인 → PNG 다운로드
        후 마인크래프트에서 프로필 → 스킨 변경에서 적용하세요.
        """
    )

if __name__ == "__main__":
    demo.launch()
