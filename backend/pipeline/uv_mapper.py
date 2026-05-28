from PIL import Image
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from backend.skin_spec.uv_coords import UV

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), '..', 'skin_spec', 'templates', 'base_64x64.png')


def paste_part(canvas: Image.Image, part_img: Image.Image, coords: tuple) -> Image.Image:
    """
    part_img를 coords(x, y, w, h) 위치에 리사이즈 후 붙여넣기
    """
    x, y, w, h = coords
    part_resized = part_img.resize((w, h), Image.NEAREST)
    # RGBA로 변환 (투명도 유지)
    if part_resized.mode != 'RGBA':
        part_resized = part_resized.convert('RGBA')
    canvas.paste(part_resized, (x, y), part_resized)
    return canvas


def build_skin(parts: dict, output_path: str = None) -> Image.Image:
    """
    parts 딕셔너리를 받아 64x64 스킨 PNG를 생성합니다.

    parts 형식 예시:
    {
        "head": {
            "inner": {
                "front": <PIL.Image>,
                "back": <PIL.Image>,
                "left": <PIL.Image>,
                "right": <PIL.Image>,
                "top": <PIL.Image>,
                "bottom": <PIL.Image>,
            },
            "outer": { ... }  # 없으면 생략 가능
        },
        "body": { ... },
        "right_arm": { ... },
        ...
    }

    output_path: 저장 경로 (None이면 저장 안 함)
    반환값: 완성된 PIL.Image (RGBA, 64x64)
    """
    # 완전 투명 64x64 캔버스 생성
    canvas = Image.new('RGBA', (64, 64), (0, 0, 0, 0))

    for part_name, layers in parts.items():
        if part_name not in UV:
            print(f"[경고] 알 수 없는 파트: {part_name}, 건너뜀")
            continue

        for layer_name, faces in layers.items():  # inner / outer
            if layer_name not in UV[part_name]:
                continue

            for face_name, img in faces.items():  # front / back / left / ...
                if face_name not in UV[part_name][layer_name]:
                    continue
                if img is None:
                    continue

                coords = UV[part_name][layer_name][face_name]
                canvas = paste_part(canvas, img, coords)

    if output_path:
        canvas.save(output_path, 'PNG')
        print(f"[완료] 스킨 저장됨: {output_path}")

    return canvas


def build_skin_from_solid_colors(color_map: dict, output_path: str = None) -> Image.Image:
    """
    테스트용: 단색으로 각 파트를 채워서 스킨 생성
    color_map 예시:
    {
        "head": (200, 150, 100, 255),    # 피부톤
        "body": (50, 60, 120, 255),      # 네이비 상의
        "right_arm": (50, 60, 120, 255),
        "left_arm": (50, 60, 120, 255),
        "right_leg": (30, 30, 80, 255),  # 바지
        "left_leg": (30, 30, 80, 255),
    }
    """
    parts = {}

    for part_name, color in color_map.items():
        if part_name not in UV:
            continue

        parts[part_name] = {"inner": {}, "outer": {}}

        for layer_name in ["inner", "outer"]:
            for face_name, coords in UV[part_name][layer_name].items():
                _, _, w, h = coords
                img = Image.new('RGBA', (w, h), color)
                parts[part_name][layer_name][face_name] = img

    return build_skin(parts, output_path)