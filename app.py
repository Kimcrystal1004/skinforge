"""
app.py — SkinForge AI
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

*, *::before, *::after { box-sizing: border-box; }

body, .gradio-container {
    background: #0a0a0a !important;
    color: #e0e0e0 !important;
    font-family: 'Inter', sans-serif !important;
    margin: 0 !important; padding: 0 !important;
}
.gradio-container { max-width: 100% !important; }
footer, .built-with { display: none !important; }
.main.svelte-1kyws56 { padding: 0 !important; }

/* ── upload ── */
#upload-wrap .wrap {
    border: 2px dashed #00C9A7 !important;
    border-radius: 16px !important;
    background: #111 !important;
    min-height: 320px !important;
    transition: background .2s !important;
}
#upload-wrap .wrap:hover { background: #161616 !important; }
#upload-wrap svg { color: #00C9A7 !important; width: 48px !important; height: 48px !important; }
#upload-wrap .upload-text span { color: #888 !important; font-size: 14px !important; }
#upload-wrap > label.svelte-116rqfv { display: none !important; }

/* ── generate button ── */
#gen-btn button {
    background: linear-gradient(135deg, #00C9A7, #00a888) !important;
    color: #000 !important; font-weight: 700 !important;
    font-size: 16px !important; letter-spacing: .3px !important;
    border-radius: 12px !important; border: none !important;
    width: 100% !important; padding: 15px !important;
    box-shadow: 0 4px 20px rgba(0,201,167,.25) !important;
    transition: all .2s !important; cursor: pointer !important;
}
#gen-btn button:hover {
    background: linear-gradient(135deg, #00ddb8, #00C9A7) !important;
    box-shadow: 0 6px 28px rgba(0,201,167,.4) !important;
    transform: translateY(-1px) !important;
}
#gen-btn button:active { transform: translateY(0) !important; }

/* ── status ── */
#status-box > label { display: none !important; }
#status-box textarea {
    background: #0f0f0f !important; border: 1px solid #1e1e1e !important;
    border-radius: 8px !important; color: #777 !important;
    font-size: 12px !important; min-height: 32px !important;
    padding: 8px 12px !important; resize: none !important;
}

/* ── bottom buttons ── */
#uv-btn button, #dl-btn button {
    background: #131313 !important; color: #bbb !important;
    border: 1px solid #252525 !important; border-radius: 10px !important;
    font-size: 14px !important; font-weight: 500 !important;
    width: 100% !important; padding: 13px !important;
    transition: all .2s !important; cursor: pointer !important;
}
#uv-btn button:hover, #dl-btn button:hover {
    border-color: #00C9A7 !important; color: #00C9A7 !important;
    background: #0f1f1c !important;
}

#dl-file { display: none !important; }

/* ── modal ── */
#guide-modal {
    display: none; position: fixed; inset: 0;
    background: rgba(0,0,0,.75); z-index: 9999;
    justify-content: center; align-items: center;
}
#guide-modal.open { display: flex; }
#guide-box {
    background: #141414; border: 1px solid #252525;
    border-radius: 16px; padding: 32px; max-width: 480px; width: 90%;
}
#guide-box h2 { color: #00C9A7; margin: 0 0 20px; font-size: 18px; }
#guide-box ol { color: #bbb; line-height: 2; padding-left: 20px; margin: 0 0 24px; }
#guide-box ol li { font-size: 14px; }
#guide-close {
    background: #00C9A7; color: #000; border: none;
    border-radius: 8px; padding: 10px 24px; font-weight: 700;
    cursor: pointer; float: right; font-family: inherit;
}
"""

