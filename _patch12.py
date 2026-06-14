import re, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('app.py', 'r', encoding='utf-8') as f:
    src = f.read()

changes = 0

# ═══════════════════════════════════════════════════════════════════
# 1. gr.Image: add width=420 (prevents Gradio from rendering too wide)
# ═══════════════════════════════════════════════════════════════════
OLD1 = ('gr.Image(\n'
        '                type="pil", label="사진 업로드",\n'
        '                elem_id="upload-wrap", show_label=False,\n'
        '                height=420,\n'
        '            )')
NEW1 = ('gr.Image(\n'
        '                type="pil", label="사진 업로드",\n'
        '                elem_id="upload-wrap", show_label=False,\n'
        '                height=420, width=420,\n'
        '            )')
if OLD1 in src:
    src = src.replace(OLD1, NEW1, 1); changes += 1; print("OK 1: gr.Image width=420 added")
else:
    print("FAIL 1: gr.Image call not found")

# ═══════════════════════════════════════════════════════════════════
# 2. Columns: min_width 300 → 440 (both outer columns)
# ═══════════════════════════════════════════════════════════════════
src_new = src.replace('gr.Column(scale=1, min_width=300)', 'gr.Column(scale=1, min_width=440)')
count = src.count('gr.Column(scale=1, min_width=300)')
if count == 2:
    src = src_new; changes += 1; print(f"OK 2: Both scale=1 columns → min_width=440")
else:
    print(f"FAIL 2: Expected 2 occurrences, found {count}")

# ═══════════════════════════════════════════════════════════════════
# 3. CSS: width:min(420px,100%) → width:420px
# ═══════════════════════════════════════════════════════════════════
OLD3 = "    +'width:min(420px,100%)!important;'\n    +'max-width:100%!important;'"
NEW3 = "    +'width:420px!important;'\n    +'max-width:100%!important;'"
if OLD3 in src:
    src = src.replace(OLD3, NEW3, 1); changes += 1; print("OK 3: CSS width:420px")
else:
    print("FAIL 3: CSS width not found")

# ═══════════════════════════════════════════════════════════════════
# 4. CSS: Remove ::before block (switching to DOM injection approach)
# ═══════════════════════════════════════════════════════════════════
OLD4 = ("\n\n    +'#upload-wrap::before{'\n"
        "    +'content:\"\"!important;'\n"
        "    +'position:absolute!important;'\n"
        "    +'top:0!important;left:0!important;'\n"
        "    +'width:100%!important;height:100%!important;'\n"
        "    +'background-image:var(--sf-upload-bg-img,none)!important;'\n"
        "    +'background-size:100% 100%!important;'\n"
        "    +'background-repeat:no-repeat!important;'\n"
        "    +'z-index:0!important;'\n"
        "    +'pointer-events:none!important;}'")
if OLD4 in src:
    src = src.replace(OLD4, '', 1); changes += 1; print("OK 4: ::before CSS removed")
else:
    print("FAIL 4: ::before block not found")

# ═══════════════════════════════════════════════════════════════════
# 5. CSS: Add :has() rule for center column transparent
# ═══════════════════════════════════════════════════════════════════
OLD5 = ("    +'#sf-arrow-wrap{'\n"
        "    +'background:transparent!important;}'\n\n"
        "    +'#sf-arrow-wrap *{'\n"
        "    +'background:transparent!important;}'")
NEW5 = ("    +'#sf-arrow-wrap{'\n"
        "    +'background:transparent!important;}'\n\n"
        "    +'#sf-arrow-wrap *{'\n"
        "    +'background:transparent!important;}'\n\n"
        "    +'.block:has(#sf-arrow-wrap){'\n"
        "    +'background:transparent!important;'\n"
        "    +'box-shadow:none!important;'\n"
        "    +'border:none!important;}'")
if OLD5 in src:
    src = src.replace(OLD5, NEW5, 1); changes += 1; print("OK 5: :has() center column CSS added")
else:
    print("FAIL 5: #sf-arrow-wrap CSS not found")

# ═══════════════════════════════════════════════════════════════════
# 6. JS: Replace initUploadBg() with injectUploadBg() (DOM injection)
# ═══════════════════════════════════════════════════════════════════
OLD6 = ("/* ─ 업로드 배경 이미지 → CSS 변수 주입 (::before 방식) ─ */\n"
        "function initUploadBg(){\n"
        "  var bg=document.getElementById('upload-bg-frame');\n"
        "  if(!bg){setTimeout(initUploadBg,300);return;}\n"
        "  var bi=bg.querySelector('img');\n"
        "  if(!bi||!bi.src){setTimeout(initUploadBg,300);return;}\n"
        "  document.documentElement.style.setProperty('--sf-upload-bg-img','url('+bi.src+')');\n"
        "  /* bg-frame은 데이터 소스 역할 완료 — 숨김 처리 */\n"
        "  var wp=bg.parentElement;\n"
        "  if(wp) sp(wp,'display','none');\n"
        "}\n"
        "setTimeout(initUploadBg,400);")
