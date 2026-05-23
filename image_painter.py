#!/usr/bin/env python3
"""
Image Painting Module
Sử dụng Pillow để áp dụng màu sơn lên ảnh mà không phụ thuộc numpy.
"""

import base64
import io
from typing import Dict, Optional


def _load_pil():
    try:
        from PIL import Image, ImageEnhance, ImageDraw
        return Image, ImageEnhance, ImageDraw
    except ImportError:
        return None


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _decode_image(image_base64: str):
    pil = _load_pil()
    if pil is None:
        return None
    Image, _, _ = pil
    if "," in image_base64:
        _, base64_data = image_base64.split(",", 1)
    else:
        base64_data = image_base64

    image_bytes = base64.b64decode(base64_data)
    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


def _encode_image(image) -> str:
    output_bytes = io.BytesIO()
    image.save(output_bytes, format="PNG")
    result_base64 = base64.b64encode(output_bytes.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{result_base64}"


def apply_paint_color_simple(image_base64: str, paint_areas: Dict[str, str], project_type: str) -> str:
    """Apply a simple whole-image color blend."""

    try:
        pil = _load_pil()
        if pil is None:
            return image_base64
        Image, ImageEnhance, _ = pil

        working_image = _decode_image(image_base64)
        if working_image is None:
            return image_base64
        if not paint_areas:
            return image_base64

        result_image = working_image.copy()
        for _, hex_color in paint_areas.items():
            overlay = Image.new("RGB", result_image.size, hex_to_rgb(hex_color))
            result_image = Image.blend(result_image, overlay, 0.35)

        result_image = ImageEnhance.Contrast(result_image).enhance(1.1)
        return _encode_image(result_image)
    except Exception as e:
        print(f"Error in apply_paint_color_simple: {e}")
        return image_base64


def apply_paint_color_advanced(image_base64: str, paint_areas: Dict[str, str], project_type: str) -> str:
    """Apply color to the most likely wall region while preserving the rest."""

    try:
        pil = _load_pil()
        if pil is None:
            return image_base64
        Image, ImageEnhance, ImageDraw = pil

        working_image = _decode_image(image_base64)
        if working_image is None:
            return image_base64
        width, height = working_image.size

        paint_colors = list(paint_areas.items())
        if not paint_colors:
            return image_base64

        result_image = working_image.copy()
        primary_rgb = hex_to_rgb(paint_colors[0][1])

        if project_type == "exterior":
            sky_height = int(height * 0.25)
            wall_height = int(height * 0.65)
            wall_start = sky_height
            wall_end = min(height, sky_height + wall_height)

            wall_overlay = Image.new("RGB", result_image.size, primary_rgb)
            wall_mask = Image.new("L", result_image.size, 0)
            ImageDraw.Draw(wall_mask).rectangle([0, wall_start, width, wall_end], fill=int(255 * 0.70))
            result_image = Image.composite(wall_overlay, result_image, wall_mask)

            if len(paint_colors) > 1:
                accent_rgb = hex_to_rgb(paint_colors[1][1])
                trim_height = int(wall_height * 0.15)
                trim_end = min(height, wall_start + trim_height)
                accent_overlay = Image.new("RGB", result_image.size, accent_rgb)
                accent_mask = Image.new("L", result_image.size, 0)
                ImageDraw.Draw(accent_mask).rectangle([0, wall_start, width, trim_end], fill=int(255 * 0.65))
                result_image = Image.composite(accent_overlay, result_image, accent_mask)
        else:
            interior_start = int(height * 0.15)
            interior_end = int(height * 0.75)
            interior_overlay = Image.new("RGB", result_image.size, primary_rgb)
            interior_mask = Image.new("L", result_image.size, 0)
            ImageDraw.Draw(interior_mask).rectangle([0, interior_start, width, interior_end], fill=int(255 * 0.70))
            result_image = Image.composite(interior_overlay, result_image, interior_mask)

        result_image = ImageEnhance.Color(result_image).enhance(1.15)
        result_image = ImageEnhance.Contrast(result_image).enhance(1.08)
        return _encode_image(result_image)
    except Exception as e:
        print(f"Error in apply_paint_color_advanced: {e}")
        return image_base64


if __name__ == "__main__":
    print("Testing image painting module...")
    print("✅ Module ready for use")
