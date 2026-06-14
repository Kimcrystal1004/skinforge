import re, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('app.py', 'r', encoding='utf-8') as f:
    src = f.read()

changes = 0

# ═══════════════════════════════════════════════════════════════════
# 1. sanitize_html=False 제거 (서버 Gradio 버전이 지원 안 함 → 크래시)
# ═══════════════════════════════════════════════════════════════════
OLD1 = 'gr.HTML(sanitize_html=False, value="""<script>\n(function(){'
NEW1 = 'gr.HTML(value="""<script>\n(function(){'
if OLD1 in src:
    src = src.replace(OLD1, NEW1, 1)
    changes += 1
    print("OK 1: sanitize_html=False removed")
else:
    print("FAIL 1: sanitize_html=False not found (already removed?)")

# ═══════════════════════════════════════════════════════════════════
# 2. 야간 배경 b64를 CSS --sf-bg-night 변수로 이동
#    (스크립트 태그가 실행 안 돼도 CSS는 항상 적용됨)
# ═══════════════════════════════════════════════════════════════════
m = re.search(r"window\._SFBG_N='(data:image/jpeg;base64,[A-Za-z0-9+/=\n\r]+)'", src)
if m:
    night_b64 = m.group(1).replace('\n', '').replace('\r', '')
    print(f"OK 2: Found night bg base64 ({len(night_b64)} chars)")

    # CSS 끝부분에 --sf-bg-night 추가
    # ':root {' 또는 ':root{' 찾기
    root_match = re.search(r':root\s*\{[^}]*\}', src)
    if root_match:
        old_root = root_match.group(0)
        # 이미 --sf-bg-night가 있으면 스킵
        if '--sf-bg-night' not in src:
            new_root = old_root.rstrip('}') + f"\n  --sf-bg-night: url('{night_b64}');\n}}"
            src = src.replace(old_root, new_root, 1)
            changes += 1
            print("OK 2b: --sf-bg-night added to :root CSS")
        else:
            print("OK 2b: --sf-bg-night already in CSS (skipped)")
            changes += 1
    else:
        print("FAIL 2b: :root block not found in CSS")
else:
    print("FAIL 2: window._SFBG_N not found")

# ═══════════════════════════════════════════════════════════════════
# 3. _CTRL_ENTER_JS에 핵심 함수 추가
#    (gr.Blocks(js=...) 는 항상 실행됨)
# ═══════════════════════════════════════════════════════════════════
# patch14 이후 _CTRL_ENTER_JS의 첫 줄
OLD3_MARKER = '() => {\n    /* Ctrl+Enter */'
if OLD3_MARKER not in src:
    print("FAIL 3: _CTRL_ENTER_JS marker not found")
else:
    EXTRA_JS = """\
    /* ─ 헬퍼 ─ */
    function sp(el,p,v){ el.style.setProperty(p,v,'important'); }

    /* ─ 배경 낮/밤 전환 ─ */
    window.sfSetBG = function(mode) {
        if (mode === 'night') {
            document.documentElement.style.setProperty('--sf-bg', 'var(--sf-bg-night)');
        } else {
            document.documentElement.style.removeProperty('--sf-bg');
        }
    };

    /* ─ 업로드박스 배경이미지 DOM 주입 ─ */
    function injectUploadBg() {
        var el = document.getElementById('upload-wrap');
        var bg = document.getElementById('upload-bg-frame');
        if (!el || !bg) { setTimeout(injectUploadBg, 400); return; }
        var bi = bg.querySelector('img');
        if (!bi || !bi.src) { setTimeout(injectUploadBg, 400); return; }
        var imgSrc = bi.src;
        function ensureBg() {
            if (document.getElementById('sf-upload-bg-img')) return;
            var img = document.createElement('img');
            img.id = 'sf-upload-bg-img';
            img.src = imgSrc;
            sp(img,'position','absolute');
            sp(img,'top','0'); sp(img,'left','0');
            sp(img,'width','100%'); sp(img,'height','100%');
            sp(img,'z-index','-1');
            sp(img,'pointer-events','none');
            sp(img,'image-rendering','pixelated');
            sp(img,'display','block');
            el.appendChild(img);
        }
        ensureBg();
        new MutationObserver(function(){ ensureBg(); }).observe(el, {childList:true});
    }
    setTimeout(injectUploadBg, 600);

    /* ─ 화살표 컬럼 배경 투명화 ─ */
    function fixArrowColumn() {
        var aw = document.getElementById('sf-arrow-wrap');
        if (!aw) { setTimeout(fixArrowColumn, 400); return; }
        var el = aw.parentElement;
        var depth = 0;
        while (el && depth < 6) {
            sp(el,'background','transparent');
            sp(el,'background-color','transparent');
            sp(el,'box-shadow','none');
            sp(el,'border','none');
            if (el.classList && el.classList.contains('gradio-container')) break;
            el = el.parentElement;
            depth++;
        }
    }
    setTimeout(fixArrowColumn, 700);
    setInterval(fixArrowColumn, 2000);

    /* ─ 업로드박스 스타일 강제 적용 ─ */
    function styleUpload() {
        var el = document.getElementById('upload-wrap');
        if (!el) return;
        sp(el,'background','transparent');
        sp(el,'border','none');
        sp(el,'box-shadow','none');
        sp(el,'width','420px');
        sp(el,'max-width','100%');
        sp(el,'height','420px');
        sp(el,'max-height','420px');
        sp(el,'position','relative');
        sp(el,'margin','0 auto');
        sp(el,'overflow','hidden');
        sp(el,'display','block');
    }
    setInterval(styleUpload, 300);
    setTimeout(styleUpload, 100);

"""
    src = src.replace(OLD3_MARKER, OLD3_MARKER + '\n' + EXTRA_JS, 1)
    changes += 1
    print("OK 3: Core JS functions added to _CTRL_ENTER_JS")

# ═══════════════════════════════════════════════════════════════════
# 4. attachTheme의 sfSetBG 미정의 fallback을 var(--sf-bg-night) 방식으로 수정
# ═══════════════════════════════════════════════════════════════════
OLD4 = ("            /* sfSetBG 미정의 시 직접 처리 */\n"
        "            if (mode === 'night' && window._SFBG_N) {\n"
        "                document.documentElement.style.setProperty('--sf-bg', 'url(' + window._SFBG_N + ')');\n"
        "            } else {\n"
        "                document.documentElement.style.removeProperty('--sf-bg');\n"
        "            }")
NEW4 = ("            /* sfSetBG 미정의 시 직접 처리 */\n"
        "            if (mode === 'night') {\n"
        "                document.documentElement.style.setProperty('--sf-bg', 'var(--sf-bg-night)');\n"
        "            } else {\n"
        "                document.documentElement.style.removeProperty('--sf-bg');\n"
        "            }")
if OLD4 in src:
    src = src.replace(OLD4, NEW4, 1)
    changes += 1
    print("OK 4: attachTheme fallback updated to use --sf-bg-night")
else:
    print("FAIL 4: attachTheme fallback not found")

# ═══════════════════════════════════════════════════════════════════
print(f"\nTotal: {changes}/4")
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(src)
print("Written to app.py")