HEADER_HTML = """
<div style="display:flex;align-items:center;justify-content:space-between;
    padding:16px 32px;background:#111;border-bottom:1px solid #1a1a1a;">
  <div style="display:flex;align-items:center;gap:10px;
      font-size:20px;font-weight:700;color:#00C9A7;">
    <span style="font-size:28px;">🎮</span> SkinForge AI
  </div>
  <button onclick="document.getElementById('guide-modal').classList.add('open')"
      style="background:transparent;border:1px solid #2a2a2a;color:#aaa;
      padding:7px 16px;border-radius:8px;font-size:13px;cursor:pointer;font-family:inherit;">
    📋 사용 가이드
  </button>
</div>

<div id="guide-modal">
  <div id="guide-box">
    <h2>📋 SkinForge AI 사용 가이드</h2>
    <ol>
      <li>인물이 잘 보이는 <b>전신 사진</b>을 준비하세요</li>
      <li>왼쪽 업로드 영역에 <b>사진을 드래그</b>하거나 클릭하여 업로드</li>
      <li><b>✨ 스킨 생성하기</b> 버튼 클릭</li>
      <li>Gemini AI가 분석 후 <b>64×64 마인크래프트 스킨</b>을 생성합니다 (약 30초)</li>
      <li>오른쪽 3D 뷰어에서 미리보기 후 <b>PNG 다운로드</b></li>
      <li>마인크래프트 → 프로필 → 스킨 변경에서 적용!</li>
    </ol>
    <button id="guide-close"
        onclick="document.getElementById('guide-modal').classList.remove('open')">
      확인
    </button>
  </div>
</div>
"""

VIEWER_EMPTY = """
<div style="background:#111;border-radius:16px;padding:20px;
    border:1px solid #1a1a1a;height:100%;min-height:420px;
    display:flex;flex-direction:column;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
    <span style="color:#aaa;font-size:14px;font-weight:600;">3D 미리보기</span>
    <span style="color:#444;font-size:12px;">🎮 Minecraft Java Edition</span>
  </div>
  <div style="flex:1;display:flex;justify-content:center;align-items:center;
      background:#0a0a0a;border-radius:12px;border:1px solid #181818;">
    <div style="text-align:center;">
      <div style="font-size:40px;margin-bottom:12px;opacity:.3;">🧱</div>
      <span style="color:#444;font-size:13px;">스킨을 생성하면<br>3D 미리보기가 표시됩니다</span>
    </div>
  </div>
  <div style="display:flex;justify-content:center;gap:8px;margin-top:14px;">
    <button disabled style="background:#0f0f0f;border:1px solid #1e1e1e;color:#333;
        padding:9px 28px;border-radius:8px;font-size:15px;cursor:not-allowed;">←</button>
    <button disabled style="background:#0f0f0f;border:1px solid #1e1e1e;color:#333;
        padding:9px 28px;border-radius:8px;font-size:15px;cursor:not-allowed;">⬜</button>
    <button disabled style="background:#0f0f0f;border:1px solid #1e1e1e;color:#333;
        padding:9px 28px;border-radius:8px;font-size:15px;cursor:not-allowed;">→</button>
  </div>
</div>
"""

def make_viewer_html(skin_b64: str) -> str:
    return f"""
<div style="background:#111;border-radius:16px;padding:20px;
    border:1px solid #1a1a1a;height:100%;min-height:420px;
    display:flex;flex-direction:column;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
    <span style="color:#aaa;font-size:14px;font-weight:600;">3D 미리보기</span>
    <span style="color:#444;font-size:12px;">🎮 Minecraft Java Edition</span>
  </div>
  <div id="sv-wrap" style="flex:1;background:#0a0a0a;border-radius:12px;
      border:1px solid #181818;overflow:hidden;min-height:300px;">
    <canvas id="skinCanvas" style="width:100%;height:100%;display:block;"></canvas>
  </div>
  <div style="display:flex;justify-content:center;gap:8px;margin-top:14px;">
    <button onclick="if(window._sv)window._sv.playerObject.rotation.y-=0.4"
        style="background:#131313;border:1px solid #252525;color:#ccc;
        padding:9px 28px;border-radius:8px;font-size:15px;cursor:pointer;">←</button>
    <button onclick="if(window._sv){{window._sv.playerObject.rotation.y=0;window._sv.autoRotate=!window._sv.autoRotate;}}"
        style="background:#131313;border:1px solid #252525;color:#ccc;
        padding:9px 28px;border-radius:8px;font-size:15px;cursor:pointer;">⏸</button>
    <button onclick="if(window._sv)window._sv.playerObject.rotation.y+=0.4"
        style="background:#131313;border:1px solid #252525;color:#ccc;
        padding:9px 28px;border-radius:8px;font-size:15px;cursor:pointer;">→</button>
  </div>
</div>
<script src="https://unpkg.com/skinview3d@2.1.1/bundles/skinview3d.bundle.js"></script>
<script>
(function() {{
  function init() {{
    const canvas = document.getElementById('skinCanvas');
    if (!canvas || typeof skinview3d === 'undefined') {{ setTimeout(init, 300); return; }}
    const wrap = document.getElementById('sv-wrap');
    const viewer = new skinview3d.SkinViewer({{
      canvas: canvas,
      width: wrap.clientWidth || 340,
      height: wrap.clientHeight || 320,
      skin: "data:image/png;base64,{skin_b64}"
    }});
    viewer.renderer.setClearColor(0x0a0a0a, 1);
    viewer.autoRotate = true;
    viewer.autoRotateSpeed = 0.6;
    viewer.zoom = 0.85;
    window._sv = viewer;
  }}
  setTimeout(init, 400);
}})();
</script>
"""


