import re, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('app.py', 'r', encoding='utf-8') as f:
    src = f.read()

changes = 0

# ═══════════════════════════════════════════════════════════════════
# 1. _BTN_GEN: onclick/onmouseover/onmouseout 줄 제거
#    Gradio 5.x가 gr.HTML 내 on* 속성을 DOMPurify로 제거함
#    → JS addEventListener로 대체 (변경 3에서 추가)
# ═══════════════════════════════════════════════════════════════════
lines = src.split('\n')
new_lines = []
skip_patterns = ["' onclick=", "' onmouseover=", "' onmouseout="]
removed = 0
for line in lines:
    if any(p in line for p in skip_patterns):
        removed += 1
        continue
    new_lines.append(line)
src = '\n'.join(new_lines)
if removed == 3:
    changes += 1; print(f"OK 1: _BTN_GEN inline handlers removed ({removed} lines)")
else:
    print(f"WARN 1: Removed {removed} lines (expected 3) — check manually")
    if removed > 0: changes += 1

# ═══════════════════════════════════════════════════════════════════
# 2. HEADER: 라디오 버튼 → 토글 버튼 2개 (onchange 사용 안 함)
# ═══════════════════════════════════════════════════════════════════
OLD2 = ('<div style="display:flex;align-items:center;gap:5px;padding:3px 7px;background:rgba(0,0,0,.3);border:1px solid #555;">\n'
        '  <span style="color:#bbb;font-size:11px;font-weight:700;">배경</span>\n'
        '  <label style="display:flex;align-items:center;gap:3px;cursor:pointer;color:#fff;font-size:13px;font-weight:700;text-shadow:1px 1px 0 #333;">\n'
        '    <input type="radio" name="sf-bg" value="day" checked\n'
        '           onchange="window.sfSetBG&&window.sfSetBG(\'day\')"\n'
        '           style="accent-color:#00C9A7;cursor:pointer;"> 낮\n'
        '  </label>\n'
        '  <label style="display:flex;align-items:center;gap:3px;cursor:pointer;color:#fff;font-size:13px;font-weight:700;text-shadow:1px 1px 0 #333;">\n'
        '    <input type="radio" name="sf-bg" value="night"\n'
        '           onchange="window.sfSetBG&&window.sfSetBG(\'night\')"\n'
        '           style="accent-color:#00C9A7;cursor:pointer;"> 밤\n'
        '  </label>\n'
        '</div>')
NEW2 = ('<div style="display:flex;align-items:center;gap:4px;padding:3px 7px;background:rgba(0,0,0,.3);border:1px solid #555;">\n'
        '  <span style="color:#bbb;font-size:11px;font-weight:700;">배경</span>\n'
        '  <button id="sf-theme-day" style="background:#00C9A7;color:#000;border:none;padding:2px 10px;'
        'font-size:12px;font-weight:700;cursor:pointer;border-radius:3px;outline:none;">낮</button>\n'
        '  <button id="sf-theme-night" style="background:rgba(255,255,255,.1);color:#fff;border:1px solid #555;'
        'padding:2px 10px;font-size:12px;font-weight:700;cursor:pointer;border-radius:3px;outline:none;">밤</button>\n'
        '</div>')
if OLD2 in src:
    src = src.replace(OLD2, NEW2, 1); changes += 1; print("OK 2: Radio → toggle buttons")
else:
    print("FAIL 2: Radio button HTML not found")

# ═══════════════════════════════════════════════════════════════════
# 3. JS: initThemeBtns + initSfGenBtn 추가
#    fixArrowColumn setInterval 바로 뒤에 삽입
# ═══════════════════════════════════════════════════════════════════
OLD3 = "setInterval(fixArrowColumn,2000);\n\n/* ─ 업로드 배경이미지 DOM 직접 주입"
NEW3 = ("setInterval(fixArrowColumn,2000);\n\n"
        "/* ─ 배경 테마 버튼 (낮/밤) — addEventListener (onchange 대체) ─ */\n"
        "function initThemeBtns(){\n"
        "  var day=document.getElementById('sf-theme-day');\n"
        "  var night=document.getElementById('sf-theme-night');\n"
        "  if(!day||!night){setTimeout(initThemeBtns,400);return;}\n"
        "  if(day._sfBound) return;\n"
        "  day._sfBound=true;\n"
        "  function setActive(active){\n"
        "    [day,night].forEach(function(b){\n"
        "      b.style.background='rgba(255,255,255,.1)';\n"
        "      b.style.color='#fff';\n"
        "      b.style.border='1px solid #555';\n"
        "    });\n"
        "    active.style.background='#00C9A7';\n"
        "    active.style.color='#000';\n"
        "    active.style.border='none';\n"
        "  }\n"
        "  day.addEventListener('click',function(){\n"
        "    if(window.sfSetBG) window.sfSetBG('day');\n"
        "    setActive(day);\n"
        "  });\n"
        "  night.addEventListener('click',function(){\n"
        "    if(window.sfSetBG) window.sfSetBG('night');\n"
        "    setActive(night);\n"
        "  });\n"
        "}\n"
        "setTimeout(initThemeBtns,500);\n\n"
        "/* ─ sf-gen-btn 클릭 핸들러 — addEventListener (onclick 속성 대체) ─ */\n"
        "function initSfGenBtn(){\n"
        "  var btn=document.getElementById('sf-gen-btn');\n"
        "  if(!btn){setTimeout(initSfGenBtn,400);return;}\n"
        "  if(btn._sfBound) return;\n"
        "  btn._sfBound=true;\n"
        "  btn.addEventListener('click',function(){\n"
        "    var b=document.querySelector('#gen-btn button');\n"
        "    if(!b) b=document.querySelector('#gen-btn');\n"
        "    if(!b) return;\n"
        "    b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,composed:true,view:window}));\n"
        "  });\n"
        "  btn.addEventListener('mouseover',function(){btn.style.filter='brightness(1.12)';});\n"
        "  btn.addEventListener('mouseout',function(){btn.style.filter='';});\n"
        "}\n"
        "setTimeout(initSfGenBtn,800);\n\n"
        "/* ─ 업로드 배경이미지 DOM 직접 주입")
if "setInterval(fixArrowColumn,2000);\n\n/* ─ 업로드 배경이미지 DOM 직접 주입" in src:
    src = src.replace(OLD3, NEW3, 1); changes += 1; print("OK 3: initThemeBtns + initSfGenBtn JS added")
else:
    print("FAIL 3: fixArrowColumn anchor not found")
    idx = src.find('setInterval(fixArrowColumn'); print("  at:", idx)

# ═══════════════════════════════════════════════════════════════════
print(f"\nTotal: {changes}/3")
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(src)
print("Written to app.py")
