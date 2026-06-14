import re, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('app.py', 'r', encoding='utf-8') as f:
    src = f.read()

changes = 0

# ═══════════════════════════════════════════════════════════════════
# 1. gr.HTML: sanitize_html=False 추가 (핵심 수정)
#    Gradio가 <script> 태그를 DOMPurify로 제거하는 것이 모든 문제의 원인
# ═══════════════════════════════════════════════════════════════════
OLD1_REAL = 'gr.HTML(value="""<script>\n(function(){'
NEW1_REAL = 'gr.HTML(sanitize_html=False, value="""<script>\n(function(){'
if OLD1_REAL in src:
    src = src.replace(OLD1_REAL, NEW1_REAL, 1)
    changes += 1
    print("OK 1: gr.HTML sanitize_html=False added")
else:
    print("FAIL 1: gr.HTML script call not found")

# ═══════════════════════════════════════════════════════════════════
# 2. initSfGenBtn: dispatchEvent → .click() (신뢰된 이벤트로 Gradio 동작)
# ═══════════════════════════════════════════════════════════════════
OLD2 = ("    b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,composed:true,view:window}));\n")
NEW2 = ("    b.click();\n")
if OLD2 in src:
    src = src.replace(OLD2, NEW2, 1); changes += 1
    print("OK 2: dispatchEvent → .click()")
else:
    print("FAIL 2: dispatchEvent line not found")
    idx = src.find('b.dispatchEvent'); print("  at:", idx)

# ═══════════════════════════════════════════════════════════════════
# 3. _CTRL_ENTER_JS 확장: initThemeBtns + initSfGenBtn 백업 추가
#    (gr.Blocks(js=...) 파라미터는 항상 실행됨 - 최후 보루)
# ═══════════════════════════════════════════════════════════════════
OLD3 = ('_CTRL_ENTER_JS = """\n'
        '() => {\n'
        '    document.addEventListener(\'keydown\', function(e) {\n'
        '        if (e.ctrlKey && e.key === \'Enter\') {\n'
        '            e.preventDefault();\n'
        '            var btn = document.querySelector(\'#gen-btn button\');\n'
        '            if (btn) btn.click();\n'
        '        }\n'
        '    });\n'
        '}\n'
        '"""')
NEW3 = ('_CTRL_ENTER_JS = """\n'
        '() => {\n'
        '    /* Ctrl+Enter */\n'
        '    document.addEventListener(\'keydown\', function(e) {\n'
        '        if (e.ctrlKey && e.key === \'Enter\') {\n'
        '            e.preventDefault();\n'
        '            var btn = document.querySelector(\'#gen-btn button\') || document.querySelector(\'#gen-btn\');\n'
        '            if (btn) btn.click();\n'
        '        }\n'
        '    });\n'
        '\n'
        '    /* sf-gen-btn 클릭 핸들러 백업 (sanitize_html=False 보완) */\n'
        '    function attachGenBtn() {\n'
        '        var btn = document.getElementById(\'sf-gen-btn\');\n'
        '        if (!btn) { setTimeout(attachGenBtn, 400); return; }\n'
        '        if (btn._grBound) return;\n'
        '        btn._grBound = true;\n'
        '        btn.addEventListener(\'click\', function() {\n'
        '            var b = document.querySelector(\'#gen-btn button\') || document.querySelector(\'#gen-btn\');\n'
        '            if (b) b.click();\n'
        '        });\n'
        '        btn.addEventListener(\'mouseover\', function() { btn.style.filter = \'brightness(1.12)\'; });\n'
        '        btn.addEventListener(\'mouseout\',  function() { btn.style.filter = \'\'; });\n'
        '    }\n'
        '    setTimeout(attachGenBtn, 600);\n'
        '\n'
        '    /* 배경 테마 버튼 백업 */\n'
        '    function attachTheme() {\n'
        '        var d = document.getElementById(\'sf-theme-day\');\n'
        '        var n = document.getElementById(\'sf-theme-night\');\n'
        '        if (!d || !n) { setTimeout(attachTheme, 400); return; }\n'
        '        if (d._grBound) return;\n'
        '        d._grBound = true;\n'
        '        function setTheme(mode) {\n'
        '            if (window.sfSetBG) { window.sfSetBG(mode); return; }\n'
        '            /* sfSetBG 미정의 시 직접 처리 */\n'
        '            if (mode === \'night\' && window._SFBG_N) {\n'
        '                document.documentElement.style.setProperty(\'--sf-bg\', \'url(\' + window._SFBG_N + \')\');\n'
        '            } else {\n'
        '                document.documentElement.style.removeProperty(\'--sf-bg\');\n'
        '            }\n'
        '        }\n'
        '        function setActive(el) {\n'
        '            [d, n].forEach(function(b) {\n'
        '                b.style.background = \'rgba(255,255,255,.1)\';\n'
        '                b.style.color = \'#fff\';\n'
        '                b.style.border = \'1px solid #555\';\n'
        '            });\n'
        '            el.style.background = \'#00C9A7\';\n'
        '            el.style.color = \'#000\';\n'
        '            el.style.border = \'none\';\n'
        '        }\n'
        '        d.addEventListener(\'click\', function() { setTheme(\'day\');   setActive(d); });\n'
        '        n.addEventListener(\'click\', function() { setTheme(\'night\'); setActive(n); });\n'
        '    }\n'
        '    setTimeout(attachTheme, 600);\n'
        '}\n'
        '"""')
if OLD3 in src:
    src = src.replace(OLD3, NEW3, 1); changes += 1
    print("OK 3: _CTRL_ENTER_JS expanded with backup handlers")
else:
    print("FAIL 3: _CTRL_ENTER_JS not found")
    idx = src.find('_CTRL_ENTER_JS'); print("  at:", idx)

# ═══════════════════════════════════════════════════════════════════
# 4. 위치 문제: 정적 CSS에 margin-top:0 추가
# ═══════════════════════════════════════════════════════════════════
OLD4 = '#result-box { margin: 0 !important; padding-top: 0 !important; }'
NEW4 = '#result-box { margin: 0 !important; padding-top: 0 !important; }\n#upload-wrap, #gen-html, [id="result-box"] { margin-top: 0 !important; }'
if OLD4 in src:
    src = src.replace(OLD4, NEW4, 1); changes += 1
    print("OK 4: margin-top:0 CSS added")
else:
    print("FAIL 4: result-box CSS not found")

# ═══════════════════════════════════════════════════════════════════
print(f"\nTotal: {changes}/4")
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(src)
print("Written to app.py")
