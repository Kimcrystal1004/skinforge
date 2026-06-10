"""
app.py — SkinForge AI
"""

import os
import io
import base64
from dotenv import load_dotenv
from PIL import Image
import gradio as gr

load_dotenv()

from core.feature_extractor import extract_features
from core.skin_generator import generate_skin
from core.skin_validator import validate_and_fix

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
    min-height: 340px !important;
    height: 340px !important;
    width: 100% !important;
    box-sizing: border-box !important;
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

/* ── 업로드 영역 이미지 맞춤 ── */
#upload-wrap img {
    width: 100% !important; height: 100% !important;
    object-fit: contain !important; max-height: 340px !important;
}
#upload-wrap .preview-image,
#upload-wrap [data-testid="image"] {
    height: 340px !important; max-height: 340px !important; overflow: hidden !important;
}

/* ── 스킨 생성하기 버튼 ── */
#gen-btn button {
    display: block !important;
    width: 100% !important;
    height: 48px !important;
    line-height: 48px !important;
    padding: 0 !important;
    border-radius: 10px !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    background: #00C9A7 !important;
    color: #000 !important;
    border: none !important;
    box-shadow: 0 4px 20px rgba(0,201,167,.35) !important;
    cursor: pointer !important;
    transition: all .2s !important;
}
#gen-btn button:hover {
    background: #00ddb8 !important;
    box-shadow: 0 6px 28px rgba(0,201,167,.55) !important;
    transform: translateY(-1px) !important;
}

/* ── 상태 박스 완전 숨김 ── */
#status-box { display: none !important; }

/* ── 결과 박스 ── */
#result-box { background: transparent !important; padding: 0 !important; border: none !important; }

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



def make_2d_preview(skin_img: Image.Image) -> list:
    """64×64 스킨 → [앞, 오른쪽, 뒤, 왼쪽] 4방향 PIL Image 리스트. 실패 시 fallback 1장."""
    try:
        import numpy as np
        S = 10
        BG = (14, 14, 14, 255)
        arr = np.array(skin_img.convert("RGBA"), dtype=np.uint8)

        def crop(x, y, w, h):
            return Image.fromarray(arr[y:y+h, x:x+w], "RGBA")

        def up(img):
            return img.resize((img.width * S, img.height * S), Image.NEAREST)

        def alpha_over(base, over):
            b = base.copy().convert("RGBA")
            b.alpha_composite(over.convert("RGBA"))
            return b

        def compose(hd, hat, bd, ra, la, rl, ll, bw=8):
            cw = (4 + bw + 4) * S
            ch = 32 * S
            cv = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            hx = (cw - 8*S) // 2
            bx = (cw - bw*S) // 2
            hcomp = alpha_over(up(hd), up(hat))
            cv.paste(hcomp,  (hx,       0),    hcomp)
            cv.paste(up(bd), (bx,       8*S),  up(bd))
            cv.paste(up(ra), (bx-4*S,   8*S),  up(ra))
            cv.paste(up(la), (bx+bw*S,  8*S),  up(la))
            cv.paste(up(rl), (bx,       20*S), up(rl))
            cv.paste(up(ll), (bx+4*S,   20*S), up(ll))
            # 투명 배경 → 어두운 배경으로
            bg = Image.new("RGB", cv.size, BG[:3])
            bg.paste(cv.convert("RGB"), mask=cv.split()[3])
            return bg

        return [
            compose(crop(8,8,8,8),  crop(40,8,8,8),  crop(20,20,8,12),
                    crop(44,20,4,12), crop(36,52,4,12),
                    crop(4,20,4,12),  crop(20,52,4,12)),
            compose(crop(16,8,8,8), crop(48,8,8,8),  crop(28,20,4,12),
                    crop(48,20,4,12), crop(40,52,4,12),
                    crop(8,20,4,12),  crop(24,52,4,12), bw=4),
            compose(crop(24,8,8,8), crop(56,8,8,8),  crop(32,20,8,12),
                    crop(52,20,4,12), crop(44,52,4,12),
                    crop(12,20,4,12), crop(28,52,4,12)),
            compose(crop(0,8,8,8),  crop(32,8,8,8),  crop(16,20,4,12),
                    crop(40,20,4,12), crop(32,52,4,12),
                    crop(0,20,4,12),  crop(16,52,4,12), bw=4),
        ]

    except Exception as e:
        print(f"[preview] 미리보기 생성 실패, fallback 사용: {e}")
        import traceback; traceback.print_exc()
        return [skin_img.convert("RGB").resize((320, 320), Image.NEAREST)]


