# PaintAI

PaintAI là ứng dụng web giúp phối màu sơn kiến trúc bằng AI. Hệ thống hiện tại sử dụng FastAPI ở backend, giao diện JavaScript thuần ở frontend, và Gemini image editing (`gemini-2.5-flash-image`) để tạo ảnh phối màu từ ảnh gốc và màu sơn người dùng chọn.

## Tổng Quan Workflow Phối Màu AI

```text
Người dùng upload ảnh
  -> chọn Nội thất hoặc Ngoại thất
  -> chọn màu HEX cho từng chi tiết kiến trúc
  -> frontend gửi payload về backend
  -> backend đổi mã HEX thành tên màu tiếng Anh theo ngữ cảnh kiến trúc
  -> backend ghép prompt tiếng Anh chuẩn hóa
  -> backend gửi ảnh gốc + prompt sang Gemini image API
  -> Gemini trả về ảnh base64
  -> frontend hiển thị thanh trượt so sánh Trước/Sau
```

Ví dụ phần màu trong prompt backend tạo ra:

```text
- wall-main (main exterior facade wall): soft warm beige, exact paint HEX #C8B08A
- trim (trim): charcoal black, exact paint HEX #222222
```

## Tính Năng Chính

- Upload ảnh công trình định dạng JPG, PNG, WEBP.
- Chọn luồng nội thất hoặc ngoại thất.
- Gán màu sơn cho từng chi tiết kiến trúc.
- Tạo ảnh phối màu bằng Gemini image editing.
- So sánh ảnh gốc và ảnh AI bằng thanh trượt Before/After.
- Xem thư viện màu sơn, mẫu công trình, thiết kế đã lưu.
- Hỗ trợ tùy chọn stack AI local YOLO/SAM khi chạy ngoài môi trường serverless.

## Cài Đặt Và Chạy Local

### 1. Cài dependency

```bash
pip install -r requirements.txt
```

`requirements.txt` hiện chỉ gồm các gói nhẹ phù hợp cho Vercel/serverless. Nếu cần YOLO/SAM local, xem mục **AI Local Tùy Chọn** bên dưới.

### 2. Tạo file `.env`

Tạo file `.env` ở thư mục gốc:

```env
GEMINI_API_KEY=your-gemini-api-key
AI_IMAGE_PROVIDER=gemini
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
DISABLE_LOCAL_AI=1
```

### 3. Chạy server

```bash
python server.py
```

Hoặc:

```bash
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Mở trình duyệt:

```text
http://127.0.0.1:8000
```

## Lấy Gemini API Key

1. Vào Google AI Studio:

```text
https://aistudio.google.com/app/apikey
```

2. Đăng nhập tài khoản Google.
3. Bấm **Create API key**.
4. Chọn hoặc tạo Google Cloud Project.
5. Copy key và đưa vào `.env`:

```env
GEMINI_API_KEY=your-gemini-api-key
```

Trên giao diện ứng dụng cũng có nút **API Key**. Nếu nhập key trên giao diện, key sẽ được lưu trong `localStorage` của trình duyệt và gửi kèm mỗi request AI.

Thứ tự ưu tiên API key:

```text
API key nhập trên giao diện
  -> GEMINI_API_KEY trong biến môi trường
