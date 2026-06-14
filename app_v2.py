"""
app_v2.py — SkinForge AI v2
완전 재설계: 모든 JS는 gr.Blocks(js=...)에만, CSS는 정적 CSS만 사용
"""

import os, io, base64
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image
import gradio as gr

load_dotenv()

from core.feature_extractor import extract_features
from core.skin_generator import generate_skin
from core.skin_validator import validate_and_fix

# ══════════════════════════════════════════════════════════════════════
# 이미지 → base64 data URL
# ══════════════════════════════════════════════════════════════════════
_D = Path(__file__).parent

def _b64(p: Path) -> str:
    ext = p.suffix.lstrip('.').lower()
    if ext == 'jpg': ext = 'jpeg'
    return f"data:image/{ext};base64," + base64.b64encode(p.read_bytes()).decode()

BG_DAY   = _b64(_D / "background_d.png")
BG_NIGHT = _b64(_D / "background_n.png")
IMG_BG   = _b64(_D / "img_background.png")
BTN_BG   = _b64(_D / "button_background.png")
GRASS    = _b64(_D / "grass_block.png")
LEVELS   = [_b64(_D / f"level{i}.png") for i in range(5)]

# ══════════════════════════════════════════════════════════════════════
# 2D 미리보기 (기존 코드)
# ══════════════════════════════════════════════════════════════════════
def make_2d_preview(skin_img: Image.Image) -> list:
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

        def compose(hd, hat, bd, ra, la, rl, ll, bw=8, side=False):
            cw = (4 + bw + 4) * S if not side else (8 + bw) * S
            ch = 32 * S
            cv = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            hx = (cw - 8*S) // 2
            bx = (cw - bw*S) // 2
            hcomp = alpha_over(up(hd), up(hat))
            cv.paste(hcomp,  (hx,    0),   hcomp)
            cv.paste(up(bd), (bx,  8*S),   up(bd))
            if not side:
                cv.paste(up(ra), (bx-4*S,  8*S), up(ra))
                cv.paste(up(la), (bx+bw*S, 8*S), up(la))
            cv.paste(up(rl), (bx, 20*S), up(rl))
            if not side:
                cv.paste(up(ll), (bx+4*S, 20*S), up(ll))
            bg = Image.new("RGB", cv.size, BG[:3])
            bg.paste(cv.convert("RGB"), mask=cv.split()[3])
            return bg

        return [
            compose(crop(8,8,8,8),  crop(40,8,8,8),  crop(20,20,8,12),
                    crop(44,20,4,12), crop(36,52,4,12), crop(4,20,4,12),  crop(20,52,4,12)),
            compose(crop(16,8,8,8), crop(48,8,8,8),  crop(28,20,4,12),
                    crop(48,20,4,12), crop(40,52,4,12), crop(8,20,4,12),  crop(24,52,4,12), bw=4, side=True),
            compose(crop(24,8,8,8), crop(56,8,8,8),  crop(32,20,8,12),
                    crop(52,20,4,12), crop(44,52,4,12), crop(12,20,4,12), crop(28,52,4,12)),
            compose(crop(0,8,8,8),  crop(32,8,8,8),  crop(16,20,4,12),
                    crop(40,20,4,12), crop(32,52,4,12), crop(0,20,4,12),  crop(16,52,4,12), bw=4, side=True),
        ]
    except Exception:
        buf = io.BytesIO()
        skin_img.convert("RGB").save(buf, "PNG")
        return [Image.open(io.BytesIO(buf.getvalue()))]


# ══════════════════════════════════════════════════════════════════════
# 결과 HTML
# ══════════════════════════════════════════════════════════════════════
_RESULT_EMPTY = f"""<div id="result-inner"
  style="width:100%;height:100%;
    display:flex;flex-direction:column;
    align-items:center;justify-content:center;
    background:transparent;box-sizing:border-box;">
  <img src="{LEVELS[0]}" style="width:56px;opacity:0.5;image-rendering:pixelated;">
  <p style="color:#aaa;font-size:13px;margin:12px 0 0;text-align:center;
    text-shadow:1px 1px 0 #000;">스킨을 생성하면 미리보기가 표시됩니다</p>
</div>"""

