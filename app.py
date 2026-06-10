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

/* ── 버튼 공통 (생성 & 다운로드 동일 크기) ── */
#gen-btn button, #dl-btn a, #dl-btn-disabled span {
    display: block !important;
    width: 100% !important;
    height: 48px !important;
    line-height: 48px !important;
    padding: 0 !important;
    border-radius: 10px !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    text-align: center !important;
    box-sizing: border-box !important;
    transition: all .2s !important;
    cursor: pointer !important;
}
#gen-btn button {
    background: #00C9A7 !important;
    color: #000 !important;
    border: none !important;
    box-shadow: 0 4px 20px rgba(0,201,167,.35) !important;
}
#gen-btn button:hover {
    background: #00ddb8 !important;
    box-shadow: 0 6px 28px rgba(0,201,167,.55) !important;
    transform: translateY(-1px) !important;
}
#dl-btn a {
    background: #00C9A7 !important;
    color: #000 !important;
    border: none !important;
    text-decoration: none !important;
    box-shadow: 0 4px 16px rgba(0,201,167,.3) !important;
}
#dl-btn a:hover { background: #00ddb8 !important; }
#dl-btn-disabled span {
    background: #1a1a1a !important;
    color: #444 !important;
    border: 1px solid #2a2a2a !important;
    cursor: not-allowed !important;
    box-shadow: none !important;
}

/* ── 상태 박스 완전 숨김 ── */
#status-box { display: none !important; }

/* ── 2D 미리보기 ── */
#preview-img { background: transparent !important; border: none !important; }
#preview-img img { border-radius: 12px !important; image-rendering: pixelated !important; }

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

PREVIEW_EMPTY = None   # gr.Image(value=None) 로 빈 상태 표시


