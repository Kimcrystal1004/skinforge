"""
skin_validator.py
생성된 스킨 PNG의 유효성 검사 및 자동 보정
"""

from PIL import Image
import numpy as np


def validate_skin(img: Image.Image) -> tuple[bool, list[str]]:
    """
    스킨 유효성 검사.
    Returns: (is_valid, [오류 메시지 목록])
    """
    errors = []

    # 1. 크기 확인
    if img.size != (64, 64):
        errors.append(f"크기 오류: {img.size} (64×64 필요)")

    # 2. RGBA 모드 확인
    if img.mode != "RGBA":
        errors.append(f"모드 오류: {img.mode} (RGBA 필요)")

    # 3. 완전 투명 스킨 여부
    arr = np.array(img.convert("RGBA"))
    opaque = (arr[:, :, 3] > 10).sum()
    if opaque < 100:
        errors.append(f"픽셀 부족: 불투명 픽셀 {opaque}개 (최소 100 필요)")

    return len(errors) == 0, errors


def fix_skin(img: Image.Image) -> Image.Image:
    """
    자동 보정:
    - 크기가 다르면 NEAREST로 64×64 리사이즈
    - RGBA 변환
    """
    img = img.convert("RGBA")
    if img.size != (64, 64):
        img = img.resize((64, 64), Image.NEAREST)
    return img


def validate_and_fix(img: Image.Image) -> tuple[Image.Image, bool, list[str]]:
    """
    검사 → 자동 보정 → 재검사 순으로 처리.
    Returns: (보정된 이미지, 최종 유효 여부, 오류 목록)
    """
    is_valid, errors = validate_skin(img)
    if not is_valid:
        img = fix_skin(img)
        is_valid, errors = validate_skin(img)
    return img, is_valid, errors