def process(photo: Image.Image):
    if photo is None:
        return VIEWER_EMPTY, None, "⚠️ 사진을 업로드해 주세요."
    try:
        features = extract_features(photo)
        tone = features.get("skin_tone", "warm_bright")
        status = f"✅ 피부톤: {tone} | 헤어: {features.get('hair_color')} {features.get('hair_style')} | 상의: {features.get('top_style')}"

        skin_img = generate_skin(features)
        skin_img, is_valid, errors = validate_and_fix(skin_img)
        if not is_valid:
            status += f" | ⚠️ 보정: {errors}"

        tmp = tempfile.NamedTemporaryFile(suffix=".png", dir=OUTPUT_DIR, delete=False)
        skin_img.save(tmp.name, format="PNG")

        with open(tmp.name, "rb") as f:
            skin_b64 = base64.b64encode(f.read()).decode()

        return make_viewer_html(skin_b64), tmp.name, status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return VIEWER_EMPTY, None, f"❌ 오류: {e}"


with gr.Blocks(css=CSS, title="SkinForge AI") as demo:
    gr.HTML(HEADER_HTML)

    with gr.Row(equal_height=True):
        # 왼쪽 패널
        with gr.Column(scale=1, min_width=300):
            gr.HTML("<div style='height:16px'></div>")
            photo_input = gr.Image(
                type="pil",
                label="upload",
                elem_id="upload-wrap",
                show_label=False,
            )
            gr.HTML("<div style='height:10px'></div>")
            generate_btn = gr.Button("✨ 스킨 생성하기", elem_id="gen-btn")
            status_output = gr.Textbox(
                label="status", interactive=False,
                elem_id="status-box", show_label=False,
                placeholder="사진을 업로드하고 스킨 생성하기를 누르세요",
            )
            gr.HTML("<div style='height:8px'></div>")

        # 오른쪽 패널
        with gr.Column(scale=1, min_width=300):
            gr.HTML("<div style='height:16px'></div>")
            viewer_output = gr.HTML(value=VIEWER_EMPTY)
            with gr.Row():
                uv_btn = gr.Button("📐 UV 맵 보기", elem_id="uv-btn")
                dl_btn = gr.Button("⬇️ PNG 다운로드", elem_id="dl-btn")
            dl_file = gr.File(label="dl", elem_id="dl-file", visible=False)
            gr.HTML("<div style='height:8px'></div>")

    generate_btn.click(
        fn=process,
        inputs=[photo_input],
        outputs=[viewer_output, dl_file, status_output],
    )

    dl_btn.click(fn=None, js="""
    () => {
      const a = document.querySelector('#dl-file a');
      if (a) { a.click(); }
      else { alert('먼저 스킨을 생성해 주세요.'); }
    }
    """)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