NEW6 = ("/* ─ 업로드 배경이미지 DOM 직접 주입 (z-index:-1 img 요소) ─ */\n"
        "function injectUploadBg(){\n"
        "  var el=document.getElementById('upload-wrap');\n"
        "  var bg=document.getElementById('upload-bg-frame');\n"
        "  if(!el||!bg){setTimeout(injectUploadBg,400);return;}\n"
        "  var bi=bg.querySelector('img');\n"
        "  if(!bi||!bi.src){setTimeout(injectUploadBg,400);return;}\n"
        "  var src=bi.src;\n"
        "  function ensureBg(){\n"
        "    if(document.getElementById('sf-upload-bg-img')) return;\n"
        "    var img=document.createElement('img');\n"
        "    img.id='sf-upload-bg-img';\n"
        "    img.src=src;\n"
        "    sp(img,'position','absolute');\n"
        "    sp(img,'top','0');\n"
        "    sp(img,'left','0');\n"
        "    sp(img,'width','100%');\n"
        "    sp(img,'height','100%');\n"
        "    sp(img,'z-index','-1');\n"
        "    sp(img,'pointer-events','none');\n"
        "    sp(img,'image-rendering','pixelated');\n"
        "    sp(img,'display','block');\n"
        "    sp(img,'box-sizing','border-box');\n"
        "    el.appendChild(img);\n"
        "  }\n"
        "  ensureBg();\n"
        "  new MutationObserver(function(){ensureBg();}).observe(el,{childList:true});\n"
        "}\n"
        "setTimeout(injectUploadBg,600);")
if OLD6 in src:
    src = src.replace(OLD6, NEW6, 1); changes += 1; print("OK 6: initUploadBg → injectUploadBg (DOM injection)")
else:
    print("FAIL 6: initUploadBg not found exactly")
    idx = src.find('function initUploadBg'); print("  at:", idx)

# ═══════════════════════════════════════════════════════════════════
# 7. JS styleUpload(): width min() → 420px
# ═══════════════════════════════════════════════════════════════════
OLD7 = "  sp(el,'width','min(420px,100%)');\n  sp(el,'max-width','100%');"
NEW7 = "  sp(el,'width','420px');\n  sp(el,'max-width','100%');"
if OLD7 in src:
    src = src.replace(OLD7, NEW7, 1); changes += 1; print("OK 7: styleUpload width 420px")
else:
    print("FAIL 7: styleUpload width not found")

# ═══════════════════════════════════════════════════════════════════
# 8. JS styleUpload(): skip #sf-upload-bg-img in img querySelectorAll
# ═══════════════════════════════════════════════════════════════════
OLD8 = "  el.querySelectorAll('img').forEach(function(img){"
NEW8 = "  el.querySelectorAll('img:not(#sf-upload-bg-img)').forEach(function(img){"
if OLD8 in src:
    src = src.replace(OLD8, NEW8, 1); changes += 1; print("OK 8: img loop skips bg img")
else:
    print("FAIL 8: querySelectorAll img not found")

# ═══════════════════════════════════════════════════════════════════
# 9. _RESULT_EMPTY: width:min(420px,100%) → 420px
# ═══════════════════════════════════════════════════════════════════
OLD9 = 'position:relative;width:min(420px,100%);height:420px;max-height:420px;aspect-ratio:1/1;overflow:hidden;margin:0 auto;">'
NEW9 = 'position:relative;width:420px;max-width:100%;height:420px;max-height:420px;aspect-ratio:1/1;overflow:hidden;margin:0 auto;">'
if OLD9 in src:
    src = src.replace(OLD9, NEW9, 1); changes += 1; print("OK 9: _RESULT_EMPTY width:420px")
else:
    print("FAIL 9: _RESULT_EMPTY style not found")

# ═══════════════════════════════════════════════════════════════════
# 10. sfwrap: width:min(420px,100%) → 420px
# ═══════════════════════════════════════════════════════════════════
OLD10 = ('style="position:relative;overflow:hidden;user-select:none;'
         'width:min(420px,100%);height:420px;max-height:420px;aspect-ratio:1/1;box-sizing:border-box;margin:0 auto;">')
NEW10 = ('style="position:relative;overflow:hidden;user-select:none;'
         'width:420px;max-width:100%;height:420px;max-height:420px;aspect-ratio:1/1;box-sizing:border-box;margin:0 auto;">')
if OLD10 in src:
    src = src.replace(OLD10, NEW10, 1); changes += 1; print("OK 10: sfwrap width:420px")
else:
    print("FAIL 10: sfwrap style not found")

# ═══════════════════════════════════════════════════════════════════
print(f"\nTotal: {changes}/10")
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(src)
print("Written to app.py")
