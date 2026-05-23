#!/usr/bin/env python3
"""
Image Painting Module
Sử dụng Pillow để áp dụng màu sơn lên ảnh dựa trên tọa độ AI thông minh.
"""

import base64
import io
from typing import Dict, List, Optional, Any


def _load_pil():
    try:
        # Tích hợp thêm ImageChops để xử lý hòa trộn đa lớp (Multiply/Overlay)
        from PIL import Image, ImageEnhance, ImageDraw, ImageChops
        return Image, ImageEnhance, ImageDraw, ImageChops
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
    Image, _, _, _ = pil
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


def apply_paint_color_ai(
    image_base64: str,
    paint_areas: Dict[str, str],
    detected_areas: List[Dict[str, Any]],
    project_type: str
) -> str:
    """
    Hòa trộn màu sơn thông minh dựa trên tọa độ thực tế từ phân tích của Gemini.
    Giữ lại kết cấu bề mặt kiến trúc và bóng đổ tự nhiên nhờ Pillow ImageChops.
    """
    try:
        pil = _load_pil()
        if pil is None:
            return image_base64
        Image, ImageEnhance, ImageDraw, ImageChops = pil

        working_image = _decode_image(image_base64)
        if working_image is None or not paint_areas or not detected_areas:
            return image_base64

        width, height = working_image.size

        # Tạo một bản đồ tra cứu nhanh tọa độ từ danh sách Gemini trả về
        # Cấu trúc: {"wall-main": [ymin, xmin, ymax, xmax]}
        boxes_map = {}
        for area in detected_areas:
            if "id" in area and "box_2d" in area:
                boxes_map[area["id"]] = area["box_2d"]

        # Trích xuất ảnh xám (L) để làm bản đồ giữ độ sáng/bóng đổ (Shadow/Texture layer)
        shadow_base = working_image.convert("L")

        # Khởi tạo ảnh kết quả
        result_image = working_image.copy()

        # Duyệt qua từng vùng màu do người dùng chỉ định trên giao diện
        for area_id, hex_color in paint_areas.items():
            if area_id not in boxes_map:
                continue

            # Lấy và quy đổi tọa độ hệ 0-1000 của Gemini sang kích thước pixel thực tế
            ymin_n, xmin_n, ymax_n, xmax_n = boxes_map[area_id]
            ymin = int((ymin_n / 1000) * height)
            xmin = int((xmin_n / 1000) * width)
            ymax = int((ymax_n / 1000) * height)
            xmax = int((xmax_n / 1000) * width)

            # Đảm bảo không bị tràn pixel ra ngoài biên ảnh
            ymin, ymax = max(0, ymin), min(height, ymax)
            xmin, xmax = max(0, xmin), min(width, xmax)

            if (xmax - xmin) <= 0 or (ymax - ymin) <= 0:
                continue

            target_rgb = hex_to_rgb(hex_color)

            # Tạo lớp phủ màu sơn (Solid Color Layer) cho vùng cụ thể
            paint_overlay = Image.new("RGB", result_image.size, target_rgb)

            # Kỹ thuật Multiply Blend: Ép vân bề mặt và bóng đổ gốc vào lớp màu sơn mới
            # Giúp lớp sơn tiệp hẳn vào thớ tường, không bị bệt phẳng lỳ như vẽ paint
            blended_paint = ImageChops.multiply(paint_overlay, shadow_base.convert("RGB"))

            # Tạo mặt nạ trong suốt để giới hạn vùng hiển thị sơn đúng theo Bounding Box
            mask = Image.new("L", result_image.size, 0)
            draw = ImageDraw.Draw(mask)

            # fill=180 (tương đương ~70% opacity) tạo độ trong suốt nhẹ để giữ độ thực tế
            draw.rectangle([xmin, ymin, xmax, ymax], fill=180)

            # Đè lớp sơn thông minh lên ảnh hiện tại thông qua mặt nạ định vị
            result_image = Image.composite(blended_paint, result_image, mask)

        # Hậu kỳ: Tăng cường nhẹ độ tương phản để màu sơn kiến trúc tươi tắn và sắc nét hơn
        result_image = ImageEnhance.Contrast(result_image).enhance(1.05)

        return _encode_image(result_image)

    except Exception as e:
        print(f"Error in apply_paint_color_ai: {e}")
        return image_base64


def apply_paint_color_simple(image_base64: str, paint_areas: Dict[str, str], project_type: str) -> str:
    """Giữ nguyên hàm gốc để làm fallback nếu không có tọa độ AI"""
    try:
        pil = _load_pil()
        if pil is None: return image_base64
        Image, ImageEnhance, _, _ = pil

        working_image = _decode_image(image_base64)
        if working_image is None or not paint_areas: return image_base64

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
    """Giữ nguyên hàm gốc để làm chế độ dự phòng hình học"""
    try:
        pil = _load_pil()
        if pil is None: return image_base64
        Image, ImageEnhance, ImageDraw, _ = pil

        working_image = _decode_image(image_base64)
        if working_image is None: return image_base64
        width, height = working_image.size

        paint_colors = list(paint_areas.items())
        if not paint_colors: return image_base64

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