def make_result_html(view_imgs: list, skin_img: Image.Image) -> str:
    labels = ["앞", "오른쪽", "뒤", "왼쪽"]
    n = len(view_imgs)

    imgs_b64 = []
    for img in view_imgs:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        imgs_b64.append(base64.b64encode(buf.getvalue()).decode())

    sb = io.BytesIO()
    skin_img.save(sb, format="PNG")
    skin_b64 = base64.b64encode(sb.getvalue()).decode()

    # 숨겨진 데이터 (DOMPurify가 span/data는 허용)
    hidden = "".join(
        f'<span id="sfi{i}" style="display:none">{imgs_b64[i]}</span>'
        for i in range(n)
    )
    # 점 인디케이터 — onclick 없이 data-idx만 (event delegation)
    dots = "".join(
        f'<span class="sf-dot" data-idx="{i}" style="'
        f'display:inline-block;width:8px;height:8px;border-radius:50%;cursor:pointer;'
        f'background:{"#00C9A7" if i==0 else "rgba(255,255,255,.3)"};'
        f'transition:background .2s;"></span>'
        for i in range(n)
    )

    return f"""<div id="result-inner" style="width:100%;height:100%;position:relative;box-sizing:border-box;">
  {hidden}
  <span id="sf-skin-b64" style="display:none">{skin_b64}</span>
  <span id="sf-n-slides" style="display:none">{n}</span>

  <div id="sfwrap" data-idx="0"
    style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;position:relative;">

    <img id="sfimg" src="data:image/png;base64,{imgs_b64[0]}"
      style="max-width:82%;max-height:82%;object-fit:contain;image-rendering:pixelated;display:block;">

    <span class="sf-nav-btn" data-dir="-1"
      style="position:absolute;left:6px;top:50%;transform:translateY(-50%);
        background:rgba(0,0,0,.55);color:#fff;font-size:20px;cursor:pointer;
        padding:4px 9px;border-radius:3px;user-select:none;line-height:1;">&#8249;</span>
    <span class="sf-nav-btn" data-dir="1"
      style="position:absolute;right:6px;top:50%;transform:translateY(-50%);
        background:rgba(0,0,0,.55);color:#fff;font-size:20px;cursor:pointer;
        padding:4px 9px;border-radius:3px;user-select:none;line-height:1;">&#8250;</span>

    <div style="position:absolute;bottom:8px;left:0;right:0;
      display:flex;flex-direction:column;align-items:center;gap:5px;">
      <span id="sflbl" style="color:#ddd;font-size:12px;text-shadow:0 1px 3px #000;">{labels[0]}</span>
      <div style="display:flex;gap:5px;">{dots}</div>
    </div>
  </div>
</div>"""


# ══════════════════════════════════════════════════════════════════════
# AI 처리 함수
# ══════════════════════════════════════════════════════════════════════
def process(photo: Image.Image):
    if photo is None:
        return _RESULT_EMPTY, ""
    try:
        features = extract_features(photo)
        skin_img = generate_skin(features)
        skin_img, is_valid, errors = validate_and_fix(skin_img)
        view_imgs = make_2d_preview(skin_img)
        return make_result_html(view_imgs, skin_img), "done"
    except Exception as e:
        import traceback; traceback.print_exc()
        return _RESULT_EMPTY, f"error:{e}"


