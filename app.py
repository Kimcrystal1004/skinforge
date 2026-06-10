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
    """64×64 스킨 → 앞/뒤/좌/우 4방향 2D 미리보기. 실패 시 raw 스킨 fallback."""
    try:
        import numpy as np
        S = 10
        BG = (14, 14, 14)
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
            return cv

        views = [
            compose(crop(8,8,8,8),  crop(40,8,8,8),  crop(20,20,8,12),
                    crop(44,20,4,12), crop(36,52,4,12),
                    crop(4,20,4,12),  crop(20,52,4,12)),
            compose(crop(24,8,8,8), crop(56,8,8,8),  crop(32,20,8,12),
                    crop(52,20,4,12), crop(44,52,4,12),
                    crop(12,20,4,12), crop(28,52,4,12)),
            compose(crop(0,8,8,8),  crop(32,8,8,8),  crop(16,20,4,12),
                    crop(40,20,4,12), crop(32,52,4,12),
                    crop(0,20,4,12),  crop(16,52,4,12), bw=4),
            compose(crop(16,8,8,8), crop(48,8,8,8),  crop(28,20,4,12),
                    crop(48,20,4,12), crop(40,52,4,12),
                    crop(8,20,4,12),  crop(24,52,4,12), bw=4),
        ]

        PAD = 10
        total_w = sum(v.width for v in views) + PAD * (len(views) + 1)
        total_h = max(v.height for v in views) + PAD * 2
        result = Image.new("RGB", (total_w, total_h), BG)
        x = PAD
        for v in views:
            result.paste(v.convert("RGB"), (x, PAD), v)
            x += v.width + PAD
        return result

    except Exception as e:
        print(f"[preview] 미리보기 생성 실패, fallback 사용: {e}")
        import traceback; traceback.print_exc()
        return skin_img.convert("RGB").resize((512, 512), Image.NEAREST)


_DL_BTN_STYLE = (
    "display:block;background:#00C9A7;color:#000 !important;border:none;"
    "font-size:15px;font-weight:700;height:48px;line-height:48px;padding:0;"
    "border-radius:10px;width:100%;box-shadow:0 4px 16px rgba(0,201,167,.3);"
    "text-decoration:none !important;text-align:center;box-sizing:border-box;"
    "cursor:pointer !important;transition:background .2s;"
)
_DL_DIS_STYLE = (
    "display:block;background:#1e1e1e;color:#444;border:1px solid #2a2a2a;"
    "font-size:15px;font-weight:700;height:48px;line-height:48px;padding:0;"
    "border-radius:10px;width:100%;text-align:center;box-sizing:border-box;"
    "cursor:not-allowed;"
)

DL_EMPTY = f'<span style="{_DL_DIS_STYLE}">⬇️ PNG 다운로드</span>'

def make_dl_html(skin_b64: str) -> str:
    return (
        f'<a href="data:image/png;base64,{skin_b64}" download="skinforge_skin.png"'
        f' style="{_DL_BTN_STYLE}"'
        f' onmouseover="this.style.background=\'#00ddb8\'"'
        f' onmouseout="this.style.background=\'#00C9A7\'">⬇️ PNG 다운로드</a>'
    )


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
        return PREVIEW_EMPTY, DL_EMPTY, f"❌ 오류: {e}"


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
            dl_btn = gr.HTML(value=DL_EMPTY, elem_id="dl-btn")

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
