"""
app.py
SkinForge AI — 사진 업로드 → 마인크래프트 스킨 생성 → 3D 미리보기·다운로드
"""

import os
import base64
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image
import gradio as gr

load_dotenv()

from core.feature_extractor import extract_features
from core.skin_generator import generate_skin
from core.skin_validator import validate_and_fix

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

* { box-sizing: border-box; }
body, .gradio-container { background: #0d0d0d !important; color: #e0e0e0 !important; font-family: 'Inter', sans-serif !important; }
.gradio-container { max-width: 1100px !important; margin: 0 auto !important; padding: 0 !important; }
footer { display: none !important; }

/* header */
#header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 18px 28px; background: #111;
    border-bottom: 1px solid #1e1e1e;
}
#header .logo { display: flex; align-items: center; gap: 10px; font-size: 20px; font-weight: 700; color: #00C9A7; }
#header .guide-btn {
    background: transparent; border: 1px solid #333; color: #aaa;
    padding: 6px 14px; border-radius: 6px; font-size: 13px; cursor: pointer;
}

/* main layout */
#main { display: flex; gap: 20px; padding: 24px 28px; }
#left-panel { flex: 1; display: flex; flex-direction: column; gap: 14px; }
#right-panel { flex: 1; display: flex; flex-direction: column; gap: 14px; }

/* upload */
#upload-wrap .wrap { border: 2px dashed #00C9A7 !important; border-radius: 12px !important; background: #111 !important; min-height: 280px !important; }
#upload-wrap .wrap:hover { background: #151515 !important; }
#upload-wrap svg { color: #00C9A7 !important; }
#upload-wrap .upload-text { color: #aaa !important; }

/* generate button */
#gen-btn { background: #00C9A7 !important; color: #000 !important; font-weight: 700 !important; font-size: 16px !important; border-radius: 10px !important; border: none !important; padding: 14px !important; }
#gen-btn:hover { background: #00b396 !important; }

/* status */
#status-box textarea { background: #111 !important; border: 1px solid #1e1e1e !important; border-radius: 8px !important; color: #aaa !important; font-size: 13px !important; }
#status-box label { color: #555 !important; }