# ══════════════════════════════════════════════════════════════════════
# CSS (정적 — 항상 적용됨)
# ══════════════════════════════════════════════════════════════════════
CSS = f"""
/* ── 기본 리셋 ── */
footer, .built-with {{ display:none !important; }}
.gradio-container {{ padding:0 !important; margin:0 !important; min-height:100vh !important; }}
.gradio-container > .main {{ padding:0 !important; }}
.gradio-container > .main > .wrap {{ padding:0 !important; gap:0 !important; }}

/* ── 배경 ── */
:root {{
  --sf-bg: url('{BG_DAY}');
  --sf-bg-night: url('{BG_NIGHT}');
  --img-bg: url('{IMG_BG}');
  --btn-bg: url('{BTN_BG}');
}}
body, .gradio-container {{
  background-image: var(--sf-bg) !important;
  background-size: cover !important;
  background-position: center !important;
  background-attachment: fixed !important;
  background-repeat: no-repeat !important;
}}

/* ── 블록 투명화 ── */
.gradio-container .block {{
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
}}
.gradio-container .gap {{ gap: 0 !important; }}

/* ── 헤더 ── */
#sf-header {{
  width: 100%;
  background: rgba(20,20,20,0.85);
  border-bottom: 2px solid #111;
  box-sizing: border-box;
  padding: 10px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}

/* ── 메인 컨테이너 ── */
#sf-main {{
  display: flex;
  align-items: flex-start;
  justify-content: center;
  gap: 0;
  padding: 24px 16px 0;
  width: 100%;
  box-sizing: border-box;
}}

/* ── 업로드/결과 박스 컬럼 ── */
.sf-col {{
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}}

/* ── 이미지 박스 (업로드 & 결과) ── */
.sf-box {{
  width: 360px;
  height: 360px;
  background-image: var(--img-bg);
  background-size: 100% 100%;
  background-repeat: no-repeat;
  position: relative;
  box-sizing: border-box;
  overflow: hidden;
  flex-shrink: 0;
}}

/* ── gr.Image 스타일링 ── */
#upload-wrap {{
  width: 100% !important;
  height: 100% !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin: 0 !important;
  position: absolute !important;
  top: 0 !important; left: 0 !important;
}}
#upload-wrap > div, #upload-wrap .wrap,
#upload-wrap .upload-container, #upload-wrap [data-testid="image"] {{
  width: 100% !important;
  height: 100% !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin: 0 !important;
}}
/* 업로드 전: 드롭 영역 투명 */
#upload-wrap .upload-container > label,
#upload-wrap .drop-target {{
  background: transparent !important;
  border: 2px dashed rgba(255,255,255,0.2) !important;
  box-shadow: none !important;
}}
/* 업로드 후: 이미지 비율 유지하며 박스 안에 맞춤 */
#upload-wrap img:not(.sf-placeholder) {{
  max-width: 100% !important;
  max-height: 100% !important;
  width: auto !important;
  height: auto !important;
  object-fit: contain !important;
  position: absolute !important;
  top: 50% !important; left: 50% !important;
  transform: translate(-50%, -50%) !important;
  image-rendering: auto !important;
}}
/* 소스 선택 버튼 숨김 */
#upload-wrap .source-selection,
#upload-wrap [data-testid="source-select"] {{ display: none !important; }}

/* ── 결과 박스 ── */
#result-box {{
  width: 100% !important; height: 100% !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin: 0 !important;
  position: absolute !important;
  top: 0 !important; left: 0 !important;
}}
#result-box > div {{
  width: 100% !important;
  height: 100% !important;
  padding: 0 !important;
  margin: 0 !important;
}}

/* ── 액션 버튼 ── */
.sf-btn {{
  width: 460px;
  max-width: 100%;
  aspect-ratio: 10 / 1;
  background-image: var(--btn-bg);
  background-size: 100% 100%;
  background-repeat: no-repeat;
  border: none;
  cursor: pointer;
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  text-shadow: 2px 2px 0 #000, -1px -1px 0 #000;
  letter-spacing: 1px;
  transition: filter 0.1s;
  display: block;
  flex-shrink: 0;
}}
.sf-btn:hover  {{ filter: brightness(1.15); }}
.sf-btn:active {{ filter: brightness(0.75); }}

/* ── 화살표 컬럼 ── */
#sf-arrow-col {{
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  flex-shrink: 0;
  align-self: center;
  margin-top: -44px; /* 버튼 높이 절반만큼 올림 */
}}

/* ── 숨겨진 Gradio 버튼 ── */
#gen-btn {{
  position: absolute !important;
  left: -9999px !important;
  opacity: 0 !important;
  pointer-events: none !important;
  height: 0 !important;
  overflow: hidden !important;
}}
#status-out {{ display: none !important; }}

/* ── 하단 가이드 버튼 ── */
#sf-bottom {{
  display: flex;
  justify-content: center;
  padding: 20px 0 32px;
}}

/* ── 모달 ── */
#sf-modal-overlay {{
  display: none;
  position: fixed;
  top: 0; left: 0; width: 100%; height: 100%;
  background: rgba(0,0,0,0.75);
  z-index: 9999;
  align-items: center;
  justify-content: center;
}}
#sf-modal-overlay.open {{ display: flex; }}
#sf-modal {{
  background: #3c3c3c;
  border: 3px solid #1a1a1a;
  box-shadow: inset 0 0 0 2px #666, 5px 5px 0 #000;
  width: 500px;
  max-width: 92vw;
  border-radius: 2px;
  overflow: hidden;
}}
"""

