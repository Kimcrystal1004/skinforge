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

TEAL = gr.themes.Color(
    c50="#e6fff9", c100="#ccfff3", c200="#99ffe7", c300="#66ffdb",
    c400="#33ffcf", c500="#00C9A7", c600="#00a888", c700="#008870",
    c800="#006858", c900="#004840", c950="#002820",
)

theme = gr.themes.Base(
    primary_hue=TEAL,
    neutral_hue="slate",
    font=gr.themes.GoogleFont("Inter"),
).set(
    body_background_fill="#0a0a0a",
    body_text_color="#e0e0e0",
    block_background_fill="#111111",
    block_border_color="#1e1e1e",
    button_primary_background_fill="#00C9A7",
    button_primary_background_fill_hover="#00ddb8",
    button_primary_text_color="#000000",
    button_secondary_background_fill="transparent",
    button_secondary_background_fill_hover="#0f1f1c",
    button_secondary_text_color="#00C9A7",
    button_secondary_border_color="#00C9A7",
    input_background_fill="#111111",
    input_border_color="#1e1e1e",
)

CSS = """
footer, .built-with { display: none !important; }

/* ── 바깥 흰 박스 제거 ── */
#upload-wrap,
#upload-wrap > .block,
#upload-wrap > div > .block,
.gradio-image { background: transparent !important; border: none !important; padding: 0 !important; box-shadow: none !important; }

/* ── 업로드 드롭존 (민트 테두리만) ── */
#upload-wrap .wrap {
    border: 2px dashed #00C9A7 !important;
    border-radius: 16px !important;
    background: #0d0d0d !important;
    min-height: 380px !important;
}
#upload-wrap .wrap:hover { background: #111 !important; }
#upload-wrap svg { color: #00C9A7 !important; }
#upload-wrap .upload-text span { color: #aaa !important; }

/* ── 안쪽 폰모양 네모 제거 ── */
#upload-wrap .wrap > .upload-container,
#upload-wrap .wrap > div:first-child:not(.upload-text),
.svelte-ozuaqz, .svelte-1ipelgc { display: none !important; }

/* ── 카메라·클립보드 아이콘 제거 ── */
#upload-wrap .source-selection,
#upload-wrap [data-testid="source-select"] { display: none !important; }

/* ── 스킨 생성하기 버튼 ── */
#gen-btn button {
    background: #00C9A7 !important;
    color: #000 !important;
    border: none !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    padding: 15px !important;
    border-radius: 12px !important;
    width: 100% !important;
    box-shadow: 0 4px 20px rgba(0,201,167,.35) !important;
    transition: all .2s !important;
}
#gen-btn button:hover {
    background: #00ddb8 !important;
    box-shadow: 0 6px 28px rgba(0,201,167,.55) !important;
    transform: translateY(-1px) !important;
}

/* ── 상태 박스 완전 숨김 ── */
#status-box { display: none !important; }

/* ── PNG 다운로드 버튼 ── */
#dl-btn button, #dl-btn a {
    background: #00C9A7 !important;
    color: #000 !important;
    border: none !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    padding: 13px !important;
    border-radius: 10px !important;
    width: 100% !important;
    box-shadow: 0 4px 16px rgba(0,201,167,.3) !important;
    transition: all .2s !important;
    text-decoration: none !important;
    display: block !important;
    text-align: center !important;
}
#dl-btn button:hover, #dl-btn a:hover {
    background: #00ddb8 !important;
}

/* ── 업로드 영역 너비 = 버튼과 동일 ── */
#upload-wrap .wrap {
    width: 100% !important;
}

/* ── 뷰어 ── */
#viewer-html { background: transparent !important; padding: 0 !important; }

/* ── 전체 블록 배경 투명 ── */
.gradio-container > .main > .wrap > .gap > div > .block {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
}
"""

