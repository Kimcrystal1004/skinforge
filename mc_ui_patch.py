import sys, io, base64, random
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image

def gen_stone(w, h, seed):
    random.seed(seed)
    img = Image.new('RGB', (w, h))
    pix = img.load()
    for y in range(h):
        for x in range(w):
            v = 118 + random.randint(-22, 26)
            if random.random() < 0.07:
                v = max(v - 40, 60)
            pix[x, y] = (v, v, v)
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return base64.b64encode(buf.getvalue()).decode()

sp = gen_stone(32, 32, 99)
sb = gen_stone(16, 16, 42)

with open(r'C:\Users\hp\OneDrive\바탕 화면\skinforge\app.py', 'r', encoding='utf-8') as f:
    src = f.read()

# ── 1. Minecraft CSS ──
mc_css = (
    "\n/* ══ Minecraft UI ══ */\n"
    "#upload-wrap .wrap {\n"
    f"    background-image: url('data:image/png;base64,{sp}') !important;\n"
    "    background-size: 32px 32px !important; image-rendering: pixelated !important;\n"
    "    border: 4px solid #222 !important; border-radius: 0 !important;\n"
    "    box-shadow: 0 0 0 2px #111, inset 5px 5px 0 rgba(255,255,255,.32), inset -5px -5px 0 rgba(0,0,0,.4) !important;\n"
    "    min-height: 340px !important; height: 340px !important;\n"
    "}\n"
    "#upload-wrap .wrap:hover { filter: brightness(1.08) !important; }\n"
    "#upload-wrap svg { color: rgba(255,255,255,.85) !important; }\n"
    "#upload-wrap .upload-text span { color: rgba(255,255,255,.75) !important; text-shadow: 1px 1px 0 #000 !important; }\n"
    "#gen-btn button {\n"
    f"    background-image: url('data:image/png;base64,{sb}') !important;\n"
    "    background-size: 16px 16px !important; background-color: #8a8a8a !important;\n"
    "    image-rendering: pixelated !important; color: #fff !important;\n"
    "    text-shadow: 2px 2px 0 #333 !important; border: 4px solid #5d9020 !important;\n"
    "    border-radius: 0 !important; height: 52px !important; transition: none !important;\n"
    "    box-shadow: 0 0 0 2px #111, inset 0 0 0 2px rgba(0,0,0,.4),\n"
    "                inset 4px 4px 0 rgba(255,255,255,.32), inset -4px -4px 0 rgba(0,0,0,.4) !important;\n"
    "}\n"
    "#gen-btn button:hover {\n"
    "    background-color: #9e9e9e !important; transform: none !important;\n"
    "    box-shadow: 0 0 0 2px #111, inset 0 0 0 2px rgba(0,0,0,.4),\n"
    "                inset 4px 4px 0 rgba(255,255,255,.45), inset -4px -4px 0 rgba(0,0,0,.28) !important;\n"
    "}\n"
)
src = src.replace('\nHEADER_HTML = """', '\nCSS += """\n' + mc_css + '"""\n\nHEADER_HTML = """')
print('CSS:', 'Minecraft UI' in src)