# ══════════════════════════════════════════════════════════════════════
# HTML 상수
# ══════════════════════════════════════════════════════════════════════
HEADER_HTML = f"""<div id="sf-header">
  <div style="display:flex;align-items:center;gap:12px;">
    <img src="{GRASS}" style="width:52px;height:52px;image-rendering:pixelated;flex-shrink:0;">
    <span style="color:#fff;font-size:22px;font-weight:900;
      text-shadow:3px 3px 0 #000,-1px -1px 0 #333;letter-spacing:1px;">SkinForge AI</span>
  </div>
  <div style="display:flex;align-items:center;gap:6px;
    background:rgba(0,0,0,0.4);padding:6px 12px;border:1px solid #444;border-radius:3px;">
    <span style="color:#aaa;font-size:12px;font-weight:700;margin-right:4px;">배경</span>
    <button id="sf-btn-day"
      style="background:#00C9A7;color:#000;border:none;padding:4px 14px;
        font-size:13px;font-weight:700;cursor:pointer;border-radius:2px;">낮</button>
    <button id="sf-btn-night"
      style="background:rgba(255,255,255,.1);color:#fff;border:1px solid #555;
        padding:4px 14px;font-size:13px;font-weight:700;cursor:pointer;border-radius:2px;">밤</button>
  </div>
</div>"""

ARROW_HTML = f"""<div id="sf-arrow-col">
  <img id="sf-arrow-img" src="{LEVELS[0]}"
    style="width:64px;image-rendering:pixelated;display:block;">
</div>"""

GEN_BTN_HTML = f"""<button id="sf-gen-btn" class="sf-btn">스킨 생성하기</button>"""
DL_BTN_HTML  = f"""<button id="sf-dl-btn" class="sf-btn">PNG 저장하기</button>"""

GUIDE_BTN_HTML = f"""<button id="sf-guide-btn"
  style="background:none;border:none;cursor:pointer;
    display:flex;flex-direction:column;align-items:center;gap:6px;padding:8px;">
  <img src="{GRASS}" style="width:48px;image-rendering:pixelated;">
  <span style="color:#fff;font-size:14px;font-weight:700;
    text-shadow:2px 2px 0 #000;">사용 가이드</span>
</button>"""

