#!/usr/bin/env python3
# 뿔(horns) + 상의(striped hoodie) + 신발(shoes) 를 기존 마인크래프트 스킨 위에 덮어씌우기
from PIL import Image
import numpy as np

PATH = r"C:\Users\hp\Downloads\c26667648d21e92d68c0c02e0bbbfba14d589329.png"

# ─── 색상 팔레트 ───────────────────────────────────────────
HORN_HI = (222, 213, 188, 255)   # 뿔 하이라이트 (밝은 크림)
HORN_MD = (183, 173, 148, 255)   # 뿔 중간톤
HORN_SH = (138, 128, 105, 255)   # 뿔 그림자

STR_DK  = (27, 27, 30)           # 후디 어두운 줄 (거의 검정)
STR_LT  = (62, 60, 66)           # 후디 밝은 줄 (짙은 회색)

SHOE    = (18, 16, 16)           # 신발 기본색

# ─── 헬퍼 ─────────────────────────────────────────────────
def set_px(arr, x, y, rgba):
    if 0 <= y < 64 and 0 <= x < 64:
        arr[y, x] = rgba

def fill(arr, x0, y0, w, h, rgba):
    arr[y0:y0+h, x0:x0+w] = rgba

def shade_c(rgb, f):
    """밝기 f를 적용한 (r,g,b,255) 반환."""
    return (int(min(rgb[0]*f, 255)),
            int(min(rgb[1]*f, 255)),
            int(min(rgb[2]*f, 255)), 255)

