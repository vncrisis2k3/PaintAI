#!/usr/bin/env python3
"""
Test Full Paint AI System with PIL
Kiểm tra toàn bộ quy trình: Upload ảnh -> Chọn màu -> AI xử lý ảnh -> Trả về ảnh
"""

import requests
import json
import base64
import sys
from pathlib import Path
from PIL import Image
import io

# API Configuration
API_BASE = "http://127.0.0.1:8000"

def print_header(title):
    """Print section header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")

def test_server_connection():
    """Test if server is running"""
    print_header("TEST 1: Kiểm Tra Kết Nối Server")
    try:
        response = requests.get(f"{API_BASE}/api/project-types", timeout=5)
        if response.status_code == 200:
            print("✅ Server đang chạy bình thường")
            data = response.json()
            print(f"✅ Số lượng loại công trình: {len(data.get('data', []))}")
            return True
        else:
            print(f"❌ Server trả về status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Lỗi kết nối: {str(e)}")
        return False

def create_test_image():
    """Create a simple test image"""
    print_header("TEST 2: Tạo Ảnh Test")
    try:
        # Create a simple gradient image (400x300)
        img = Image.new('RGB', (400, 300))
        pixels = img.load()
        
        # Create a gradient
        for i in range(400):
            for j in range(300):
                r = int(255 * i / 400)
                g = int(255 * j / 300)
                b = 128
                pixels[i, j] = (r, g, b)
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        print(f"✅ Ảnh test được tạo: {img.size} pixels")
        print(f"✅ Kích thước base64: {len(base64_image)} bytes ({len(base64_image)/1024:.1f} KB)")
        
        return f"data:image/png;base64,{base64_image}"
    except Exception as e:
        print(f"❌ Lỗi tạo ảnh: {str(e)}")
        return None

def test_paint_colors_endpoint(image_base64):
    """Test the /api/ai/generate-colors endpoint"""
    print_header("TEST 3: Kiểm Tra Endpoint /api/ai/generate-colors")
    
    if not image_base64:
        print("❌ Không có ảnh test")
        return False
    
    # Test payload
    payload = {
        "image": image_base64,
        "projectType": "interior",
        "paintAreas": {
            "wall-main": "#FF5733",      # Red color
            "accent": "#33FF57",         # Green color
            "ceiling": "#3357FF"         # Blue color
        },
        "api_key": None
    }
    
    print(f"📤 Gửi request tới /api/ai/generate-colors")
    print(f"   - Project Type: {payload['projectType']}")
    print(f"   - Paint Areas: {json.dumps(payload['paintAreas'], indent=2)}")
    print(f"   - Image Size: {len(payload['image'])} bytes")
    
    try:
        response = requests.post(
            f"{API_BASE}/api/ai/generate-colors",
            json=payload,
            timeout=30
        )
        
        print(f"📥 Response Status: {response.status_code}")
        result = response.json()
        
        if result.get('success'):
            print("✅ API trả về SUCCESS")
            print(f"   - Message: {result.get('message')}")
            
            if result.get('data') and result['data'].get('image'):
                generated_image = result['data']['image']
                image_size = len(generated_image)
                print(f"✅ Ảnh được tạo thành công!")
                print(f"   - Kích thước: {image_size} bytes ({image_size/1024:.1f} KB)")
                print(f"   - Format: Base64 PNG")
                
                # Try to decode and verify
                try:
                    if "," in generated_image:
                        _, base64_data = generated_image.split(",", 1)
                    else:
                        base64_data = generated_image
                    
                    image_bytes = base64.b64decode(base64_data)
                    img = Image.open(io.BytesIO(image_bytes))
                    print(f"   - Kích thước ảnh: {img.size} pixels")
                    print(f"   - Mode: {img.mode}")
                    return True
                except Exception as e:
                    print(f"⚠️  Cảnh báo: Không thể decode ảnh: {str(e)}")
                    return False
            else:
                print("❌ Không nhận được ảnh từ API")
                return False
        else:
            print(f"❌ API trả về FAILED")
            print(f"   - Message: {result.get('message')}")
            if result.get('details'):
                print(f"   - Details: {json.dumps(result.get('details'), indent=2)}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ Timeout (30s): Endpoint phản hồi quá chậm")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Lỗi kết nối: Không thể kết nối tới API")
        return False
    except Exception as e:
        print(f"❌ Lỗi: {str(e)}")
        return False

def test_validation():
    """Test request validation"""
    print_header("TEST 4: Kiểm Tra Validation")
    
    test_cases = [
        {
            "name": "Missing image",
            "payload": {
                "image": "",
                "projectType": "interior",
                "paintAreas": {"wall": "#FF0000"}
            },
            "should_fail": True
        },
        {
            "name": "Invalid projectType",
            "payload": {
                "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "projectType": "invalid",
                "paintAreas": {"wall": "#FF0000"}
            },
            "should_fail": True
        },
        {
            "name": "Empty paintAreas",
            "payload": {
                "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "projectType": "interior",
                "paintAreas": {}
            },
            "should_fail": True
        }
    ]
    
    for test_case in test_cases:
        print(f"\n📋 Test: {test_case['name']}")
        try:
            response = requests.post(
                f"{API_BASE}/api/ai/generate-colors",
                json=test_case['payload'],
                timeout=5
            )
            
            result = response.json()
            is_failed = not result.get('success', True)
            
            if test_case['should_fail'] and is_failed:
                print(f"   ✅ PASS - Validation đúng: {result.get('message', 'Rejected')}")
            elif not test_case['should_fail'] and not is_failed:
                print(f"   ✅ PASS - Request chấp nhận")
            else:
                print(f"   ❌ FAIL - Kết quả không như mong đợi")
                
        except Exception as e:
            print(f"   ❌ ERROR: {str(e)}")

def main():
    """Run all tests"""
    print("\n" + "🎨 PAINT AI SYSTEM - FULL TEST ".center(80, "="))
    print("Testing PIL-based image processing for color application\n")
    
    # Test 1: Server connection
    if not test_server_connection():
        print("\n❌ Server không khả dụng. Vui lòng khởi động: python server.py")
        sys.exit(1)
    
    # Test 2: Create test image
    test_image = create_test_image()
    if not test_image:
        print("\n❌ Không thể tạo ảnh test")
        sys.exit(1)
    
    # Test 3: Paint colors endpoint
    success = test_paint_colors_endpoint(test_image)
    
    # Test 4: Validation
    test_validation()
    
    # Summary
    print_header("📊 KẾT QUẢ KIỂM TRA")
    if success:
        print("""
✅ HỆ THỐNG HOẠT ĐỘNG ĐÚNG!

Tóm tắt:
1. ✅ Server FastAPI đang chạy
2. ✅ API endpoints hoạt động
3. ✅ PIL image processing hoạt động
4. ✅ Ảnh phối màu được tạo thành công

Công nghệ sử dụng:
- Backend: FastAPI + PIL/Pillow
- Image Processing: NumPy array manipulation
- Output: Base64 PNG format

Quy trình:
1. Frontend tải ảnh lên
2. Chọn loại công trình (Nội thất/Ngoại thất)
3. Chọn màu sơn cho các vùng
4. Backend xử lý ảnh bằng PIL:
   - Decode base64 → Image object
   - Áp dụng màu qua array manipulation
   - Encode → Base64 PNG
5. Trả về ảnh đã phối màu
6. Frontend hiển thị với comparison slider
        """)
    else:
        print("""
❌ CÓ VẤN ĐỀ TRONG HỆ THỐNG

Kiểm tra:
1. Server đang chạy?
2. Các imports đúng chưa (PIL, numpy)?
3. File image_painter.py có tồn tại?
4. Validation errors nào?
        """)
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()
