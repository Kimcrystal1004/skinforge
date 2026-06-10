"""
image_utils.py
PIL 헬퍼 유틸리티
"""

import io
from PIL import Image


def pil_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def bytes_to_pil(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGBA")


def scale_nearest(img: Image.Image, scale: int = 8) -> Image.Image:
    """픽셀아트 확대 (nearest neighbor)"""
    w, h = img.size
    return img.resize((w * scale, h * scale), Image.NEAREST)


def add_checkerboard_bg(img: Image.Image, cell: int = 4) -> Image.Image:
    """투명 영역에 체커보드 배경 합성 (미리보기용)"""
    import numpy as np
    arr_bg = np.zeros((img.height, img.width, 3), dtype=np.uint8)
    for y in range(img.height):
        for x in range(img.width):
            arr_bg[y, x] = [200, 200, 200] if (x // cell + y // cell) % 2 == 0 else [240, 240, 240]
    bg = Image.fromarray(arr_bg).convert("RGBA")
    bg.paste(img, (0, 0), img)
    return bg
