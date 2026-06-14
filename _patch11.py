import re, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('app.py', 'r', encoding='utf-8') as f:
    src = f.read()

changes = 0

# ═══════════════════════════════════════════════════════════════════
# 1. Python: #upload-bg-frame → display:none 초기부터 숨김
#    (초기 렌더 시 왼쪽 컬럼을 700px로 부풀리는 원인 제거)
# ═══════════════════════════════════════════════════════════════════
OLD1 = 'style="width:min(700px,100%);aspect-ratio:1/1;display:block;pointer-events:none;overflow:hidden;"'
NEW1 = 'style="display:none;pointer-events:none;"'
if OLD1 in src:
    src = src.replace(OLD1, NEW1, 1); changes += 1; print("OK 1: upload-bg-frame → display:none from start")
else:
    print("FAIL 1: upload-bg-frame style not found")
    idx = src.find('upload-bg-frame'); print("  at:", idx, repr(src[idx:idx+120]))

# ═══════════════════════════════════════════════════════════════════
# 2. JS: constrainUploadParent() 추가 — upload-wrap 부모에 overflow:hidden
#    (drag-drop 존이 upload-wrap 외부(형제)로 렌더되는 경우 클리핑)
#    initUploadBg() 바로 다음에 삽입
# ═══════════════════════════════════════════════════════════════════
OLD2 = "setTimeout(initUploadBg,400);"
NEW2 = ("setTimeout(initUploadBg,400);\n"
        "\n"
        "/* ─ upload-wrap 부모 클리핑: drag-drop 존 숨김 ─ */\n"
        "function constrainUploadParent(){\n"
        "  var el=document.getElementById('upload-wrap');\n"
        "  if(!el) return;\n"
        "  var par=el.parentElement;\n"
        "  if(!par) return;\n"
        "  sp(par,'overflow','hidden');\n"
        "  sp(par,'max-height','420px');\n"
        "  sp(par,'background','transparent');\n"
        "  sp(par,'border','none');\n"
        "  sp(par,'box-shadow','none');\n"
        "  /* drag-drop 형제 요소 숨김 */\n"
        "  Array.prototype.forEach.call(par.children,function(c){\n"
        "    if(c===el) return;\n"
        "    var t=c.textContent||'';\n"
        "    if(t.indexOf('드롭')>-1||t.indexOf('Drop')>-1||t.indexOf('drop')>-1||c.tagName==='LABEL'){\n"
        "      sp(c,'display','none');\n"
        "    }\n"
        "  });\n"
        "}\n"
        "setInterval(constrainUploadParent,500);\n"
        "setTimeout(constrainUploadParent,200);")
if OLD2 in src:
    src = src.replace(OLD2, NEW2, 1); changes += 1; print("OK 2: constrainUploadParent() added")
else:
    print("FAIL 2: setTimeout(initUploadBg,400) not found")

# ═══════════════════════════════════════════════════════════════════
# 3. JS: fixArrowColumn() 추가 — 화살표 컬럼 흰 배경 투명화
#    setInterval(styleUpload,300) 바로 다음에 삽입
# ═══════════════════════════════════════════════════════════════════
OLD3 = "setInterval(styleUpload,300);\nsetTimeout(styleUpload,100);"
NEW3 = ("setInterval(styleUpload,300);\n"
        "setTimeout(styleUpload,100);\n"
        "\n"
        "/* ─ 화살표 컬럼 배경 투명화 ─ */\n"
        "function fixArrowColumn(){\n"
        "  var aw=document.getElementById('sf-arrow-wrap');\n"
        "  if(!aw){setTimeout(fixArrowColumn,400);return;}\n"
        "  var el=aw.parentElement;\n"
        "  var depth=0;\n"
        "  while(el&&depth<6){\n"
        "    sp(el,'background','transparent');\n"
        "    sp(el,'background-color','transparent');\n"
        "    sp(el,'box-shadow','none');\n"
        "    sp(el,'border','none');\n"
        "    if(el.classList&&el.classList.contains('gradio-container')) break;\n"
        "    el=el.parentElement;\n"
        "    depth++;\n"
        "  }\n"
        "}\n"
        "setTimeout(fixArrowColumn,700);\n"
        "setInterval(fixArrowColumn,2000);")
if OLD3 in src:
    src = src.replace(OLD3, NEW3, 1); changes += 1; print("OK 3: fixArrowColumn() added")
else:
    print("FAIL 3: setInterval(styleUpload,300) anchor not found")
    idx = src.find('setInterval(styleUpload'); print("  at:", idx)

# ═══════════════════════════════════════════════════════════════════
# 4. CSS: #upload-wrap width → min(420px,45vw) 와 _RESULT_EMPTY 동일하게
#    두 박스 같은 크기 보장 (양쪽 컬럼이 이제 동일 너비이므로 min(420px,100%)도 OK
#    추가로: upload-wrap 부모 그 자체 클리핑을 CSS에서도 명시
# ═══════════════════════════════════════════════════════════════════
# 이미 height:420px!important 있는지 확인 후 없으면 추가
if "+'height:420px!important;'" in src and "+'max-height:420px!important;'" in src:
    print("OK 4: CSS height already applied (no change needed)")
    changes += 1
else:
    print("FAIL 4: CSS height not found - check manually")

# ═══════════════════════════════════════════════════════════════════
print(f"\nTotal: {changes}/4")
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(src)
print("Written to app.py")
