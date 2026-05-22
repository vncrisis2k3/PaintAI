# PaintAI - Hệ Thống Phối Màu Kiến Trúc Thông Minh

Ứng dụng web AI giúp tự động phân tách và phối màu sơn cho các công trình kiến trúc bằng công nghệ Google Gemini 2.5 Flash.

## 🎯 Tính Năng Chính

✨ **Phối Màu AI Thông Minh**
- Upload ảnh công trình (nội thất/ngoại thất)
- AI tự động phân tách các vùng cần sơn
- Gợi ý màu sơn phù hợp với phong cách kiến trúc

🎨 **Thư Viện Mẫu Công Trình**
- Xem trước 100+ mẫu nhà mẫu
- Lọc theo số tầng, số mặt tiền, loại công trình
- Tìm kiếm nhanh theo mã hoặc tên mẫu

🌈 **Danh Sách Màu Sơn Toàn Diện**
- 500+ màu sơn chuẩn từ các nhãn hiệu nổi tiếng
- Phân loại theo thể loại (Hiện đại, Tối, Ấm áp, v.v.)
- So sánh màu trực tiếp trên canvas

📊 **Lưu & Quản Lý Thiết Kế**
- Lưu các phương án phối màu yêu thích
- Xem lịch sử thiết kế
- Xuất PDF báo cáo phối màu

## 🚀 Quick Start

### 1. Cài đặt Dependencies

```bash
pip install -r requirements.txt
```

### 2. Tạo File .env

Tạo file `.env` trong thư mục gốc với nội dung:

```
GEMINI_API_KEY=your_api_key_here
```

Lấy API key từ: https://ai.google.dev/

### 3. Khởi Động Server

```bash
python server.py
```

Server sẽ chạy trên: `http://127.0.0.1:8000`

### 4. Mở Trong Browser

```
http://localhost:8000
```

## 📁 Cấu Trúc Dự Án

```
clone_01/
├── server.py                      # FastAPI backend server
├── get_colors.py                  # Scraper để lấy dữ liệu màu sơn
├── seed_db.py                     # Script khởi tạo database
├── database.db                    # SQLite database
├── .env                           # Environment variables (API Key)
├── danh_sach_mau_son_chuan.json  # Dữ liệu màu sơn chuẩn
├── data_thuvienmau.txt           # Dữ liệu thư viện mẫu
├── mauson.txt                     # Dữ liệu danh sách màu
│
└── static/
    ├── index.html                 # Giao diện HTML chính
    ├── app.js                     # Logic frontend chính (Vanilla JS)
    ├── style.css                  # Styling
    ├── ai-editor.js               # Không dùng (JSX cũ)
    ├── RealtimePaintVisualizer.jsx # Component React
    └── danh_sach_mau_son_chuan.json # Bản sao dữ liệu màu
```

## 🔌 API Endpoints

### Lấy Danh Sách

```http
GET /api/project-types           # Loại công trình
GET /api/brands                  # Nhãn hiệu sơn
GET /api/collections             # Thư viện mẫu nhà (phân trang)
GET /api/colors                  # Danh sách màu (phân trang)
```

### AI Features

```http
GET  /api/ai/test-key            # Kiểm tra Gemini API Key
POST /api/ai/generate-colors     # Tạo ảnh phối màu
```

**Request Body:**
```json
{
  "image": "data:image/jpeg;base64,...",
  "projectType": "interior|exterior",
  "paintAreas": {
    "wall-main": "#FFFFFF",
    "accent": "#FF5733",
    "ceiling": "#2E8B57"
  },
  "api_key": null
}
```

### Proxy

```http
GET /api/proxy-image?url=...     # Bypass CORS cho ảnh
```

## 🛠️ Công Nghệ

| Thành Phần | Công Nghệ |
|-----------|----------|
| **Backend** | FastAPI (Python) |
| **Frontend** | Vanilla JavaScript + HTML5 Canvas |
| **Database** | SQLite3 |
| **Styling** | CSS3 + Tailwind CSS |
| **AI** | Google Gemini 2.5 Flash API |
| **Server** | Uvicorn |