def make_2d_preview(skin_img: Image.Image) -> Image.Image:
    """64×64 스킨 → 앞/뒤/좌/우 4방향 2D 미리보기 이미지"""
    import numpy as np
    SCALE = 10
    S = SCALE
    BG = (14, 14, 14, 255)

    arr = np.array(skin_img.convert("RGBA"), dtype=np.uint8)

    def crop(x, y, w, h):
        return Image.fromarray(arr[y:y+h, x:x+w], "RGBA")

    def up(img):
        return img.resize((img.width * S, img.height * S), Image.NEAREST)

    def alpha_over(base, overlay):
        r = base.copy().convert("RGBA")
        r.alpha_composite(overlay.convert("RGBA"))
        return r

    # ── UV 영역 정의 ───────────────────────────────────────────────
    faces = dict(
        # HEAD
        hf=crop(8,8,8,8),   hb=crop(24,8,8,8),
        hr=crop(0,8,8,8),   hl=crop(16,8,8,8),
        # HAT overlay
        hatf=crop(40,8,8,8), hatb=crop(56,8,8,8),
        hatr=crop(32,8,8,8), hatl=crop(48,8,8,8),
        # BODY
        bf=crop(20,20,8,12), bb=crop(32,20,8,12),
        br=crop(16,20,4,12), bl=crop(28,20,4,12),
        # RIGHT ARM
        raf=crop(44,20,4,12), rab=crop(52,20,4,12),
        rar=crop(40,20,4,12), ral=crop(48,20,4,12),
        # LEFT ARM
        laf=crop(36,52,4,12), lab=crop(44,52,4,12),
        lar=crop(32,52,4,12), lal=crop(40,52,4,12),
        # RIGHT LEG
        rlf=crop(4,20,4,12),  rlb=crop(12,20,4,12),
        rlr=crop(0,20,4,12),  rll=crop(8,20,4,12),
        # LEFT LEG
        llf=crop(20,52,4,12), llb=crop(28,52,4,12),
        llr=crop(16,52,4,12), lll=crop(24,52,4,12),
    )

    def compose(head, hat, body, ra, la, rl, ll, body_w=8):
        """body_w: 8 for front/back, 4 for side views"""
        cw = (4 + body_w + 4) * S
        ch = 32 * S
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        head_x = ((cw - 8 * S) // 2)
        body_x = ((cw - body_w * S) // 2)
        ra_x   = body_x - 4 * S
        la_x   = body_x + body_w * S
        rl_x   = body_x
        ll_x   = body_x + 4 * S

        h_comp = alpha_over(up(head), up(hat))
        canvas.paste(h_comp,    (head_x, 0),      h_comp)
        canvas.paste(up(body),  (body_x, 8*S),    up(body))
        canvas.paste(up(ra),    (ra_x,   8*S),    up(ra))
        canvas.paste(up(la),    (la_x,   8*S),    up(la))
        canvas.paste(up(rl),    (rl_x,   20*S),   up(rl))
        canvas.paste(up(ll),    (ll_x,   20*S),   up(ll))
        return canvas

    views = [
        ("앞",  compose(faces["hf"], faces["hatf"], faces["bf"],  faces["raf"], faces["laf"], faces["rlf"], faces["llf"])),
        ("뒤",  compose(faces["hb"], faces["hatb"], faces["bb"],  faces["rab"], faces["lab"], faces["rlb"], faces["llb"])),
        ("오른쪽", compose(faces["hr"], faces["hatr"], faces["br"],  faces["rar"], faces["lar"], faces["rlr"], faces["llr"], body_w=4)),
        ("왼쪽",  compose(faces["hl"], faces["hatl"], faces["bl"],  faces["ral"], faces["lal"], faces["rll"], faces["lll"], body_w=4)),
    ]

    # ── 레이블 영역 ──────────────────────────────────────────────
    try:
        from PIL import ImageDraw, ImageFont
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
    except Exception:
        font = None

    LABEL_H = 22
    PAD = 12
    total_w = sum(v[1].width for v in views) + PAD * (len(views) + 1)
    max_h = max(v[1].height for v in views)
    result = Image.new("RGBA", (total_w, max_h + LABEL_H + PAD), BG)

    x = PAD
    for label, img in views:
        result.paste(img, (x, LABEL_H), img)
        if font:
            draw = ImageDraw.Draw(result)
            tw = draw.textlength(label, font=font)
            draw.text((x + (img.width - tw) / 2, 4), label, fill=(160, 160, 160, 255), font=font)
        x += img.width + PAD

    return result.convert("RGB")


def make_dl_html(skin_b64: str) -> str:
    return f"""
<a href="data:image/png;base64,{skin_b64}" download="skinforge_skin.png"
   style="display:block;background:#00C9A7;color:#000;border:none;font-size:15px;
   font-weight:700;height:48px;line-height:48px;padding:0;border-radius:10px;width:100%;
   box-shadow:0 4px 16px rgba(0,201,167,.3);text-decoration:none;
   text-align:center;box-sizing:border-box;transition:all .2s;"
   onmouseover="this.style.background='#00ddb8'"
   onmouseout="this.style.background='#00C9A7'">
  ⬇️ PNG 다운로드
</a>"""


def process(photo: Image.Image):
    if photo is None:
        return PREVIEW_EMPTY, "", "⚠️ 사진을 업로드해 주세요."
    try:
        features = extract_features(photo)
        tone = features.get("skin_tone", "warm_bright")
        status = f"✅ 피부톤: {tone} | 헤어: {features.get('hair_color')} {features.get('hair_style')} | 상의: {features.get('top_style')}"

        skin_img = generate_skin(features)
        skin_img, is_valid, errors = validate_and_fix(skin_img)
        if not is_valid:
            status += f" | ⚠️ {errors}"

        preview_img = make_2d_preview(skin_img)

        b = io.BytesIO()
        skin_img.save(b, format="PNG")
        buf = base64.b64encode(b.getvalue()).decode()

        print(f"[skinforge] 생성 완료 | {status}")
        return preview_img, make_dl_html(buf), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return PREVIEW_EMPTY, "", f"❌ 오류: {e}"


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
                show_label=False, visible=False,
            )

        with gr.Column(scale=1, min_width=300):
            preview_output = gr.Image(
                value=None, label="미리보기 (앞 / 뒤 / 오른쪽 / 왼쪽)",
                show_label=True, interactive=False,
                elem_id="preview-img",
            )
            dl_btn = gr.HTML(value="", elem_id="dl-btn")

    generate_btn.click(
        fn=process,
        inputs=[photo_input],
        outputs=[preview_output, dl_btn, status_output],
        show_progress="minimal",
    )

if __name__ == "__main__":
    user = os.environ.get("APP_USER", "admin")
    pw   = os.environ.get("APP_PW",   "skinforge")
    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=7860,
                auth=(user, pw), auth_message="SkinForge AI — 접근 권한이 필요합니다")