HEADER_HTML = """
<div style="display:flex;align-items:center;justify-content:space-between;
    padding:16px 32px;background:#111;border-bottom:1px solid #1a1a1a;margin-bottom:8px;">
  <div style="display:flex;align-items:center;gap:10px;font-size:20px;font-weight:700;color:#00C9A7;">
    <span style="font-size:26px;">🎮</span> SkinForge AI
  </div>
  <button onclick="document.getElementById('gm').style.display='flex'"
    style="background:transparent;border:1px solid #2a2a2a;color:#aaa;padding:7px 16px;
    border-radius:8px;font-size:13px;cursor:pointer;font-family:inherit;">
    📋 사용 가이드
  </button>
</div>
<div id="gm" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.8);
    z-index:9999;justify-content:center;align-items:center;">
  <div style="background:#141414;border:1px solid #252525;border-radius:16px;
      padding:32px;max-width:460px;width:90%;">
    <h2 style="color:#00C9A7;margin:0 0 20px;font-size:18px;">📋 사용 가이드</h2>
    <ol style="color:#bbb;line-height:2.2;padding-left:20px;margin:0 0 24px;font-size:14px;">
      <li>인물이 잘 보이는 <b style="color:#e0e0e0;">전신 사진</b>을 준비하세요</li>
      <li>왼쪽 업로드 영역에 사진을 드래그하거나 클릭해 업로드</li>
      <li><b style="color:#00C9A7;">✨ 스킨 생성하기</b> 버튼 클릭</li>
      <li>Gemini AI가 분석 후 64×64 스킨을 생성합니다 <span style="color:#555;">(약 30초)</span></li>
      <li>3D 뷰어에서 미리보기 후 PNG 다운로드</li>
      <li>마인크래프트 → 프로필 → 스킨 변경에서 적용!</li>
    </ol>
    <button onclick="document.getElementById('gm').style.display='none'"
      style="background:#00C9A7;color:#000;border:none;border-radius:8px;
      padding:10px 28px;font-weight:700;cursor:pointer;font-size:14px;font-family:inherit;float:right;">
      확인
    </button>
  </div>
</div>
"""

VIEWER_EMPTY = """
<div style="background:#111;border-radius:16px;padding:20px;border:1px solid #1a1a1a;
    min-height:380px;display:flex;flex-direction:column;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
    <span style="color:#aaa;font-size:14px;font-weight:600;">3D 미리보기</span>
    <span style="color:#444;font-size:12px;">🎮 Minecraft Java Edition</span>
  </div>
  <div style="flex:1;display:flex;justify-content:center;align-items:center;
      background:#0a0a0a;border-radius:12px;border:1px solid #181818;min-height:280px;">
    <div style="text-align:center;">
      <div style="font-size:36px;margin-bottom:10px;opacity:.25;">🧱</div>
      <span style="color:#444;font-size:13px;">스킨을 생성하면<br>3D 미리보기가 표시됩니다</span>
    </div>
  </div>
  <div style="display:flex;justify-content:center;gap:8px;margin-top:14px;">
    <button disabled style="background:#0f0f0f;border:1px solid #1e1e1e;color:#333;
        padding:9px 28px;border-radius:8px;font-size:15px;">←</button>
    <button disabled style="background:#0f0f0f;border:1px solid #1e1e1e;color:#333;
        padding:9px 28px;border-radius:8px;font-size:15px;">⏸</button>
    <button disabled style="background:#0f0f0f;border:1px solid #1e1e1e;color:#333;
        padding:9px 28px;border-radius:8px;font-size:15px;">→</button>
  </div>
</div>
"""