_RESULT_EMPTY = """
<div style="background:#111;border-radius:16px;border:1px solid #1a1a1a;
    padding:20px;display:flex;flex-direction:column;gap:14px;">
  <div style="background:#0a0a0a;border-radius:12px;border:1px solid #181818;
      height:280px;display:flex;align-items:center;justify-content:center;">
    <div style="text-align:center;">
      <div style="font-size:36px;opacity:.2;">🧱</div>
      <p style="color:#444;font-size:13px;margin:8px 0 0;">
        스킨을 생성하면 미리보기가 표시됩니다
      </p>
    </div>
  </div>
  <span style="display:block;background:#1e1e1e;color:#444;border:1px solid #2a2a2a;
      font-size:15px;font-weight:700;height:48px;line-height:48px;
      border-radius:10px;text-align:center;box-sizing:border-box;cursor:not-allowed;">
    ⬇️ PNG 다운로드
  </span>
</div>
"""

def make_result_html(view_imgs: list, skin_img: Image.Image) -> str:
    """캐러셀 미리보기(앞→오른→뒤→왼) + 다운로드 버튼"""
    labels = ["앞", "오른쪽", "뒤", "왼쪽"]

    imgs_js = []
    for img in view_imgs:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        imgs_js.append(base64.b64encode(buf.getvalue()).decode())

    imgs_json = "[" + ",".join(f'"{b}"' for b in imgs_js) + "]"
    labels_json = "[" + ",".join(f'"{l}"' for l in labels[:len(view_imgs)]) + "]"

    sb = io.BytesIO()
    skin_img.save(sb, format="PNG")
    skin_b64 = base64.b64encode(sb.getvalue()).decode()

    return f"""
<div style="background:#111;border-radius:16px;border:1px solid #1a1a1a;
    padding:20px;display:flex;flex-direction:column;gap:14px;">

  <!-- 캐러셀 -->
  <div style="position:relative;background:#0a0a0a;border-radius:12px;
      border:1px solid #181818;overflow:hidden;user-select:none;">

    <!-- 방향 라벨 -->
    <div id="sf-label"
         style="position:absolute;top:10px;left:50%;transform:translateX(-50%);
                background:rgba(0,0,0,.55);color:#00C9A7;font-size:12px;
                font-weight:700;padding:3px 12px;border-radius:20px;z-index:2;
                font-family:sans-serif;">앞</div>

    <!-- 이미지 -->
    <img id="sf-img"
         src="data:image/png;base64,{imgs_js[0]}"
         style="width:100%;height:auto;image-rendering:pixelated;display:block;"
         alt="skin preview">

    <!-- 왼쪽 화살표 -->
    <button onclick="sfNav(-1)"
      style="position:absolute;left:8px;top:50%;transform:translateY(-50%);
             background:rgba(0,0,0,.5);border:1px solid #333;color:#ccc;
             width:36px;height:36px;border-radius:50%;font-size:18px;
             cursor:pointer;z-index:2;display:flex;align-items:center;
             justify-content:center;padding:0;">&#8592;</button>

    <!-- 오른쪽 화살표 -->
    <button onclick="sfNav(1)"
      style="position:absolute;right:8px;top:50%;transform:translateY(-50%);
             background:rgba(0,0,0,.5);border:1px solid #333;color:#ccc;
             width:36px;height:36px;border-radius:50%;font-size:18px;
             cursor:pointer;z-index:2;display:flex;align-items:center;
             justify-content:center;padding:0;">&#8594;</button>

    <!-- 인디케이터 -->
    <div id="sf-dots"
         style="position:absolute;bottom:8px;left:50%;transform:translateX(-50%);
                display:flex;gap:6px;z-index:2;"></div>
  </div>

  <!-- 다운로드 버튼 -->
  <a href="data:image/png;base64,{skin_b64}"
     download="skinforge_skin.png"
     style="display:block;background:#00C9A7;color:#000;text-decoration:none;
            font-size:15px;font-weight:700;height:48px;line-height:48px;
            border-radius:10px;text-align:center;box-sizing:border-box;
            cursor:pointer;box-shadow:0 4px 16px rgba(0,201,167,.3);"
     onmouseover="this.style.background='#00ddb8'"
     onmouseout="this.style.background='#00C9A7'">
    ⬇️ PNG 다운로드
  </a>
</div>

<script>
(function(){{
  var imgs   = {imgs_json};
  var labels = {labels_json};
  var idx    = 0;

  var imgEl   = document.getElementById('sf-img');
  var lblEl   = document.getElementById('sf-label');
  var dotsEl  = document.getElementById('sf-dots');

  // 인디케이터 점 생성
  labels.forEach(function(_, i) {{
    var d = document.createElement('div');
    d.style.cssText = 'width:7px;height:7px;border-radius:50%;background:' +
                      (i===0 ? '#00C9A7' : 'rgba(255,255,255,.3)') + ';transition:background .2s;';
    dotsEl.appendChild(d);
  }});

  function update() {{
    imgEl.src   = 'data:image/png;base64,' + imgs[idx];
    lblEl.textContent = labels[idx];
    Array.from(dotsEl.children).forEach(function(d, i) {{
      d.style.background = i === idx ? '#00C9A7' : 'rgba(255,255,255,.3)';
    }});
  }}

  window.sfNav = function(dir) {{
    idx = (idx + dir + imgs.length) % imgs.length;
    update();
  }};
}})();
</script>
"""


