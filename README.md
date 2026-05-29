# PaintAI

PaintAI là ứng dụng web phối màu sơn kiến trúc bằng AI. Dự án dùng **FastAPI** cho backend, giao diện tĩnh trong thư mục `static/`, SQLite cho dữ liệu mẫu/màu sơn, và hỗ trợ tạo ảnh phối màu bằng Gemini hoặc OpenAI Image API. Khi chạy local có thể bật thêm pipeline AI nội bộ YOLO/SAM để phát hiện vùng kiến trúc.

## Tính năng chính

- Upload ảnh công trình và tạo phiên xử lý ảnh.
- Phát hiện/gợi ý vùng cần sơn cho nội thất hoặc ngoại thất.
- Chọn màu sơn theo mã HEX, danh mục màu, hãng sơn và bộ sưu tập.
- Tạo ảnh phối màu bằng AI image editing.
- So sánh ảnh gốc và ảnh sau phối màu trên giao diện.
- Lưu thiết kế và danh sách màu yêu thích.
- Hỗ trợ deploy serverless trên Vercel với dependency nhẹ.
- Hỗ trợ YOLO/SAM local nếu cần xử lý AI offline.

## Công nghệ

- Backend: FastAPI, Uvicorn, Pydantic
- Frontend: HTML, CSS, JavaScript, Tailwind CDN, Babel CDN
- Image processing: Pillow, NumPy
- Database: SQLite (`database.db`)
- AI image providers: Gemini, OpenAI Image API
- Local AI tùy chọn: YOLOv8, Torch, OpenCV, SAM

## Cài đặt local

### 1. Tạo môi trường Python

```bash
python -m venv .venv
.\.venv\Scripts\activate
```

Trên macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Cài dependency

```bash
pip install -r requirements.txt
```

`requirements.txt` chỉ chứa các gói nhẹ phù hợp cho local cơ bản và deploy Vercel. Nếu cần YOLO/SAM local, xem mục **AI local tùy chọn**.

### 3. Tạo file `.env`

Sao chép từ `.env.example`:

```bash
copy .env.example .env
```

Trên macOS/Linux:

```bash
cp .env.example .env
```

Cấu hình tối thiểu khi dùng Gemini:

```env
GEMINI_API_KEY=your-gemini-api-key
AI_IMAGE_PROVIDER=gemini
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
DISABLE_LOCAL_AI=1
AI_IMAGE_REQUEST_TIMEOUT_SECONDS=90
```

### 4. Chạy server

```bash
python server.py
```

Hoặc:

```bash
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Mở trình duyệt tại:

```text
http://127.0.0.1:8000
```

## Biến môi trường

Biến thường dùng:

```env
AI_IMAGE_PROVIDER=gemini
AI_IMAGE_REQUEST_TIMEOUT_SECONDS=90
DISABLE_LOCAL_AI=1
PAINT_SESSIONS_DIR=./paint_sessions
DATABASE_PATH=./database.db
```

Gemini:

```env
GEMINI_API_KEY=your-gemini-api-key
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
```

OpenAI Image API:

```env
OPENAI_API_KEY=your-openai-api-key
OPENAI_IMAGE_MODEL=gpt-image-1
OPENAI_IMAGE_SIZE=1024x1024
OPENAI_IMAGE_QUALITY=medium
```

Ghi chú:

- `AI_IMAGE_PROVIDER` có thể là `local`, `gemini`, `nano-banana`, `openai` hoặc `gpt-image`.
- `DISABLE_LOCAL_AI=1` nên được bật khi deploy serverless để tránh import Torch/OpenCV.
- API key nhập từ giao diện có thể được gửi kèm request và sẽ ưu tiên hơn biến môi trường tương ứng.

## Workflow phối màu AI

```text
Người dùng upload ảnh
  -> chọn loại công trình/nội thất/ngoại thất
  -> hệ thống phát hiện hoặc nhận danh sách vùng cần sơn
  -> người dùng chọn màu cho từng vùng
  -> frontend gửi ảnh, vùng sơn và màu HEX về backend
  -> backend chuẩn hóa prompt phối màu kiến trúc
  -> Gemini/OpenAI tạo ảnh phối màu mới
  -> frontend hiển thị ảnh kết quả để so sánh