## 🔧 Cấu Hình

### Database

Database sẽ tự động tạo khi server khởi động. Để reset:

```bash
python seed_db.py
```

### CORS

CORS đã được bật cho tất cả origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 🐛 Troubleshooting

### Lỗi: 422 Unprocessable Entity

**Nguyên nhân:** Dữ liệu request không hợp lệ

**Giải pháp:**
- Đảm bảo upload ảnh trước khi tạo phối màu
- Chọn loại công trình (Nội thất/Ngoại thất)
- Chọn ít nhất một màu cho vùng

**Debug:**
```javascript
// Mở DevTools Console và kiểm tra:
console.log(state.aiColorTool.selectedColors);
console.log(state.aiColorTool.projectType);
console.log(state.aiColorTool.uploadedImage?.length);
```

### Lỗi: Không tìm thấy API Key

**Giải pháp:**
1. Tạo file `.env` trong thư mục gốc
2. Thêm: `GEMINI_API_KEY=your_key_here`
3. Restart server

### Ảnh không hiển thị

**Giải pháp:** Dùng endpoint proxy:
```
/api/proxy-image?url=https://example.com/image.jpg
```

## 📝 Hướng Dẫn Sử Dụng

### Bước 1: Upload Ảnh
- Click vào "Phối Màu AI"
- Kéo thả hoặc click để chọn ảnh công trình
- Định dạng: PNG, JPG, WEBP (tối đa 10MB)

### Bước 2: Chọn Loại
- Chọn "Nội thất" hoặc "Ngoại thất"
- AI sẽ phân tách các vùng cần sơn tự động

### Bước 3: Gán Màu
- Chọn vùng (Tường chính, Accent, Trần, v.v.)
- Chọn màu từ palette
- Có thể thêm vùng tùy chỉnh bằng nút "+ Tự nhập"

### Bước 4: Tạo Ảnh Phối Màu
- Click "Tạo ảnh phối màu"
- Đợi AI xử lý (khoảng 30 giây)
- Kéo thanh để so sánh ảnh gốc và kết quả

### Bước 5: Lưu Thiết Kế
- Click "Lưu thiết kế"
- Nhập tên cho phương án của bạn
- Xem lại trong tab "Thiết kế của tôi"

## 📊 Dữ Liệu

### Danh Mục Loại Công Trình
- Biệt thự
- Nhà phố
- Chung cư.
- Nhà vườn
- v.v.

### Nhãn Hiệu Sơn
- Việt Paint
- Jotun
- Tikkurila
- Dulux
- v.v.

### Số Tầng
- 1 tầng
- 2 tầng
- 3 tầng
- 4+ tầng

## 🔐 Bảo Mật

- API Key lưu trữ an toàn trong environment variables
- Không lưu trữ ảnh người dùng trên server (chỉ xử lý tạm thời)
- CORS được cấu hình cho phép từ mọi nơi (có thể điều chỉnh khi production)

## 📈 Performance

- Canvas rendering tối ưu với CSS blend modes
- Image proxy cache 24 giờ
- Database queries có index tối ưu
- Frontend load nhanh với vanilla JS (không framework overhead)

## 🚀 Deployment

### Production Checklist

- [ ] Tắt debug mode
- [ ] Cấu hình CORS cụ thể thay vì `["*"]`
- [ ] Dùng production ASGI server (gunicorn, etc.)
- [ ] Cấu hình HTTPS/SSL
- [ ] Thiết lập database backup
- [ ] Giới hạn request rate
- [ ] Thêm authentication nếu cần

### Deploy Lên Heroku

```bash
git push heroku main
```

### Deploy Lên Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 📞 Support

- Report bugs: Tạo issue trên GitHub
- Email: support@paintai.local

## 📄 License

MIT License - xem file LICENSE để chi tiết

## 👨‍💻 Contributors

- PaintAI Team

---

**Phiên bản:** 2.4.0  
**Cập nhật lần cuối:** May 22, 2026