MODAL_HTML = f"""<div id="sf-modal-overlay">
  <div id="sf-modal">
    <div style="background:#2a2a2a;padding:12px 16px;
      display:flex;align-items:center;justify-content:space-between;
      border-bottom:2px solid #1a1a1a;">
      <div style="display:flex;align-items:center;gap:8px;">
        <img src="{GRASS}" style="width:26px;image-rendering:pixelated;">
        <span style="color:#fff;font-weight:700;font-size:15px;">사용 가이드</span>
      </div>
      <button id="sf-modal-close"
        style="background:none;border:none;color:#999;font-size:22px;cursor:pointer;
          line-height:1;padding:0 4px;">&#x2715;</button>
    </div>
    <div style="padding:16px;color:#ccc;font-size:13px;line-height:1.65;">
      <p style="margin:0 0 14px;color:#bbb;">
        SkinForge AI는 당신의 사진을 AI로 분석해<br>마인크래프트 64×64 스킨을 자동 생성합니다.
      </p>
      <div style="display:flex;flex-direction:column;gap:6px;">
        <div style="display:flex;align-items:flex-start;gap:10px;background:#2a2a2a;padding:9px 12px;">
          <span style="background:#555;color:#fff;font-weight:700;font-size:11px;
            padding:2px 7px;border-radius:2px;flex-shrink:0;">1</span>
          <span><b style="color:#fff;">전신이 잘 보이는 사진</b>을 준비하세요.</span>
        </div>
        <div style="display:flex;align-items:flex-start;gap:10px;background:#2a2a2a;padding:9px 12px;">
          <span style="background:#555;color:#fff;font-weight:700;font-size:11px;
            padding:2px 7px;border-radius:2px;flex-shrink:0;">2</span>
          <span><b style="color:#fff;">왼쪽 업로드 영역</b>에 사진을 드래그하거나 클릭해 업로드하세요.</span>
        </div>
        <div style="display:flex;align-items:flex-start;gap:10px;background:#2a2a2a;padding:9px 12px;">
          <span style="background:#555;color:#fff;font-weight:700;font-size:11px;
            padding:2px 7px;border-radius:2px;flex-shrink:0;">3</span>
          <span><b style="color:#fff;">스킨 생성하기</b> 버튼을 클릭하세요. AI 분석에 약 20~40초 소요됩니다.</span>
        </div>
        <div style="display:flex;align-items:flex-start;gap:10px;background:#2a2a2a;padding:9px 12px;">
          <span style="background:#555;color:#fff;font-weight:700;font-size:11px;
            padding:2px 7px;border-radius:2px;flex-shrink:0;">4</span>
          <span>미리보기 확인 후 &#11015; <b style="color:#fff;">PNG 저장하기</b>. 마음에 안 들면 다시 생성해보세요!</span>
        </div>
        <div style="display:flex;align-items:flex-start;gap:10px;background:#2a2a2a;padding:9px 12px;">
          <span style="background:#555;color:#fff;font-weight:700;font-size:11px;
            padding:2px 7px;border-radius:2px;flex-shrink:0;">5</span>
          <span>마인크래프트 &#8594; <b style="color:#fff;">스킨 변경</b>에서 다운로드한 PNG를 적용하면 완료!</span>
        </div>
      </div>
      <p style="margin:14px 0 0;padding:10px 12px;
        background:#2a1f00;border-left:3px solid #f9a825;
        color:#f9a825;font-size:12px;">
        &#128161; TIP: 단색 배경, 정면 포즈 사진이 가장 정확한 스킨을 만들어냅니다.
      </p>
    </div>
  </div>
</div>"""


# ══════════════════════════════════════════════════════════════════════
# JS — gr.Blocks(js=...) 에만 넣기 (항상 실행됨)
# ══════════════════════════════════════════════════════════════════════
# level 이미지 URL들을 JS에 직접 embed
_LEVELS_JS = "[" + ",".join(f'"{u}"' for u in LEVELS) + "]"

