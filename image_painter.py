#!/usr/bin/env python3
"""
Image Painting Module - AI Optimized
Sử dụng Pillow xử lý mặt nạ và hòa trộn đa lớp dựa trên tọa độ box_2d từ AI.
"""

import base64
import io
from typing import Dict, List, Optional, Any

def _load_pil():
    try:
        from PIL import Image, ImageEnhance, ImageDraw, ImageChops
        return Image, ImageEnhance, ImageDraw, ImageChops
    except ImportError:
        return None

def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

def _decode_image(image_base64: str):
    pil = _load_pil()
    if pil is None: return None
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

def apply_paint_color_ai(image_base64: str, paint_areas: Dict[str, str], detected_areas: List[Dict[str, Any]], project_type: str) -> str:
    """Đổ màu thông minh khít theo tọa độ box_2d thực tế từ Gemini"""
    try:
        pil = _load_pil()
        if pil is None: return image_base64
        Image, ImageEnhance, ImageDraw, ImageChops = pil

        working_image = _decode_image(image_base64)
        if working_image is None or not paint_areas or not detected_areas:
            return image_base64

        width, height = working_image.size
        result_image = working_image.copy()
        shadow_base = working_image.convert("L")

        # Map nhanh dữ liệu vùng từ client lên dictionary để tra cứu
        boxes_map = {}
        for area in detected_areas:
            # Chấp nhận cả 2 kiểu viết camelCase hoặc snake_case từ Frontend
            a_id = area.get("id") or area.get("area_id")
            a_box = area.get("box_2d") or area.get("box2d")
            if a_id and a_box and len(a_box) == 4:
                boxes_map[str(a_id).lower()] = a_box

        # Duyệt qua các vùng màu người dùng chọn phối
        for area_id, hex_color in paint_areas.items():
            search_key = str(area_id).lower()
            if search_key not in boxes_map:
                continue

            # Tọa độ gốc hệ 0-1000 của Gemini
            ymin_n, xmin_n, ymax_n, xmax_n = boxes_map[search_key]
            
            # Quy đổi sang pixel thực tế
            ymin = int((ymin_n / 1000) * height)
            xmin = int((xmin_n / 1000) * width)
            ymax = int((ymax_n / 1000) * height)
            xmax = int((xmax_n / 1000) * width)

            # Ranh giới an toàn cho ảnh
            ymin, ymax = max(0, ymin), min(height, ymax)
            xmin, xmax = max(0, xmin), min(width, xmax)

            if (xmax - xmin) <= 0 or (ymax - ymin) <= 0:
                continue

            target_rgb = hex_to_rgb(hex_color)
            paint_overlay = Image.new("RGB", result_image.size, target_rgb)
            
            # Blend vân bề mặt thô gốc vào lớp sơn mới
            blended_paint = ImageChops.multiply(paint_overlay, shadow_base.convert("RGB"))

            # Tạo mặt nạ vùng đổ màu chính xác theo tọa độ
            mask = Image.new("L", result_image.size, 0)
            draw = ImageDraw.Draw(mask)
            draw.rectangle([xmin, ymin, xmax, ymax], fill=165) # Độ mờ vừa phải giữ chiều sâu

            result_image = Image.composite(blended_paint, result_image, mask)

        result_image = ImageEnhance.Contrast(result_image).enhance(1.05)
        return _encode_image(result_image)
    except Exception as e:
        print(f"Lỗi apply_paint_color_ai: {e}")
        return image_base64

def apply_paint_color_advanced(image_base64: str, paint_areas: Dict[str, str], project_type: str) -> str:
    """Hàm dự phòng gốc - Chỉ kích hoạt khi không lấy được tọa độ AI"""
    try:
        pil = _load_pil()
        if pil is None: return image_base64
        Image, ImageEnhance, ImageDraw, _ = pil
        working_image = _decode_image(image_base64)
        if working_image is None or not paint_areas: return image_base64
        width, height = working_image.size
        result_image = working_image.copy()
        
        paint_colors = list(paint_areas.items())
        primary_rgb = hex_to_rgb(paint_colors[0][1])

        # Vẽ khối hình học thô nếu luồng AI đứt gãy
        wall_start, wall_end = int(height * 0.25), int(height * 0.90)
        wall_overlay = Image.new("RGB", result_image.size, primary_rgb)
        wall_mask = Image.new("L", result_image.size, 0)
        ImageDraw.Draw(wall_mask).rectangle([0, wall_start, width, wall_end], fill=140)
        result_image = Image.composite(wall_overlay, result_image, wall_mask)

        return _encode_image(result_image)
    except Exception as e:
        print(f"Lỗi apply_paint_color_advanced: {e}")
        return image_base64