# ── 2. _RESULT_EMPTY ──
src = src.replace(
    '<div style="background:#111;border-radius:16px;border:1px solid #1a1a1a;\n    padding:20px;display:flex;flex-direction:column;gap:14px;">',
    (f'<div style="background-image:url(\'data:image/png;base64,{sp}\');'
     f'background-size:32px 32px;image-rendering:pixelated;background-color:#8a8a8a;'
     f'border:4px solid #222;padding:12px;display:flex;flex-direction:column;gap:10px;'
     f'box-shadow:0 0 0 2px #111,inset 5px 5px 0 rgba(255,255,255,.3),inset -5px -5px 0 rgba(0,0,0,.38);">')
)
src = src.replace(
    '<div style="background:#0a0a0a;border-radius:12px;border:1px solid #181818;\n      height:280px;display:flex;align-items:center;justify-content:center;">',
    '<div style="background:rgba(0,0,0,.45);height:300px;display:flex;align-items:center;justify-content:center;box-shadow:inset 3px 3px 0 rgba(0,0,0,.4),inset -3px -3px 0 rgba(255,255,255,.08);">'
)
src = src.replace(
    ('  <span style="display:block;background:#1e1e1e;color:#444;border:1px solid #2a2a2a;\n'
     '      font-size:15px;font-weight:700;height:48px;line-height:48px;\n'
     '      border-radius:10px;text-align:center;box-sizing:border-box;cursor:not-allowed;">\n'
     '    ⬇️ PNG 다운로드\n'
     '  </span>'),
    (f'  <span style="display:block;background-image:url(\'data:image/png;base64,{sb}\');'
     f'background-size:16px 16px;image-rendering:pixelated;background-color:#5a5a5a;'
     f'color:rgba(255,255,255,.4);text-shadow:1px 1px 0 #222;border:4px solid #3a5a10;'
     f'box-shadow:0 0 0 2px #111,inset 4px 4px 0 rgba(255,255,255,.18),inset -4px -4px 0 rgba(0,0,0,.38);'
     f'font-size:15px;font-weight:700;height:52px;line-height:52px;'
     f'text-align:center;box-sizing:border-box;cursor:not-allowed;">\n'
     f'    ⬇️ PNG 다운로드\n'
     f'  </span>')
)
print('empty:', 'rgba(0,0,0,.45)' in src)

# ── 3. make_result_html 외부 컨테이너 ──
src = src.replace(
    'return f"""\n<div style="background:#111;border-radius:16px;border:1px solid #1a1a1a;\n    padding:20px;display:flex;flex-direction:column;gap:14px;">',
    (f'return f"""\n'
     f'<div style="background-image:url(\'data:image/png;base64,{sp}\');'
     f'background-size:32px 32px;image-rendering:pixelated;background-color:#8a8a8a;'
     f'border:4px solid #222;padding:12px;display:flex;flex-direction:column;gap:10px;'
     f'box-shadow:0 0 0 2px #111,inset 5px 5px 0 rgba(255,255,255,.3),inset -5px -5px 0 rgba(0,0,0,.38);">')
)

# ── 4. 미리보기 박스 ──
src = src.replace(
    '  <div id="sfwrap" data-idx="0"\n       style="position:relative;background:#0a0a0a;border-radius:12px;\n              border:1px solid #181818;overflow:hidden;user-select:none;">',
    '  <div id="sfwrap" data-idx="0"\n       style="position:relative;background:rgba(0,0,0,.45);overflow:hidden;user-select:none;box-shadow:inset 3px 3px 0 rgba(0,0,0,.4),inset -3px -3px 0 rgba(255,255,255,.08);">'
)
print('preview:', 'rgba(0,0,0,.45)' in src)

# ── 5. 다운로드 버튼 ──
old_dl = (
    '  <a href="data:image/png;base64,{skin_b64}"\n'
    '     download="skinforge_skin.png"\n'
    '     style="display:block;background:#00C9A7;color:#000;text-decoration:none;\n'
    '            font-size:15px;font-weight:700;height:48px;line-height:48px;\n'
    '            border-radius:10px;text-align:center;box-sizing:border-box;\n'
    '            cursor:pointer;box-shadow:0 4px 16px rgba(0,201,167,.3);"\n'
    "     onmouseover=\"this.style.background='#00ddb8'\"\n"
    "     onmouseout=\"this.style.background='#00C9A7'\">\n"
    '    ⬇️ PNG 다운로드\n'
    '  </a>'
)
new_dl = (
    '  <a href="data:image/png;base64,{skin_b64}"\n'
    '     download="skinforge_skin.png"\n'
    f'     style="display:block;background-image:url(\'data:image/png;base64,{sb}\');'
    f'background-size:16px 16px;image-rendering:pixelated;background-color:#8a8a8a;'
    f'color:#fff;text-decoration:none;text-shadow:2px 2px 0 #333;'
    f'font-size:15px;font-weight:700;height:52px;line-height:52px;'
    f'border:4px solid #5d9020;text-align:center;box-sizing:border-box;cursor:pointer;'
    f'box-shadow:0 0 0 2px #111,inset 0 0 0 2px rgba(0,0,0,.4),'
    f'inset 4px 4px 0 rgba(255,255,255,.32),inset -4px -4px 0 rgba(0,0,0,.4);"\n'
    "     onmouseover=\"this.style.backgroundColor='#9e9e9e'\"\n"
    "     onmouseout=\"this.style.backgroundColor='#8a8a8a'\">\n"
    '    ⬇️ PNG 다운로드\n'
    '  </a>'
)
src = src.replace(old_dl, new_dl)
print('download btn:', '#5d9020' in src)