JS = f"""
() => {{

/* ─────────────────────────────────────────
   낮 / 밤 배경 전환
───────────────────────────────────────── */
function initTheme() {{
  var d = document.getElementById('sf-btn-day');
  var n = document.getElementById('sf-btn-night');
  if (!d || !n) {{ setTimeout(initTheme, 300); return; }}
  if (d._sfBound) return;
  d._sfBound = true;

  function setDay() {{
    document.documentElement.style.removeProperty('--sf-bg');
    d.style.cssText = 'background:#00C9A7;color:#000;border:none;padding:4px 14px;font-size:13px;font-weight:700;cursor:pointer;border-radius:2px;';
    n.style.cssText = 'background:rgba(255,255,255,.1);color:#fff;border:1px solid #555;padding:4px 14px;font-size:13px;font-weight:700;cursor:pointer;border-radius:2px;';
  }}
  function setNight() {{
    document.documentElement.style.setProperty('--sf-bg', 'var(--sf-bg-night)');
    n.style.cssText = 'background:#00C9A7;color:#000;border:none;padding:4px 14px;font-size:13px;font-weight:700;cursor:pointer;border-radius:2px;';
    d.style.cssText = 'background:rgba(255,255,255,.1);color:#fff;border:1px solid #555;padding:4px 14px;font-size:13px;font-weight:700;cursor:pointer;border-radius:2px;';
  }}
  d.addEventListener('click', setDay);
  n.addEventListener('click', setNight);
}}
setTimeout(initTheme, 400);


/* ─────────────────────────────────────────
   화살표 애니메이션
───────────────────────────────────────── */
var LEVELS = {_LEVELS_JS};
var _arrowTimer = null;
var _arrowStep  = 0;

function arrowSet(step) {{
  var img = document.getElementById('sf-arrow-img');
  if (img) img.src = LEVELS[Math.min(step, 4)];
  _arrowStep = step;
}}

function arrowStart() {{
  arrowSet(0);
  if (_arrowTimer) clearInterval(_arrowTimer);
  _arrowTimer = setInterval(function() {{
    if (_arrowStep < 4) arrowSet(_arrowStep + 1);
  }}, 6000); // 6초마다 한 단계씩 (총 ~30초)
}}

function arrowDone() {{
  if (_arrowTimer) {{ clearInterval(_arrowTimer); _arrowTimer = null; }}
  arrowSet(4);
  setTimeout(function() {{ arrowSet(0); }}, 2500);
}}


/* ─────────────────────────────────────────
   스킨 생성하기 버튼
───────────────────────────────────────── */
function initGenBtn() {{
  var btn = document.getElementById('sf-gen-btn');
  if (!btn) {{ setTimeout(initGenBtn, 300); return; }}
  if (btn._sfBound) return;
  btn._sfBound = true;

  btn.addEventListener('click', function() {{
    var gb = document.querySelector('#gen-btn button') || document.querySelector('#gen-btn');
    if (!gb) return;
    arrowStart();
    gb.click();
  }});
}}
setTimeout(initGenBtn, 500);


/* ─────────────────────────────────────────
   결과 감지 → 화살표 완료
───────────────────────────────────────── */
function watchResult() {{
  var box = document.getElementById('result-box');
  if (!box) {{ setTimeout(watchResult, 400); return; }}
  var _generating = false;

  new MutationObserver(function() {{
    if (document.getElementById('sf-skin-b64')) {{
      arrowDone();
      _generating = false;
    }}
  }}).observe(box, {{ childList: true, subtree: true }});
}}
setTimeout(watchResult, 800);


/* ─────────────────────────────────────────
   PNG 저장하기 버튼
───────────────────────────────────────── */
function initDlBtn() {{
  var btn = document.getElementById('sf-dl-btn');
  if (!btn) {{ setTimeout(initDlBtn, 300); return; }}
  if (btn._sfBound) return;
  btn._sfBound = true;

  btn.addEventListener('click', function() {{
    var span = document.getElementById('sf-skin-b64');
    if (!span || !span.textContent.trim()) {{
      alert('먼저 스킨을 생성해주세요.');
      return;
    }}
    var a = document.createElement('a');
    a.href = 'data:image/png;base64,' + span.textContent.trim();
    a.download = 'skinforge_skin.png';
    a.click();
  }});
}}
setTimeout(initDlBtn, 500);


/* ─────────────────────────────────────────
   캐러셀 (event delegation — onclick 불필요)
───────────────────────────────────────── */
var _sfN = 4;

function sfSlide(dir) {{
  var wrap = document.getElementById('sfwrap');
  if (!wrap) return;
  var n = parseInt(document.getElementById('sf-n-slides').textContent || '4');
  var idx = (parseInt(wrap.dataset.idx || '0') + dir + n) % n;
  wrap.dataset.idx = idx;
  var span = document.getElementById('sfi' + idx);
  if (span) document.getElementById('sfimg').src = 'data:image/png;base64,' + span.textContent.trim();
  var labels = ['앞','오른쪽','뒤','왼쪽'];
  var lbl = document.getElementById('sflbl');
  if (lbl) lbl.textContent = labels[idx] || '';
  document.querySelectorAll('.sf-dot').forEach(function(d, i) {{
    d.style.background = (i === idx) ? '#00C9A7' : 'rgba(255,255,255,.3)';
  }});
}}

document.addEventListener('click', function(e) {{
  var nav = e.target.closest('.sf-nav-btn');
  if (nav) {{ sfSlide(parseInt(nav.dataset.dir)); return; }}
  var dot = e.target.closest('.sf-dot');
  if (dot) {{
    var wrap = document.getElementById('sfwrap');
    if (wrap) {{
      var cur = parseInt(wrap.dataset.idx || '0');
      var target = parseInt(dot.dataset.idx);
      sfSlide(target - cur);
    }}
  }}
}});


/* ─────────────────────────────────────────
   사용 가이드 모달
───────────────────────────────────────── */
function initModal() {{
  var openBtn  = document.getElementById('sf-guide-btn');
  var closeBtn = document.getElementById('sf-modal-close');
  var overlay  = document.getElementById('sf-modal-overlay');
  if (!openBtn || !closeBtn || !overlay) {{ setTimeout(initModal, 300); return; }}
  if (openBtn._sfBound) return;
  openBtn._sfBound = true;

  openBtn.addEventListener('click', function() {{
    overlay.classList.add('open');
  }});
  closeBtn.addEventListener('click', function() {{
    overlay.classList.remove('open');
  }});
  overlay.addEventListener('click', function(e) {{
    if (e.target === overlay) overlay.classList.remove('open');
  }});
}}
setTimeout(initModal, 500);


/* ─────────────────────────────────────────
   Ctrl+Enter → 생성
───────────────────────────────────────── */
document.addEventListener('keydown', function(e) {{
  if (e.ctrlKey && e.key === 'Enter') {{
    e.preventDefault();
    var btn = document.getElementById('sf-gen-btn');
    if (btn) btn.click();
  }}
}});

}}
"""


