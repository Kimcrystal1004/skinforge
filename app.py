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
body, .gradio-container {
    background: #0d0d0d !important;
    color: #e0e0e0 !important;
    font-family: 'Inter', sans-serif !important;
}
.gradio-container { max-width: 1080px !important; margin: 0 auto !important; padding: 0 !important; }
footer { display: none !important; }
.main { padding: 0 !important; }

/* header */
#sf-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 28px; background: #111; border-bottom: 1px solid #1e1e1e;
    margin-bottom: 0;
}

/* upload component 스타일 */
#upload-wrap { background: transparent !important; }
#upload-wrap .wrap {
    border: 2px dashed #00C9A7 !important;
    border-radius: 14px !important;
    background: #111 !important;
    min-height: 260px !important;
}
#upload-wrap .wrap:hover { background: #141414 !important; }
#upload-wrap svg { color: #00C9A7 !important; }
#upload-wrap .upload-text span { color: #aaa !important; }
#upload-wrap label { display: none !important; }

/* 생성 버튼 */
#gen-btn button {
    background: #00C9A7 !important;
    color: #000 !important;
    font-weight: 700 !important;
    font-size: 16px !important;
    border-radius: 10px !important;
    border: none !important;
    width: 100% !important;
    padding: 14px !important;
    cursor: pointer !important;
}
#gen-btn button:hover { background: #00b396 !important; }

/* 상태 텍스트박스 */
#status-box { margin-top: 0 !important; }
#status-box label { display: none !important; }
#status-box textarea {
    background: #111 !important;
    border: 1px solid #1e1e1e !important;
    border-radius: 8px !important;
    color: #888 !important;
    font-size: 12px !important;
    min-height: 36px !important;
    resize: none !important;
}

/* 하단 버튼 행 */
#bottom-row { margin-top: 4px !important; }
#uv-btn button {
    background: #1a1a1a !important;
    color: #ccc !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    width: 100% !important;
    padding: 12px !important;
}
#uv-btn button:hover { border-color: #00C9A7 !important; color: #00C9A7 !important; }

/* 다운로드 버튼 */
#dl-btn button {
    background: #1a1a1a !important;
    color: #ccc !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    width: 100% !important;
    padding: 12px !important;
}
#dl-btn button:hover { border-color: #00C9A7 !important; color: #00C9A7 !important; }

/* gr.File 숨기기 */
#dl-file { display: none !important; }

/* 뷰어 HTML */
#viewer-html { background: transparent !important; padding: 0 !important; }
#viewer-html > div { margin: 0 !important; }

/* 전체 패널 패딩 */
#left-col { padding: 24px 16px 24px 28px !important; }
#right-col { padding: 24px 28px 24px 16px !important; }
"""

VIEWER_EMPTY = """
<div style="background:#111; border-radius:14px; padding:20px; border:1px solid #1e1e1e; height:420px; display:flex; flex-direction:column;">
  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
    <span style="color:#aaa; font-size:14px; font-weight:600;">3D 미리보기</span>
    <span style="color:#444; font-size:12px;">🎮 Minecraft Java Edition</span>
  </div>
  <div style="flex:1; display:flex; justify-content:center; align-items:center; background:#0a0a0a; border-radius:10px; border:1px solid #1a1a1a;">
    <span style="color:#444; font-size:13px;">스킨을 생성하면 3D 미리보기가 표시됩니다</span>
  </div>
  <div style="display:flex; justify-content:center; gap:10px; margin-top:14px;">
    <button disabled style="background:#161616; border:1px solid #222; color:#444; padding:9px 28px; border-radius:8px; font-size:16px; cursor:not-allowed;">←</button>
    <button disabled style="background:#161616; border:1px solid #222; color:#444; padding:9px 28px; border-radius:8px; font-size:16px; cursor:not-allowed;">⬜</button>
    <button disabled style="background:#161616; border:1px solid #222; color:#444; padding:9px 28px; border-radius:8px; font-size:16px; cursor:not-allowed;">→</button>
  </div>
</div>
"""

def make_viewer_html(skin_b64: str) -> str:
    return f"""