def process(photo: Image.Image):
    if photo is None:
        return _RESULT_EMPTY, "⚠️ 사진을 업로드해 주세요."
    try:
        features = extract_features(photo)
        tone  = features.get("skin_tone", "warm_bright")
        status = (f"✅ 피부톤: {tone} | "
                  f"헤어: {features.get('hair_color')} {features.get('hair_style')} | "
                  f"상의: {features.get('top_style')}")

        skin_img = generate_skin(features)
        skin_img, is_valid, errors = validate_and_fix(skin_img)
        if not is_valid:
            status += f" | ⚠️ {errors}"

        view_imgs = make_2d_preview(skin_img)
        print(f"[skinforge] 생성 완료 | {status}")
        return make_result_html(view_imgs, skin_img), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        err_html = f"""
<div style="background:#111;border-radius:16px;border:1px solid #2a1a1a;
    padding:20px;color:#f66;font-size:13px;">
  ❌ 오류: {e}
</div>"""
        return err_html, f"❌ 오류: {e}"


with gr.Blocks(css=CSS, title="SkinForge AI", theme=theme) as demo:
    gr.HTML(HEADER_HTML)

    with gr.Row(equal_height=False):
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
                show_label=False, visible=True,
            )

        with gr.Column(scale=1, min_width=300):
            result_html = gr.HTML(value=_RESULT_EMPTY, elem_id="result-box")

    generate_btn.click(
        fn=process,
        inputs=[photo_input],
        outputs=[result_html, status_output],
        show_progress="minimal",
    )

if __name__ == "__main__":
    user = os.environ.get("APP_USER", "admin")
    pw   = os.environ.get("APP_PW",   "skinforge")
    demo.queue(default_concurrency_limit=2)
    demo.launch(server_name="0.0.0.0", server_port=7860,
                auth=(user, pw), auth_message="SkinForge AI — 접근 권한이 필요합니다",
                max_file_size="20mb")