def stripe_face(arr, x0, y0, w, h, f=1.0, cuff=False):
    """2픽셀 단위 가로 줄무늬 칠하기. cuff=True → 마지막 2행 진하게."""
    for row in range(h):
        y = y0 + row
        if cuff and row >= h - 2:
            base = STR_DK
        elif (row // 2) % 2 == 0:
            base = STR_DK
        else:
            base = STR_LT
        arr[y, x0:x0+w] = shade_c(base, f)

# ─── 스킨 로드 ────────────────────────────────────────────
img = Image.open(PATH).convert("RGBA")
arr = np.array(img)

# ═══════════════════════════════════════════════════════════
# 1.  뿔 (HORNS)  — 머리 모자 레이어2 (hat/outer)
#
#  마인크래프트 64×64 UV:
#    Hat top   : x=40..47, y=0..7
#    Hat right : x=32..39, y=8..15  ← 캐릭터 오른쪽 옆면
#    Hat front : x=40..47, y=8..15
#    Hat left  : x=48..55, y=8..15  ← 캐릭터 왼쪽 옆면
#    Hat back  : x=56..63, y=8..15
# ═══════════════════════════════════════════════════════════

# ── 모자 윗면: 좌우 끝에 뿔 밑동 ──────────────────────────
# x=40 쪽(오른 뿔 밑동), x=47 쪽(왼 뿔 밑동)
for (x, y, c) in [
    (40,0,HORN_SH),(40,1,HORN_MD),(40,2,HORN_HI),
    (41,0,HORN_SH),(41,1,HORN_HI),
    (47,0,HORN_SH),(47,1,HORN_MD),(47,2,HORN_HI),
    (46,0,HORN_SH),(46,1,HORN_HI),
]:
    set_px(arr, x, y, c)

# ── 모자 오른쪽 면 (x=32..39): 오른 뿔 옆면 ───────────────
# 위→오른쪽으로 솟았다가 안쪽으로 나선형으로 말림
R_HORN = [
    (39,8,HORN_HI),(38,8,HORN_HI),(37,8,HORN_MD),
    (39,9,HORN_HI),(38,9,HORN_MD),
    (38,10,HORN_HI),(37,10,HORN_HI),(36,10,HORN_MD),
    (37,11,HORN_HI),(36,11,HORN_MD),(35,11,HORN_SH),
    (36,12,HORN_HI),(35,12,HORN_MD),(34,12,HORN_SH),
    (35,13,HORN_HI),(34,13,HORN_MD),(33,13,HORN_SH),
    (34,14,HORN_MD),(33,14,HORN_SH),
    (35,14,HORN_SH),(36,14,HORN_MD),   # 나선 안쪽 루프
    (35,15,HORN_MD),(36,15,HORN_HI),(37,15,HORN_MD),
]
for (x, y, c) in R_HORN:
    set_px(arr, x, y, c)

# ── 모자 왼쪽 면 (x=48..55): 왼 뿔 옆면 (오른 뿔 좌우 반전) ──
L_HORN = [
    (48,8,HORN_HI),(49,8,HORN_HI),(50,8,HORN_MD),
    (48,9,HORN_HI),(49,9,HORN_MD),
    (49,10,HORN_HI),(50,10,HORN_HI),(51,10,HORN_MD),
    (50,11,HORN_HI),(51,11,HORN_MD),(52,11,HORN_SH),
    (51,12,HORN_HI),(52,12,HORN_MD),(53,12,HORN_SH),
    (52,13,HORN_HI),(53,13,HORN_MD),(54,13,HORN_SH),
    (53,14,HORN_MD),(54,14,HORN_SH),
    (52,14,HORN_SH),(51,14,HORN_MD),   # 나선 안쪽 루프
    (52,15,HORN_MD),(51,15,HORN_HI),(50,15,HORN_MD),
]
for (x, y, c) in L_HORN:
    set_px(arr, x, y, c)

# ── 모자 앞면: 정면에서 보이는 뿔 밑동 ────────────────────
for (x, y, c) in [
    (40,8,HORN_SH),(40,9,HORN_MD),
    (47,8,HORN_SH),(47,9,HORN_MD),
]:
    set_px(arr, x, y, c)

# ── 모자 뒷면: 뒷면에도 뿔 밑동 힌트 ─────────────────────
for (x, y, c) in [
    (56,8,HORN_SH),(56,9,HORN_MD),
    (63,8,HORN_SH),(63,9,HORN_MD),
]:
    set_px(arr, x, y, c)

# ═══════════════════════════════════════════════════════════
# 2.  상의 (STRIPED HOODIE)  — 레이어1 몸통 + 팔
#
#  후디 색상: 검정(#1b1b1e)↔짙은회색(#3e3c42) 2픽셀 가로줄
#  소매 끝 2행: 커프 (진한 단색)
# ═══════════════════════════════════════════════════════════

# BODY 몸통
stripe_face(arr, 20, 16,  8,  4, f=0.80)           # 몸통 윗면
stripe_face(arr, 28, 16,  8,  4, f=0.70)           # 몸통 아랫면
stripe_face(arr, 16, 20,  4, 12, f=0.78)           # 몸통 오른쪽
stripe_face(arr, 20, 20,  8, 12, f=1.00)           # 몸통 앞면
stripe_face(arr, 28, 20,  4, 12, f=0.78)           # 몸통 왼쪽
stripe_face(arr, 32, 20,  8, 12, f=0.62)           # 몸통 뒷면

# RIGHT ARM 오른팔
stripe_face(arr, 44, 16,  4,  4, f=0.80)                    # 윗면
stripe_face(arr, 48, 16,  4,  4, f=0.70)                    # 아랫면
stripe_face(arr, 40, 20,  4, 12, f=0.78, cuff=True)         # 바깥쪽
stripe_face(arr, 44, 20,  4, 12, f=1.00, cuff=True)         # 앞면
stripe_face(arr, 48, 20,  4, 12, f=0.78, cuff=True)         # 안쪽
stripe_face(arr, 52, 20,  4, 12, f=0.62, cuff=True)         # 뒷면

# LEFT ARM 왼팔 (1.8+ format)
stripe_face(arr, 36, 48,  4,  4, f=0.80)                    # 윗면
stripe_face(arr, 40, 48,  4,  4, f=0.70)                    # 아랫면
stripe_face(arr, 32, 52,  4, 12, f=0.78, cuff=True)         # 왼쪽
stripe_face(arr, 36, 52,  4, 12, f=1.00, cuff=True)         # 앞면
stripe_face(arr, 40, 52,  4, 12, f=0.78, cuff=True)         # 오른쪽
stripe_face(arr, 44, 52,  4, 12, f=0.62, cuff=True)         # 뒷면

# ═══════════════════════════════════════════════════════════
# 3.  신발 (SHOES)  — 다리 하단 4행 (발목~발끝)
#
#  오른 다리 레이어1: y=20..31 → 신발 y=28..31
#  왼  다리 레이어1: y=52..63 → 신발 y=60..63
# ═══════════════════════════════════════════════════════════

# 오른 다리 신발
fill(arr,  0, 28, 4, 4, shade_c(SHOE, 0.85))   # 오른 옆면
fill(arr,  4, 28, 4, 4, shade_c(SHOE, 1.00))   # 앞면
fill(arr,  8, 28, 4, 4, shade_c(SHOE, 0.85))   # 왼 옆면
fill(arr, 12, 28, 4, 4, shade_c(SHOE, 0.65))   # 뒷면
fill(arr,  8, 16, 4, 4, shade_c(SHOE, 0.50))   # 밑창 (바닥면)

# 왼 다리 신발
fill(arr, 24, 60, 4, 4, shade_c(SHOE, 0.85))   # 오른 옆면
fill(arr, 20, 60, 4, 4, shade_c(SHOE, 1.00))   # 앞면
fill(arr, 16, 60, 4, 4, shade_c(SHOE, 0.85))   # 왼 옆면
fill(arr, 28, 60, 4, 4, shade_c(SHOE, 0.65))   # 뒷면
fill(arr, 24, 48, 4, 4, shade_c(SHOE, 0.50))   # 밑창 (바닥면)

# ─── 저장 ─────────────────────────────────────────────────
Image.fromarray(arr).save(PATH)
print(f"Done! → {PATH}")