```

Ví dụ payload tạo ảnh:

```json
{
  "image": "data:image/jpeg;base64,...",
  "projectType": "exterior",
  "paintAreas": {
    "wall-main": "#C8B08A",
    "trim": "#222222"
  },
  "detectedAreas": [
    {
      "id": "wall-main",
      "label": "main exterior wall / facade wall paintable surface",
      "displayLabel": "Tường chính",
      "hex": "#C8B08A"
    }
  ],
  "imageProvider": "gemini",
  "api_key": null
}
```

## API chính

Danh mục và dữ liệu:

```http
GET /api/project-types
GET /api/brands
GET /api/collections
GET /api/collections/{id}/layers
GET /api/colors
GET /paint_colors_extracted.json
```

Ảnh và phối màu:

```http
POST /api/upload-image
POST /api/apply-paint
GET  /api/paint-image/{image_id}
GET  /api/proxy-image?url=...
```

AI:

```http
GET  /api/ai/sam-status
POST /api/ai-colorize
GET  /api/ai/test-key
POST /api/ai/test-key
POST /api/ai/generate-colors
```

Lưu thiết kế và màu yêu thích:

```http
POST   /api/saved-designs
GET    /api/saved-designs
DELETE /api/saved-designs/{id}
POST   /api/favorites/colors/{color_id}
GET    /api/favorites/colors
DELETE /api/favorites/colors/{color_id}
```

## Deploy Vercel

Repo đã có cấu hình sẵn:

- `api/index.py` re-export FastAPI app cho Vercel.
- `vercel.json` route `/api/*` vào serverless function và route static file vào `static/`.
- `DISABLE_LOCAL_AI=1` được set để tránh tải các gói AI nặng trên serverless.

Các biến môi trường nên set trong Vercel Dashboard:

```env
GEMINI_API_KEY=your-gemini-api-key
AI_IMAGE_PROVIDER=gemini
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
DISABLE_LOCAL_AI=1
AI_IMAGE_REQUEST_TIMEOUT_SECONDS=90
```

Deploy bằng Vercel CLI:

```bash
vercel
```

Không upload `.env` lên Vercel. Dùng Environment Variables trong dashboard.

## AI local tùy chọn

Nếu muốn chạy YOLO/SAM local:

```bash
pip install -r requirements-local-ai.txt
```

Sau đó tắt cờ disable local AI trong `.env`:

```env
DISABLE_LOCAL_AI=0
```

Không đưa `torch`, `ultralytics`, `opencv-python` vào `requirements.txt` khi deploy Vercel vì dễ làm build fail hoặc vượt giới hạn serverless.

## Cấu trúc dự án

```text
.
├── api/
│   └── index.py                  # Entrypoint Vercel serverless
├── static/
│   ├── index.html                # Giao diện chính
│   ├── app.js                    # Logic frontend
│   ├── ai-editor.js              # UI/logic AI editor
│   ├── style.css                 # CSS
│   └── danh_sach_mau_son_chuan.json
├── ai_image_provider.py          # Tích hợp Gemini/OpenAI image editing
├── image_painter.py              # Xử lý ảnh local
├── sam_segmenter.py              # SAM tùy chọn
├── yolo_detector.py              # YOLO tùy chọn
├── server.py                     # FastAPI app
├── seed_db.py                    # Seed dữ liệu SQLite
├── requirements.txt              # Dependency nhẹ
├── requirements-local-ai.txt     # Dependency AI local tùy chọn
├── vercel.json                   # Cấu hình Vercel
└── database.db                   # SQLite local
```

## Kiểm tra

Chạy smoke test:

```bash
python -m pytest test_smoke.py ai_image_provider_test.py
```

Kiểm tra cú pháp JavaScript:

```bash
node --check static/app.js
node --check static/ai-editor.js
```

## Lỗi thường gặp

### Thiếu hoặc sai API key

Kiểm tra `GEMINI_API_KEY` hoặc `OPENAI_API_KEY` trong `.env`. Nếu nhập key trên giao diện, key đó sẽ được gửi theo request và có thể ghi đè biến môi trường.

### Gemini trả lỗi quota 429

Key hợp lệ nhưng project không có quota image generation. Cần bật billing, đổi project hoặc dùng provider khác có quota.

### Vercel build fail vì Torch/OpenCV

Dùng `requirements.txt` cho deploy. Các gói nặng chỉ để trong `requirements-local-ai.txt` và chỉ cài khi chạy local.

### Ảnh ngoài bị lỗi CORS

Dùng proxy ảnh:

```text
/api/proxy-image?url=https://example.com/image.jpg
```

### Tạo ảnh bị timeout

Tăng `AI_IMAGE_REQUEST_TIMEOUT_SECONDS` tối đa 180 giây, giảm kích thước ảnh upload hoặc chạy backend ở môi trường server/API riêng thay vì serverless.