# ══════════════════════════════════════════════════════════════════════
# Gradio 레이아웃
# ══════════════════════════════════════════════════════════════════════
with gr.Blocks(css=CSS, title="SkinForge AI", js=JS) as demo:

    # 헤더
    gr.HTML(HEADER_HTML)

    # 메인 영역 (커스텀 HTML로 레이아웃 제어)
    gr.HTML(f"""<div id="sf-main">

  <!-- 왼쪽: 업로드 컬럼 -->
  <div class="sf-col">
    <div class="sf-box">""")

    photo_input = gr.Image(
        type="pil", show_label=False,
        elem_id="upload-wrap",
        height=360, width=360,
    )

    gr.HTML("""    </div>""")
    gr.HTML(GEN_BTN_HTML)
    gr.HTML("""  </div>""")

    # 가운데: 화살표
    gr.HTML(ARROW_HTML)

    # 오른쪽: 결과 컬럼
    gr.HTML("""  <div class="sf-col">
    <div class="sf-box">""")

    result_html = gr.HTML(
        value=_RESULT_EMPTY,
        elem_id="result-box",
    )

    gr.HTML("""    </div>""")
    gr.HTML(DL_BTN_HTML)
    gr.HTML("""  </div>

</div>""")  # /sf-main

    # 하단: 사용 가이드
    gr.HTML(f"""<div id="sf-bottom">{GUIDE_BTN_HTML}</div>""")

    # 모달
    gr.HTML(MODAL_HTML)

    # 숨겨진 Gradio 버튼 (실제 처리 트리거)
    generate_btn = gr.Button("generate", elem_id="gen-btn", visible=True)
    status_out   = gr.Textbox(visible=False, elem_id="status-out")

    generate_btn.click(
        fn=process,
        inputs=[photo_input],
        outputs=[result_html, status_out],
        show_progress="minimal",
    )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", 7860)),
        show_api=False,
    )