def make_viewer_html(skin_b64: str) -> str:
    return f"""
<div style="background:#111;border-radius:16px;padding:20px;border:1px solid #1a1a1a;
    min-height:380px;display:flex;flex-direction:column;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
    <span style="color:#aaa;font-size:14px;font-weight:600;">3D 미리보기</span>
    <span style="color:#444;font-size:12px;">🎮 Minecraft Java Edition</span>
  </div>
  <div id="sv-wrap" style="flex:1;background:#0a0a0a;border-radius:12px;
      border:1px solid #181818;overflow:hidden;min-height:280px;position:relative;">
    <canvas id="skinCanvas" style="position:absolute;inset:0;width:100%;height:100%;"></canvas>
  </div>
  <div style="display:flex;justify-content:center;gap:8px;margin-top:14px;">
    <button onclick="if(window._sv)window._sv.playerObject.rotation.y-=0.4"
      style="background:#131313;border:1px solid #252525;color:#ccc;
      padding:9px 28px;border-radius:8px;font-size:15px;cursor:pointer;">←</button>
    <button onclick="if(window._sv)window._sv.autoRotate=!window._sv.autoRotate"
      style="background:#131313;border:1px solid #252525;color:#ccc;
      padding:9px 28px;border-radius:8px;font-size:15px;cursor:pointer;">⏸</button>
    <button onclick="if(window._sv)window._sv.playerObject.rotation.y+=0.4"
      style="background:#131313;border:1px solid #252525;color:#ccc;
      padding:9px 28px;border-radius:8px;font-size:15px;cursor:pointer;">→</button>
  </div>
</div>
<script>
(function() {{
  var SKIN = "data:image/png;base64,{skin_b64}";
  function tryLoad() {{
    if (typeof skinview3d === 'undefined') {{
      var s = document.createElement('script');
      s.src = 'https://unpkg.com/skinview3d@2.1.1/bundles/skinview3d.bundle.js';
      s.onload = initViewer;
      document.head.appendChild(s);
    }} else {{ initViewer(); }}
  }}
  function initViewer() {{
    var wrap = document.getElementById('sv-wrap');
    var canvas = document.getElementById('skinCanvas');
    if (!wrap || !canvas) {{ setTimeout(initViewer, 300); return; }}
    try {{
      var v = new skinview3d.SkinViewer({{
        canvas: canvas,
        width: wrap.offsetWidth || 300,
        height: wrap.offsetHeight || 280,
        skin: SKIN
      }});
      v.renderer.setClearColor(0x0a0a0a, 1);
      v.autoRotate = true;
      v.autoRotateSpeed = 0.6;
      v.zoom = 0.85;
      window._sv = v;
    }} catch(e) {{ setTimeout(initViewer, 500); }}
  }}
  setTimeout(tryLoad, 200);
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
            status += f" | ⚠️ {errors}"

        tmp = tempfile.NamedTemporaryFile(
            suffix=".png", dir=OUTPUT_DIR, delete=False, prefix="skin_"
        )
        skin_img.save(tmp.name, format="PNG")

        with open(tmp.name, "rb") as f:
            skin_b64 = base64.b64encode(f.read()).decode()

        print(f"[skinforge] 생성 완료: {tmp.name} | {status}")
        return make_viewer_html(skin_b64), tmp.name, status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return VIEWER_EMPTY, None, f"❌ 오류: {e}"


with gr.Blocks(css=CSS, title="SkinForge AI", theme=theme) as demo:
    gr.HTML(HEADER_HTML)

    with gr.Row(equal_height=True):
        with gr.Column(scale=1, min_width=300):
            photo_input = gr.Image(
                type="pil", label="사진 업로드",
                elem_id="upload-wrap", show_label=False,
            )
            generate_btn = gr.Button(
                "✨ 스킨 생성하기", variant="primary", elem_id="gen-btn",
            )
            status_output = gr.Textbox(
                label="상태", interactive=False, elem_id="status-box",
                show_label=False, visible=False,
            )

        with gr.Column(scale=1, min_width=300):
            viewer_output = gr.HTML(value=VIEWER_EMPTY, elem_id="viewer-html")
            dl_btn = gr.DownloadButton(
                "⬇️ PNG 다운로드", elem_id="dl-btn", variant="primary",
            )

    generate_btn.click(
        fn=process,
        inputs=[photo_input],
        outputs=[viewer_output, dl_btn, status_output],
        show_progress="minimal",
    )

if __name__ == "__main__":
    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=7860)
