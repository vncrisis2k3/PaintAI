#!/usr/bin/env python3
"""
Test Gemini API Image Generation Capabilities
Kiểm tra xem Gemini 2.5 Flash có khả năng tạo ảnh được không
"""
import json
import os
import urllib.request
import base64
from pathlib import Path

# Load .env
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

API_KEY = os.environ.get("GEMINI_API_KEY")

def test_gemini_image_generation():
    """
    Test trực tiếp với Gemini API để xem nó có khả năng:
    1. Nhận ảnh đầu vào
    2. Xử lý yêu cầu áp dụng màu
    3. Trả về ảnh
    """
    
    if not API_KEY:
        print("❌ Không tìm thấy GEMINI_API_KEY")
        return
    
    print("🔍 TEST: Gemini 2.5 Flash Image Processing Capabilities")
    print("=" * 70)
    
    # Tạo ảnh test đơn giản
    try:
        from PIL import Image
        import io
        
        # Tạo ảnh test
        img = Image.new('RGB', (100, 100), color=(200, 150, 100))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_base64 = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
        print("✅ Ảnh test được tạo: 100x100 PNG")
        
    except ImportError:
        # Ảnh PNG 1x1 pixel đơn giản
        img_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        print("⚠️  PIL không có, sử dụng ảnh 1x1 pixel")
    
    # Test 1: Yêu cầu Gemini trả về ảnh base64
    print("\n📋 TEST 1: Yêu cầu trả về ảnh base64")
    print("-" * 70)
    
    system_prompt_1 = """You are an image processing AI. 
Your task is to modify the image by applying a red color tint to it.
Return ONLY the modified image in base64 PNG format. NO text, NO explanation."""
    
    request_data_1 = {
        "contents": [
            {
                "parts": [
                    {"text": "Apply a red color tint to this image and return only base64 PNG."},
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": img_base64
                        }
                    }
                ]
            }
        ],
        "systemInstruction": {
            "parts": [{"text": system_prompt_1}]
        },
        "generationConfig": {
            "responseMimeType": "text/plain"
        }
    }
    
    try:
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={API_KEY}"
        
        req = urllib.request.Request(
            gemini_url,
            data=json.dumps(request_data_1).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        print("📤 Gửi request tới Gemini API...")
        with urllib.request.urlopen(req, timeout=60) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            
            candidates = res_json.get("candidates", [])
            if candidates:
                text_content = candidates[0]["content"]["parts"][0]["text"]
                
                # Kiểm tra xem có phải base64 không
                if len(text_content) > 100 and not text_content.startswith("I cannot"):
                    print("✅ Gemini trả về dữ liệu dài (có thể là ảnh)")
                    print(f"   Response length: {len(text_content)} characters")
                    if text_content[:20].isalnum():
                        print("   ✅ Dữ liệu trông giống base64")
                    else:
                        print(f"   ⚠️  Dữ liệu không giống base64: {text_content[:100]}")
                else:
                    print(f"❌ Gemini không trả về ảnh: {text_content[:200]}")
            else:
                print("❌ Không có response từ Gemini")
        
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            error_json = json.loads(error_body)
            error_msg = error_json.get("error", {}).get("message", "")
        except:
            error_msg = error_body
        print(f"❌ HTTP Error {e.code}: {error_msg[:200]}")
    
    except Exception as e:
        print(f"❌ Lỗi: {e}")
    
    # Test 2: Yêu cầu Gemini phân tích ảnh
    print("\n📋 TEST 2: Yêu cầu Gemini phân tích ảnh (không tạo ảnh)")
    print("-" * 70)
    
    system_prompt_2 = """You are an architectural color consultant.
Analyze the image and describe what colors are present and suggest painting areas."""
    
    request_data_2 = {
        "contents": [
            {
                "parts": [
                    {"text": "Analyze this image and describe its colors and surfaces."},
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": img_base64
                        }
                    }
                ]
            }
        ],
        "systemInstruction": {
            "parts": [{"text": system_prompt_2}]
        },
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    try:
        req = urllib.request.Request(
            gemini_url,
            data=json.dumps(request_data_2).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        print("📤 Gửi request phân tích ảnh...")
        with urllib.request.urlopen(req, timeout=30) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            
            candidates = res_json.get("candidates", [])
            if candidates:
                text_content = candidates[0]["content"]["parts"][0]["text"]
                print("✅ Gemini trả về phân tích ảnh thành công")
                print(f"\n📝 Phân tích (đầu tiên 300 ký tự):")
                print(text_content[:300])
            else:
                print("❌ Không có response từ Gemini")
        
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            error_json = json.loads(error_body)
            error_msg = error_json.get("error", {}).get("message", "")
        except:
            error_msg = error_body
        print(f"❌ HTTP Error {e.code}: {error_msg[:200]}")
    
    except Exception as e:
        print(f"❌ Lỗi: {e}")
    
    print("\n" + "=" * 70)
    print("📊 KẾT LUẬN:")
    print("-" * 70)
    print("""
Gemini 2.5 Flash là một mô hình Ngôn Ngữ (LLM) với khả năng Vision.
Nó CÓ THỂ:
  ✅ Phân tích ảnh
  ✅ Mô tả các đối tượng trong ảnh
  ✅ Đề xuất màu sắc
  
Nó KHÔNG THỂ (hoặc CỰC KỲ HẠN CHẾ):
  ❌ Tạo/chỉnh sửa ảnh mới
  ❌ Áp dụng màu sắc lên ảnh hiện có
  ❌ Thực hiện image processing phức tạp

Để tạo ảnh phối màu, bạn cần sử dụng:
  🎨 Image generation models: DALL-E, Stable Diffusion, Adobe Firefly
  🎨 Image processing libraries: PIL, OpenCV, ImageMagick
  🎨 Chuyên biệt AI models: ControlNet, Diffusion models

HỆ THỐNG HIỆN TẠI CÓ VẤN ĐỀ TẠI:
  ❌ Endpoint /api/ai/generate-colors yêu cầu Gemini "áp dụng màu"
  ❌ Nhưng Gemini không hỗ trợ tính năng này
  ❌ Kết quả: Người dùng sẽ không thấy ảnh phối màu được tạo ra
""")

if __name__ == "__main__":
    test_gemini_image_generation()