/* secondary buttons */
.sec-btn button { background: #1a1a1a !important; color: #ccc !important; border: 1px solid #2a2a2a !important; border-radius: 8px !important; font-size: 14px !important; }
.sec-btn button:hover { background: #222 !important; border-color: #00C9A7 !important; color: #00C9A7 !important; }
"""

VIEWER_EMPTY = """
<div style="background:#111; border-radius:12px; padding:20px; border:1px solid #1e1e1e; height:100%;">
  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
    <span style="color:#aaa; font-size:14px; font-weight:600;">3D 미리보기</span>
    <span style="color:#444; font-size:12px;">🎮 Minecraft Java Edition</span>
  </div>
  <div style="display:flex; justify-content:center; align-items:center; min-height:280px; background:#0a0a0a; border-radius:10px; border:1px solid #1a1a1a;">
    <span style="color:#444; font-size:14px;">스킨을 생성하면 3D 미리보기가 표시됩니다</span>
  </div>
  <div style="display:flex; justify-content:center; gap:10px; margin-top:14px;">
    <button disabled style="background:#161616; border:1px solid #222; color:#444; padding:8px 22px; border-radius:8px;">←</button>
    <button disabled style="background:#161616; border:1px solid #222; color:#444; padding:8px 22px; border-radius:8px;">⬜</button>
    <button disabled style="background:#161616; border:1px solid #222; color:#444; padding:8px 22px; border-radius:8px;">→</button>
  </div>
</div>
"""

def make_viewer_html(skin_b64: str) -> str:
    return f"""
<div style="background:#111; border-radius:12px; padding:20px; border:1px solid #1e1e1e;">
  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
    <span style="color:#aaa; font-size:14px; font-weight:600;">3D 미리보기</span>
    <span style="color:#444; font-size:12px;">🎮 Minecraft Java Edition</span>
  </div>
  <div style="display:flex; justify-content:center; align-items:center; background:#0a0a0a; border-radius:10px; border:1px solid #1a1a1a; overflow:hidden; height:300px;">
    <canvas id="skinCanvas" style="width:100%; height:100%;"></canvas>
  </div>
  <div style="display:flex; justify-content:center; gap:10px; margin-top:14px;">
    <button onclick="if(window._sv)window._sv.playerObject.rotation.y-=0.3" style="background:#1a1a1a; border:1px solid #2a2a2a; color:#ccc; padding:8px 22px; border-radius:8px; cursor:pointer;">←</button>
    <button onclick="if(window._sv)window._sv.playerObject.rotation.y=0" style="background:#1a1a1a; border:1px solid #2a2a2a; color:#ccc; padding:8px 22px; border-radius:8px; cursor:pointer;">⬜</button>
    <button onclick="if(window._sv)window._sv.playerObject.rotation.y+=0.3" style="background:#1a1a1a; border:1px solid #2a2a2a; color:#ccc; padding:8px 22px; border-radius:8px; cursor:pointer;">→</button>
  </div>
</div>
<script src="https://unpkg.com/skinview3d@2.1.1/bundles/skinview3d.bundle.js"></script>
<script>
(function() {{
  const canvas = document.getElementById('skinCanvas');
  if (!canvas) return;
  const viewer = new skinview3d.SkinViewer({{
    canvas: canvas,
    width: canvas.parentElement.clientWidth || 300,
    height: 300,
    skin: "data:image/png;base64,{skin_b64}"
  }});
  viewer.renderer.setClearColor(0x0a0a0a, 1);
  viewer.autoRotate = true;
  viewer.autoRotateSpeed = 0.8;
  viewer.zoom = 0.9;
  window._sv = viewer;
}})();
</script>
"""


def process(photo: Image.Image):
    if photo is None:
        return VIEWER_EMPTY, None, "⚠️ 사진을 업로드해 주세요."
    try:
        features = extract_features(photo)
        tone = features.get("skin_tone", "warm_bright")
        status = f"✅ 분석 완료 — 피부톤: {tone} | 헤어: {features.get('hair_color')} {features.get('hair_style')}"

        skin_img = generate_skin(features)
        skin_img, is_valid, errors = validate_and_fix(skin_img)
        if not is_valid:
            status += f"\n⚠️ 보정 후에도 오류: {errors}"

        tmp = tempfile.NamedTemporaryFile(suffix=".png", dir=OUTPUT_DIR, delete=False)
        skin_img.save(tmp.name, format="PNG")

        with open(tmp.name, "rb") as f:
            skin_b64 = base64.b64encode(f.read()).decode()

        viewer_html = make_viewer_html(skin_b64)
        return viewer_html, tmp.name, status

    except Exception as e:
        return VIEWER_EMPTY, None, f"❌ 오류 발생: {e}"


HEADER_HTML = """
<div id="header">
  <div class="logo">
    <span style="font-size:28px;">🎮</span>
    <span>SkinForge AI</span>
  </div>
  <button class="guide-btn">📋 사용 가이드</button>
</div>
"""

with gr.Blocks(css=CSS, title="SkinForge AI") as demo:
    gr.HTML(HEADER_HTML)

    with gr.Row(elem_id="main"):
        with gr.Column(elem_id="left-panel"):
            photo_input = gr.Image(
                type="pil",
                label="사진을 업로드하세요 (JPG, PNG 최대 10MB)",
                elem_id="upload-wrap",
            )
            generate_btn = gr.Button("✨ 스킨 생성하기", elem_id="gen-btn")
            status_output = gr.Textbox(label="상태", interactive=False, elem_id="status-box")

        with gr.Column(elem_id="right-panel"):
            viewer_output = gr.HTML(value=VIEWER_EMPTY)
            with gr.Row():
                uv_btn = gr.Button("📐 UV 맵 보기", elem_classes="sec-btn")
                download_output = gr.File(label="⬇️ PNG 다운로드", elem_classes="sec-btn")

    generate_btn.click(
        fn=process,
        inputs=[photo_input],
        outputs=[viewer_output, download_output, status_output],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