# ── 6. 화살표 중간 컬럼 ──
arrow_html = (
    '<div style="display:flex;align-items:center;justify-content:center;height:100%;min-height:360px;">'
    '<svg id="mc-arrow-svg" viewBox="0 0 60 40" width="60" height="42" xmlns="http://www.w3.org/2000/svg">'
    '<defs><clipPath id="aclip"><polygon points="1,13 37,13 37,2 59,20 37,38 37,27 1,27"/></clipPath></defs>'
    '<polygon points="1,13 37,13 37,2 59,20 37,38 37,27 1,27" fill="#2a2a2a" stroke="#555" stroke-width="1.5"/>'
    '<rect id="arr-fill" x="0" y="0" width="0" height="40" fill="white" clip-path="url(#aclip)"/>'
    '</svg></div>'
)
old_col2 = (
    '        with gr.Column(scale=1, min_width=300):\n'
    '            result_html = gr.HTML(value=_RESULT_EMPTY, elem_id="result-box")'
)
new_col2 = (
    '        with gr.Column(scale=0, min_width=90):\n'
    f'            gr.HTML(value="""{arrow_html}""")\n\n'
    '        with gr.Column(scale=1, min_width=300):\n'
    '            result_html = gr.HTML(value=_RESULT_EMPTY, elem_id="result-box")'
)
src = src.replace(old_col2, new_col2)
print('arrow col:', 'aclip' in src)

# ── 7. 화살표 JS ──
arrow_js = (
    '<script>\n'
    '(function(){\n'
    '  function init(){\n'
    '    var btn=document.querySelector(\'#gen-btn button\');\n'
    '    if(!btn){setTimeout(init,300);return;}\n'
    '    var raf=null,startT=0;\n'
    '    function step(){\n'
    '      var r=document.getElementById(\'arr-fill\');\n'
    '      if(!r)return;\n'
    '      var pct=Math.min((Date.now()-startT)/30000,0.94);\n'
    '      r.setAttribute(\'width\',String(pct*62));\n'
    '      if(pct<0.94)raf=requestAnimationFrame(step);\n'
    '    }\n'
    '    btn.addEventListener(\'click\',function(){\n'
    '      var r=document.getElementById(\'arr-fill\');\n'
    '      if(r)r.setAttribute(\'width\',\'0\');\n'
    '      startT=Date.now();\n'
    '      if(raf)cancelAnimationFrame(raf);\n'
    '      raf=requestAnimationFrame(step);\n'
    '      var box=document.querySelector(\'#result-box\');\n'
    '      if(box){\n'
    '        var obs=new MutationObserver(function(){\n'
    '          if(box.querySelector(\'#sfimg\')){\n'
    '            cancelAnimationFrame(raf);\n'
    '            var r2=document.getElementById(\'arr-fill\');\n'
    '            if(r2)r2.setAttribute(\'width\',\'62\');\n'
    '            obs.disconnect();\n'
    '          }\n'
    '        });\n'
    '        obs.observe(box,{childList:true,subtree:true});\n'
    '      }\n'
    '    });\n'
    '  }\n'
    '  init();\n'
    '})();\n'
    '</script>'
)
src = src.replace(
    '    generate_btn.click(',
    f'    gr.HTML(value="""{arrow_js}""")\n\n    generate_btn.click('
)
print('arrow JS:', 'arr-fill' in src)

with open(r'C:\Users\hp\OneDrive\바탕 화면\skinforge\app.py', 'w', encoding='utf-8') as f:
    f.write(src)
print('All done.')
