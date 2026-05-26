# PaintAI

PaintAI la ung dung web giup phoi mau son kien truc bang AI. He thong hien tai su dung FastAPI o backend, giao dien JavaScript thuan o frontend, va Gemini image editing (`gemini-2.5-flash-image`) de tao anh phoi mau tu anh goc va mau son nguoi dung chon.

## Tong Quan Workflow Phoi Mau AI

```text
Nguoi dung upload anh
  -> chon Noi that hoac Ngoai that
  -> chon mau HEX cho tung chi tiet kien truc
  -> frontend gui payload ve backend
  -> backend doi ma HEX thanh ten mau tieng Anh theo ngu canh kien truc
  -> backend ghep prompt tieng Anh chuan hoa
  -> backend gui anh goc + prompt sang Gemini image API
  -> Gemini tra ve anh base64
  -> frontend hien thi thanh truot so sanh Truoc/Sau
```

Vi du phan mau trong prompt backend tao ra:

```text
- wall-main (main exterior facade wall): soft warm beige, exact paint HEX #C8B08A
- trim (trim): charcoal black, exact paint HEX #222222
```

## Tinh Nang Chinh

- Upload anh cong trinh dinh dang JPG, PNG, WEBP.
- Chon luong noi that hoac ngoai that.
- Gan mau son cho tung chi tiet kien truc.
- Tao anh phoi mau bang Gemini image editing.
- So sanh anh goc va anh AI bang thanh truot Before/After.
- Xem thu vien mau son, mau cong trinh, thiet ke da luu.
- Ho tro tuy chon stack AI local YOLO/SAM khi chay ngoai moi truong serverless.

## Cai Dat Va Chay Local

### 1. Cai dependency

```bash
pip install -r requirements.txt
```

`requirements.txt` hien chi gom cac goi nhe phu hop cho Vercel/serverless. Neu can YOLO/SAM local, xem muc **AI Local Tuy Chon** ben duoi.

### 2. Tao file `.env`

Tao file `.env` o thu muc goc:

```env
GEMINI_API_KEY=your-gemini-api-key
AI_IMAGE_PROVIDER=gemini
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
DISABLE_LOCAL_AI=1
```

### 3. Chay server

```bash
python server.py
```

Hoac:

```bash
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Mo trinh duyet:

```text
http://127.0.0.1:8000
```

## Lay Gemini API Key

1. Vao Google AI Studio:

```text
https://aistudio.google.com/app/apikey
```

2. Dang nhap tai khoan Google.
3. Bam **Create API key**.
4. Chon hoac tao Google Cloud Project.
5. Copy key va dua vao `.env`:

```env
GEMINI_API_KEY=your-gemini-api-key
```

Tren giao dien ung dung cung co nut **API Key**. Neu nhap key tren giao dien, key se duoc luu trong `localStorage` cua trinh duyet va gui kem moi request AI.

Thu tu uu tien API key:

```text
API key nhap tren giao dien
  -> GEMINI_API_KEY trong bien moi truong
```

Neu doi key trong giao dien thi khong can restart server. Neu doi key trong `.env` thi phai restart server.

## Luu Y Ve Quota Gemini

Model `gemini-2.5-flash-image` co the khong co quota mien phi du de xu ly anh that. Neu gap loi:

```text
429 RESOURCE_EXHAUSTED
Quota exceeded
free_tier_requests, limit: 0
```

thi project/key hien tai khong co quota image generation kha dung. Can bat billing hoac dung key/project khac co quota:

```text
https://ai.dev/rate-limit
https://ai.google.dev/gemini-api/docs/rate-limits
```

## API Chinh

Danh muc:

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

Proxy anh:

```http
GET /api/proxy-image?url=...
```

## Payload Tao Anh Phoi Mau

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
      "displayLabel": "Tuong chinh",
      "hex": "#C8B08A"
    }
  ],
  "imageProvider": "gemini",
  "api_key": null
}
```

Provider ho tro:

```text
local
openai
gpt-image
gemini
nano-banana
```

Frontend hien dang gui `imageProvider: "gemini"` khi nguoi dung bam tao anh AI.