```

Nếu đổi key trong giao diện thì không cần restart server. Nếu đổi key trong `.env` thì phải restart server.

## Lưu Ý Về Quota Gemini

Model `gemini-2.5-flash-image` có thể không có quota miễn phí đủ để xử lý ảnh thật. Nếu gặp lỗi:

```text
429 RESOURCE_EXHAUSTED
Quota exceeded
free_tier_requests, limit: 0
```

thì project/key hiện tại không có quota image generation khả dụng. Cần bật billing hoặc dùng key/project khác có quota:

```text
https://ai.dev/rate-limit
https://ai.google.dev/gemini-api/docs/rate-limits
```

## API Chính

Danh mục:

```http
GET /api/project-types
GET /api/brands
GET /api/collections
GET /api/colors
```

AI:

```http
GET  /api/ai/test-key
POST /api/ai/generate-colors
```

Proxy ảnh:

```http
GET /api/proxy-image?url=...
```

## Payload Tạo Ảnh Phối Màu

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

Provider hỗ trợ:

```text
local
openai
gpt-image
gemini
nano-banana
```

Frontend hiện đang gửi `imageProvider: "gemini"` khi người dùng bấm tạo ảnh AI.

## Biến Môi Trường

Bắt buộc cho Gemini image generation:

```env
GEMINI_API_KEY=your-gemini-api-key
AI_IMAGE_PROVIDER=gemini
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
```

Khuyến nghị khi deploy Vercel:

```env
DISABLE_LOCAL_AI=1
AI_IMAGE_REQUEST_TIMEOUT_SECONDS=90
```

Tùy chọn OpenAI image provider:

```env
OPENAI_API_KEY=your-openai-api-key
OPENAI_IMAGE_MODEL=gpt-image-1
OPENAI_IMAGE_SIZE=1024x1024
OPENAI_IMAGE_QUALITY=medium
```

Tùy chọn lưu trữ local:

```env
PAINT_SESSIONS_DIR=./paint_sessions
DATABASE_PATH=./database.db
```

## Deploy Lên Vercel

Repo đã cấu hình sẵn cho Vercel:

- `api/index.py` là entrypoint serverless FastAPI.
- `vercel.json` route `/api/*` về serverless function và route static asset về `/static`.
- `DISABLE_LOCAL_AI=1` để Vercel không import YOLO/Torch/OpenCV.
- `requirements.txt` chỉ gồm dependency nhẹ.

Cần set các biến môi trường sau trong Vercel Dashboard:

```env
GEMINI_API_KEY=your-gemini-api-key
AI_IMAGE_PROVIDER=gemini
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
DISABLE_LOCAL_AI=1
AI_IMAGE_REQUEST_TIMEOUT_SECONDS=90
```

Không upload `.env`; file này đã được ignore bởi `.vercelignore`.

Deploy bằng CLI:

```bash
vercel
```

Hoặc deploy qua Git integration của Vercel.

## AI Local Tùy Chọn

Mặc định deploy không cài các gói nặng như `torch`, `ultralytics`, `opencv-python`. Nếu muốn thử YOLO/SAM local, cài:

```bash
pip install -r requirements-local-ai.txt
```

Không đưa các gói này vào `requirements.txt` khi deploy Vercel, vì rất dễ làm build fail hoặc vượt giới hạn serverless.

## Cấu Trúc Dự Án

```text
.
├── api/
│   └── index.py                 # Entrypoint Vercel serverless
├── static/
│   ├── index.html               # Giao diện chính
│   ├── app.js                   # Logic frontend
│   ├── style.css                # CSS
│   └── danh_sach_mau_son_chuan.json
├── ai_image_provider.py         # Lớp gọi Gemini/OpenAI image provider
├── image_painter.py             # Xử lý ảnh local
├── sam_segmenter.py             # SAM tùy chọn
├── yolo_detector.py             # YOLO tùy chọn
├── server.py                    # FastAPI app
├── requirements.txt             # Dependency nhẹ cho deploy
├── requirements-local-ai.txt    # Dependency AI local tùy chọn
├── vercel.json                  # Cấu hình Vercel
└── database.db                  # SQLite catalog local
```

## Xử Lý Lỗi Thường Gặp

### Gemini key OK nhưng tạo ảnh lỗi 429

Key đúng, nhưng project không có quota cho image model. Cần bật billing hoặc dùng key/project khác có quota image generation.

### Lỗi unexpected model name format

Kiểm tra:

```env
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
```

Không điền API key hoặc URL vào `GEMINI_IMAGE_MODEL`.

### Vercel build fail do Torch/OpenCV

Dùng `requirements.txt` hiện tại. Không đưa `torch`, `ultralytics`, `opencv-python` vào `requirements.txt`; các gói này chỉ nằm trong `requirements-local-ai.txt`.

### Tạo ảnh bị timeout

Gemini image editing có thể chậm. Giới hạn thời gian chạy function phụ thuộc plan Vercel của bạn. Nếu gặp timeout, cần nâng plan, tối ưu kích thước ảnh upload, hoặc chạy backend ở môi trường server/API riêng thay vì serverless.

### Ảnh ngoài không hiển thị do CORS

Dùng endpoint proxy:

```text
/api/proxy-image?url=https://example.com/image.jpg
```

## Kiểm Tra Trước Khi Deploy

Chạy:

```bash
python -m pytest test_smoke.py ai_image_provider_test.py
node --check static/app.js
```

Kết quả mong đợi:

```text
tests pass
JavaScript syntax check passes
```
