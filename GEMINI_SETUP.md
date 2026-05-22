# 🎨 PaintAI - Gemini 2.5 Flash Integration Setup

## Quick Start Guide

### Step 1: Get Your Gemini API Key
1. Go to [Google AI Studio](https://aistudio.google.com)
2. Click "Get API Key" (top right)
3. Create a new project or select existing one
4. Copy your API key

### Step 2: Configure .env File
Edit the `.env` file in the `clone_01` folder:

```
GEMINI_API_KEY=your-api-key-here
APP_URL=http://localhost:8000
APP_ENV=development
```

Replace `your-api-key-here` with your actual Gemini API key.

### Step 3: Install Dependencies
```bash
pip install python-dotenv
```

### Step 4: Start Server
```bash
python server.py
```

## How It Works

### Flow:
1. User uploads building image
2. Selects Interior or Exterior type
3. Chooses paint colors for each area
4. Clicks "Tạo ảnh phối màu" (Generate Color Visualization)
5. Frontend sends request to `/api/ai/generate-colors` with:
   - Base64 image
   - Project type (interior/exterior)
   - Selected paint colors for each area
6. Backend calls Gemini 2.5 Flash API
7. Gemini applies colors photorealistically to the image
8. Returns modified image as base64 PNG
9. Frontend displays the result

### API Endpoint

**POST** `/api/ai/generate-colors`

Request body:
```json
{
  "image": "data:image/jpeg;base64,...",
  "projectType": "interior",
  "paintAreas": {
    "wall-main": "#FF6B6B",
    "accent": "#4ECDC4",
    "ceiling": "#FFFFFF"
  }
}
```

Response:
```json
{
  "success": true,
  "data": {
    "image": "data:image/png;base64,..."
  }
}
```

## Features

✅ Real-time image visualization with AI  
✅ Supports custom paint area names  
✅ Photorealistic color application  
✅ Uses Gemini 2.5 Flash for fast processing  
✅ Preserves architectural details (windows, doors, textures)  

## Troubleshooting

### Error: "Không tìm thấy API Key Gemini"
- Make sure `.env` file exists in `clone_01` folder
- Make sure `GEMINI_API_KEY` is set correctly
- Restart the server

### Error: "Lỗi khi gọi Gemini API"
- Check your API key is valid and active
- Make sure you have internet connection
- Check Gemini API quota/limits in Google Cloud Console

### Image Not Generated
- Ensure image is in supported format (PNG, JPG, WEBP)
- File size should be less than 10MB
- Try uploading a clearer image

## Important Notes

⚠️ **API Key Security**: Never commit your `.env` file to version control  
⚠️ **API Costs**: Gemini 2.5 Flash API calls may incur costs - check Google pricing  
⚠️ **Rate Limits**: Gemini API has rate limiting - see Google documentation

## Support

For issues with Gemini API, see: https://ai.google.dev/docs