## Bien Moi Truong

Bat buoc cho Gemini image generation:

```env
GEMINI_API_KEY=your-gemini-api-key
AI_IMAGE_PROVIDER=gemini
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
```

Khuyen nghi khi deploy Vercel:

```env
DISABLE_LOCAL_AI=1
AI_IMAGE_REQUEST_TIMEOUT_SECONDS=90
```

Tuy chon OpenAI image provider:

```env
OPENAI_API_KEY=your-openai-api-key
OPENAI_IMAGE_MODEL=gpt-image-1
OPENAI_IMAGE_SIZE=1024x1024
OPENAI_IMAGE_QUALITY=medium
```

Tuy chon luu tru local:

```env
PAINT_SESSIONS_DIR=./paint_sessions
DATABASE_PATH=./database.db
```

## Deploy Len Vercel

Repo da cau hinh san cho Vercel:

- `api/index.py` la entrypoint serverless FastAPI.
- `vercel.json` route `/api/*` ve serverless function va route static asset ve `/static`.
- `DISABLE_LOCAL_AI=1` de Vercel khong import YOLO/Torch/OpenCV.
- `requirements.txt` chi gom dependency nhe.

Can set cac bien moi truong sau trong Vercel Dashboard:

```env
GEMINI_API_KEY=your-gemini-api-key
AI_IMAGE_PROVIDER=gemini
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
DISABLE_LOCAL_AI=1
AI_IMAGE_REQUEST_TIMEOUT_SECONDS=90
```

Khong upload `.env`; file nay da duoc ignore boi `.vercelignore`.

Deploy bang CLI:

```bash
vercel
```

Hoac deploy qua Git integration cua Vercel.

## AI Local Tuy Chon

Mac dinh deploy khong cai cac goi nang nhu `torch`, `ultralytics`, `opencv-python`. Neu muon thu YOLO/SAM local, cai:

```bash
pip install -r requirements-local-ai.txt
```

Khong dua cac goi nay vao `requirements.txt` khi deploy Vercel, vi rat de lam build fail hoac vuot gioi han serverless.

## Cau Truc Du An

```text
.
├── api/
│   └── index.py                 # Entrypoint Vercel serverless
├── static/
│   ├── index.html               # Giao dien chinh
│   ├── app.js                   # Logic frontend
│   ├── style.css                # CSS
│   └── danh_sach_mau_son_chuan.json
├── ai_image_provider.py         # Lop goi Gemini/OpenAI image provider
├── image_painter.py             # Xu ly anh local
├── sam_segmenter.py             # SAM tuy chon
├── yolo_detector.py             # YOLO tuy chon
├── server.py                    # FastAPI app
├── requirements.txt             # Dependency nhe cho deploy
├── requirements-local-ai.txt    # Dependency AI local tuy chon
├── vercel.json                  # Cau hinh Vercel
└── database.db                  # SQLite catalog local
```

## Xu Ly Loi Thuong Gap

### Gemini key OK nhung tao anh loi 429

Key dung, nhung project khong co quota cho image model. Can bat billing hoac dung key/project khac co quota image generation.

### Loi unexpected model name format

Kiem tra:

```env
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
```

Khong dien API key hoac URL vao `GEMINI_IMAGE_MODEL`.

### Vercel build fail do Torch/OpenCV

Dung `requirements.txt` hien tai. Khong dua `torch`, `ultralytics`, `opencv-python` vao `requirements.txt`; cac goi nay chi nam trong `requirements-local-ai.txt`.

### Tao anh bi timeout

Gemini image editing co the cham. `vercel.json` hien dat `maxDuration` la 60 giay, nhung gioi han thuc te phu thuoc plan Vercel cua ban.

### Anh ngoai khong hien thi do CORS

Dung endpoint proxy:

```text
/api/proxy-image?url=https://example.com/image.jpg
```

## Kiem Tra Truoc Khi Deploy

Chay:

```bash
python -m pytest test_smoke.py ai_image_provider_test.py
node --check static/app.js
```

Ket qua mong doi:

```text
tests pass
JavaScript syntax check passes
```
