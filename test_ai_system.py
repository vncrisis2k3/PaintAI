#!/usr/bin/env python3
"""
Test Script - Kiểm tra hệ thống phối màu AI Gemini
"""
import json
import os
import sys
import urllib.request
import base64
from pathlib import Path

# Load .env
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

API_KEY = os.environ.get("GEMINI_API_KEY")
BASE_URL = "http://127.0.0.1:8000"

def print_header(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_api_key():
    """Test 1: Kiểm tra API key Gemini"""
    print_header("TEST 1: Kiểm tra API Key Gemini")
    
    if not API_KEY:
        print("❌ LỖI: Không tìm thấy GEMINI_API_KEY trong .env")
        return False
    
    print(f"✅ API Key tìm thấy: {API_KEY[:10]}...{API_KEY[-10:]}")
    
    # Test endpoint test-key
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/ai/test-key")
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            
            if result.get("success"):
                print(f"✅ API Key hợp lệ: {result.get('message', 'OK')}")
                return True
            else:
                print(f"❌ API Key không hợp lệ: {result.get('message', 'Unknown error')}")
                return False
    except Exception as e:
        print(f"❌ Lỗi kết nối đến endpoint test-key: {e}")
        return False

def test_server_connection():
    """Test 2: Kiểm tra kết nối đến server"""
    print_header("TEST 2: Kiểm tra kết nối Server")
    
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/project-types")
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
            if result.get("success"):
                print(f"✅ Server hoạt động bình thường")
                print(f"   - Loại công trình: {len(result.get('data', []))} mục")
                return True
            else:
                print(f"❌ Server trả về lỗi: {result.get('message')}")
                return False
    except Exception as e:
        print(f"❌ Không thể kết nối đến server: {e}")
        print(f"   Server URL: {BASE_URL}")
        return False

def test_generate_colors_endpoint():
    """Test 3: Kiểm tra endpoint generate-colors"""
    print_header("TEST 3: Kiểm tra Endpoint /api/ai/generate-colors")
    
    # Tạo một ảnh test nhỏ (1x1 pixel)
    try:
        from PIL import Image
        import io
        
        # Tạo ảnh nhỏ (100x100) để test
        img = Image.new('RGB', (100, 100), color=(255, 100, 150))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_base64 = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
        
        print("✅ Ảnh test được tạo thành công (100x100 PNG)")
        
    except ImportError:
        print("⚠️  PIL không cài đặt, sử dụng ảnh base64 đơn giản")
        # Sử dụng ảnh base64 đơn giản (1x1 PNG)
        img_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    
    # Tạo payload
    payload = {
        "image": f"data:image/png;base64,{img_base64}",
        "projectType": "interior",
        "paintAreas": {
            "wall-main": "#FF6B6B",
            "accent": "#4ECDC4",
            "ceiling": "#FFFFFF"
        },
        "api_key": None
    }
    
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/ai/generate-colors",
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        print("📤 Gửi request tới /api/ai/generate-colors...")
        print(f"   - projectType: {payload['projectType']}")
        print(f"   - paintAreas: {list(payload['paintAreas'].keys())}")
        print(f"   - image size: ~{len(img_base64) // 1024}KB (base64)")
        
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
            
            if result.get("success"):
                print("✅ API trả về kết quả thành công")
                if result.get("data", {}).get("image"):
                    print(f"   ✅ Ảnh được tạo: {len(result['data']['image']) // 1024}KB (base64)")
                    return True
                else:
                    print("❌ Response không chứa ảnh")
                    print(f"   Response: {json.dumps(result, indent=2)[:200]}...")
                    return False
            else:
                print(f"❌ API trả về lỗi: {result.get('message')}")
                if result.get("error_type"):
                    print(f"   Loại lỗi: {result.get('error_type')}")
                return False
                
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"❌ HTTP Error {e.code}: {error_body}")
        return False
    except Exception as e:
        print(f"❌ Lỗi khi gọi endpoint: {e}")
        return False

def check_endpoint_logic():
    """Test 4: Phân tích logic của endpoint"""
    print_header("TEST 4: Phân tích Logic Generate-Colors Endpoint")
    
    # Đọc file server.py để kiểm tra logic
    try:
        with open("server.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        checks = [
            ("Kiểm tra hàm ai_generate_colors", "@app.post(\"/api/ai/generate-colors\")" in content),
            ("Kiểm tra validation image", "validate_image" in content),
            ("Kiểm tra validation paintAreas", "validate_paint_areas" in content),
            ("Kiểm tra Gemini system prompt", "photorealistically apply" in content),
            ("Kiểm tra base64 extraction", "base64" in content),
            ("Kiểm tra response format", "data:image/png" in content),
        ]
        
        for check_name, check_result in checks:
            status = "✅" if check_result else "❌"
            print(f"{status} {check_name}")
        
        return all(result for _, result in checks)
        
    except Exception as e:
        print(f"❌ Lỗi khi đọc file: {e}")
        return False

def main():
    """Chạy tất cả các test"""
    print("\n🔍 KIỂM TRA HỆ THỐNG PHỐI MÀU AI GEMINI")
    print("=" * 60)
    
    results = []
    
    # Test 1: Server connection
    results.append(("Kết nối Server", test_server_connection()))
    
    # Test 2: API Key
    results.append(("API Key Gemini", test_api_key()))
    
    # Test 3: Logic check
    results.append(("Logic Endpoint", check_endpoint_logic()))
    
    # Test 4: Generate colors (nếu các test trước thành công)
    if results[0][1] and results[1][1]:
        results.append(("Generate Colors", test_generate_colors_endpoint()))
    else:
        print("\n⚠️  Bỏ qua test Generate Colors do các test trước không thành công")
        results.append(("Generate Colors", False))
    
    # Summary
    print_header("TỔNG KẾT KẾT QUẢ TEST")
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    total_pass = sum(1 for _, result in results if result)
    total_tests = len(results)
    
    print(f"\nKết quả: {total_pass}/{total_tests} test thành công")
    
    if total_pass == total_tests:
        print("✅ HỆ THỐNG HOẠT ĐỘNG BÌNH THƯỜNG")
    else:
        print("❌ HỆ THỐNG CÓ VẤN ĐỀ - Xem chi tiết ở trên")
    
    return 0 if total_pass == total_tests else 1

if __name__ == "__main__":
    sys.exit(main())
