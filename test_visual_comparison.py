#!/usr/bin/env python3
"""
Visual Test - Compare Original vs Painted Image
"""

import base64
import io
import requests
import json
import sys
from PIL import Image
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

__test__ = False

API_BASE = "http://127.0.0.1:8000"

def response_error_message(result):
    return result.get("message") or result.get("detail") or result.get("error") or "Unknown error"

def create_test_image_with_details():
    """Create a more detailed test image with distinct areas"""
    img = Image.new('RGB', (500, 400), color=(200, 200, 200))
    pixels = img.load()
    
    # Draw different colored regions to simulate walls, ceiling, trim
    # Top region (ceiling) - light color
    for i in range(500):
        for j in range(0, 100):
            pixels[i, j] = (220, 220, 220)
    
    # Middle region (main wall) - medium color
    for i in range(500):
        for j in range(100, 300):
            pixels[i, j] = (180, 170, 160)
    
    # Bottom region (trim) - darker color
    for i in range(500):
        for j in range(300, 400):
            pixels[i, j] = (150, 140, 130)
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return f"data:image/png;base64,{base64_image}", img

def compare_images(original_b64, painted_b64):
    """Compare two images and show difference"""
    
    # Decode original
    if "," in original_b64:
        _, orig_data = original_b64.split(",", 1)
    else:
        orig_data = original_b64
    orig_img = Image.open(io.BytesIO(base64.b64decode(orig_data)))
    
    # Decode painted
    if "," in painted_b64:
        _, paint_data = painted_b64.split(",", 1)
    else:
        paint_data = painted_b64
    paint_img = Image.open(io.BytesIO(base64.b64decode(paint_data)))
    
    # Convert to numpy
    orig_array = np.array(orig_img, dtype=np.uint8)
    paint_array = np.array(paint_img, dtype=np.uint8)
    
    # Calculate differences
    diff = np.abs(orig_array.astype(np.float32) - paint_array.astype(np.float32))
    avg_diff = np.mean(diff)
    max_diff = np.max(diff)
    
    # Per-region analysis
    height, width = orig_array.shape[:2]
    
    print("\n📊 ẢNH GỐCVS ẢNH ĐÃ XỬ LÝ - PHÂN TÍCH CHI TIẾT\n")
    print("="*60)
    
    regions = [
        ("Vùng Trần Nhà (0-100px)", 0, 100),
        ("Vùng Tường Chính (100-300px)", 100, 300),
        ("Vùng Phào Chỉ (300-400px)", 300, 400)
    ]
    
    for region_name, y_start, y_end in regions:
        orig_region = orig_array[y_start:y_end, :, :]
        paint_region = paint_array[y_start:y_end, :, :]
        
        orig_avg = np.mean(orig_region, axis=(0, 1))
        paint_avg = np.mean(paint_region, axis=(0, 1))
        
        region_diff = np.mean(np.abs(orig_region.astype(np.float32) - paint_region.astype(np.float32)))
        
        print(f"\n{region_name}:")
        print(f"  Màu ảnh gốc (avg):  RGB({int(orig_avg[0])}, {int(orig_avg[1])}, {int(orig_avg[2])})")
        print(f"  Màu ảnh sơn (avg):  RGB({int(paint_avg[0])}, {int(paint_avg[1])}, {int(paint_avg[2])})")
        print(f"  Độ khác biệt:       {region_diff:.1f} (0-255 scale)")
        
        if region_diff > 20:
            print(f"  ✅ Màu ĐÃ THAY ĐỔI RÕ RỀT")
        elif region_diff > 10:
            print(f"  ⚠️  Màu thay đổi nhẹ")
        else:
            print(f"  ❌ Màu KHÔNG thay đổi (hoặc rất tối)")
    
    print("\n" + "="*60)
    print(f"\n📈 THỐNG KÊ CHUNG:")
    print(f"  - Độ khác biệt trung bình: {avg_diff:.2f} (0-255 scale)")
    print(f"  - Độ khác biệt tối đa: {max_diff:.2f}")
    
    if avg_diff > 30:
        print(f"\n✅ THÀNH CÔNG: Ảnh đã được phối màu rõ rệt!")
        print(f"   (Khác biệt >30 là rõ thấy bằng mắt)")
    elif avg_diff > 15:
        print(f"\n⚠️  NHẸ: Ảnh có thay đổi nhưng không rõ lắm")
        print(f"   (Khác biệt 15-30 là thay đổi nhẹ)")
    else:
        print(f"\n❌ THẤT BẠI: Ảnh gần như không thay đổi")
        print(f"   (Khác biệt <15 rất khó nhìn thấy)")

def main():
    print("\n" + "🎨 VISUAL TEST - So Sánh Ảnh Gốc vs Ảnh Sơn ".center(60, "=") + "\n")
    
    # Create test image
    print("📸 Tạo ảnh test với 3 vùng khác nhau...")
    test_image_b64, original_pil = create_test_image_with_details()
    print(f"✅ Ảnh test: {original_pil.size} pixels")
    
    # Call API
    print("\n📤 Gọi API /api/ai/generate-colors...")
    payload = {
        "image": test_image_b64,
        "projectType": "interior",
        "paintAreas": {
            "ceiling": "#FF5733",      # Red - cho trần
            "wall-main": "#33FF57",    # Green - cho tường chính
            "trim": "#3357FF"          # Blue - cho phào chỉ
        },
        "detectedAreas": [
            {
                "id": "ceiling",
                "type": "ceiling",
                "box_2d": [0, 0, 250, 1000],
                "polygon_2d": [[0, 0], [0, 1000], [250, 1000], [250, 0]],
                "seed_points_2d": [[125, 500]],
            },
            {
                "id": "wall-main",
                "type": "wall",
                "box_2d": [250, 0, 750, 1000],
                "polygon_2d": [[250, 0], [250, 1000], [750, 1000], [750, 0]],
                "seed_points_2d": [[500, 500]],
            },
            {
                "id": "trim",
                "type": "trim",
                "box_2d": [750, 0, 1000, 1000],
                "polygon_2d": [[750, 0], [750, 1000], [1000, 1000], [1000, 0]],
                "seed_points_2d": [[875, 500]],
            },
        ],
        "api_key": None
    }
    
    try:
        response = requests.post(
            f"{API_BASE}/api/ai/generate-colors",
            json=payload,
            timeout=30
        )
        result = response.json()
        
        if result.get('success') and result.get('data', {}).get('image'):
            painted_image_b64 = result['data']['image']
            print(f"✅ Nhận được ảnh đã xử lý")
            
            # Compare
            compare_images(test_image_b64, painted_image_b64)
            
        else:
            print(f"❌ API lỗi: {response_error_message(result)}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Lỗi: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