<div style="background:#111; border-radius:14px; padding:20px; border:1px solid #1e1e1e; height:420px; display:flex; flex-direction:column;">
  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
    <span style="color:#aaa; font-size:14px; font-weight:600;">3D 미리보기</span>
    <span style="color:#444; font-size:12px;">🎮 Minecraft Java Edition</span>
  </div>
  <div style="flex:1; display:flex; justify-content:center; align-items:center; background:#0a0a0a; border-radius:10px; border:1px solid #1a1a1a; overflow:hidden;">
    <canvas id="skinCanvas" style="width:100%; height:100%; display:block;"></canvas>
  </div>
  <div style="display:flex; justify-content:center; gap:10px; margin-top:14px;">
    <button onclick="if(window._sv)window._sv.playerObject.rotation.y-=0.4" style="background:#1a1a1a; border:1px solid #2a2a2a; color:#ccc; padding:9px 28px; border-radius:8px; font-size:16px; cursor:pointer; transition:border-color .2s;">←</button>
    <button onclick="if(window._sv){{window._sv.playerObject.rotation.y=0;window._sv.playerObject.rotation.x=0;}}" style="background:#1a1a1a; border:1px solid #2a2a2a; color:#ccc; padding:9px 28px; border-radius:8px; font-size:16px; cursor:pointer;">⬜</button>
    <button onclick="if(window._sv)window._sv.playerObject.rotation.y+=0.4" style="background:#1a1a1a; border:1px solid #2a2a2a; color:#ccc; padding:9px 28px; border-radius:8px; font-size:16px; cursor:pointer;">→</button>
  </div>
</div>
<script src="https://unpkg.com/skinview3d@2.1.1/bundles/skinview3d.bundle.js"></script>
<script>
(function() {{
  function init() {{
    const canvas = document.getElementById('skinCanvas');
    if (!canvas) {{ setTimeout(init, 200); return; }}
    const wrap = canvas.parentElement;
    const w = wrap.clientWidth || 300;
    const h = wrap.clientHeight || 300;
    const viewer = new skinview3d.SkinViewer({{
      canvas: canvas,
      width: w,
      height: h,
      skin: "data:image/png;base64,{skin_b64}"
    }});
    viewer.renderer.setClearColor(0x0a0a0a, 1);
    viewer.autoRotate = true;
    viewer.autoRotateSpeed = 0.6;
    viewer.zoom = 0.85;
    window._sv = viewer;
  }}
  init();
}})();
</script>
"""


def process(photo: Image.Image):
    if photo is None:
        return VIEWER_EMPTY, None, "⚠️ 사진을 업로드해 주세요."
    try:
        features = extract_features(photo)
        tone = features.get("skin_tone", "warm_bright")
        status = f"✅ 피부톤: {tone} | 헤어: {features.get('hair_color')} {features.get('hair_style')}"

        skin_img = generate_skin(features)
        skin_img, is_valid, errors = validate_and_fix(skin_img)
        if not is_valid:
            status += f" | ⚠️ {errors}"

        tmp = tempfile.NamedTemporaryFile(suffix=".png", dir=OUTPUT_DIR, delete=False)
        skin_img.save(tmp.name, format="PNG")

        with open(tmp.name, "rb") as f:
            skin_b64 = base64.b64encode(f.read()).decode()

        return make_viewer_html(skin_b64), tmp.name, status

    except Exception as e:
        return VIEWER_EMPTY, None, f"❌ 오류: {e}"


HEADER_HTML = """
<div id="sf-header">
  <div style="display:flex; align-items:center; gap:10px; font-size:20px; font-weight:700; color:#00C9A7;">
    <span style="font-size:26px;">🎮</span> SkinForge AI
  </div>
  <button style="background:transparent; border:1px solid #333; color:#aaa; padding:6px 14px; border-radius:6px; font-size:13px; cursor:pointer; font-family:inherit;">
    📋 사용 가이드
  </button>
</div>
"""

with gr.Blocks(css=CSS, title="SkinForge AI") as demo:
    gr.HTML(HEADER_HTML)

    with gr.Row():
        with gr.Column(elem_id="left-col"):
            photo_input = gr.Image(
                type="pil",
                label="upload",
                elem_id="upload-wrap",
            )
            generate_btn = gr.Button("✨ 스킨 생성하기", elem_id="gen-btn")
            status_output = gr.Textbox(
                label="status",
                interactive=False,
                elem_id="status-box",
                placeholder="사진을 업로드하고 스킨 생성하기를 누르세요",
            )

        with gr.Column(elem_id="right-col"):
            viewer_output = gr.HTML(value=VIEWER_EMPTY, elem_id="viewer-html")
            with gr.Row(elem_id="bottom-row"):
                uv_btn = gr.Button("📐 UV 맵 보기", elem_id="uv-btn")
                dl_btn = gr.Button("⬇️ PNG 다운로드", elem_id="dl-btn")
            dl_file = gr.File(label="dl", elem_id="dl-file", visible=False)

    generate_btn.click(
        fn=process,
        inputs=[photo_input],
        outputs=[viewer_output, dl_file, status_output],
    )

    dl_btn.click(fn=None, js="""
    () => {
      const link = document.querySelector('#dl-file a');
      if (link) link.click();
      else alert('먼저 스킨을 생성해주세요.');
    }
    """)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
