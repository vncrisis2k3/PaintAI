# PaintAI API Flow Documentation

## 🎯 Proper Request Flow (Updated)

### ✅ **AFTER Improvements**: Correct Error Handling

```
┌─────────────────────────────────────────────────────────────┐
│ Frontend: Upload Image                                      │
└────────────────┬────────────────────────────────────────────┘
                 │ Step 1: Analyze with Gemini
                 ▼
        ╔════════════════════╗
        ║  POST /api/ai-    ║
        ║  colorize         ║
        ║  (Gemini Analysis)║
        ╚════════════════════╝
                 │
         ┌───────┴───────┐
         │               │
    ✅ Success      ❌ Error?
         │               │
         │        ┌──────┴──────┐
         │        │             │
         │    Rate Limit   Quota Exceeded
         │    (429)        (400)
         │        │             │
         │    ❌ STOP      ❌ STOP
         │    No PIL       No PIL
         │        │             │
         │        └──────┬──────┘
         │               │
         │        Show Error Message
         │        "API limit reached"
         │        (Don't process image)
         │
         │ Get AI Recommendations:
         │ - primaryPaint.hex
         │ - accentPaint.hex
         │
         │ Step 2: Process Image (ONLY if success=true)
         ▼
    ╔════════════════════╗
    ║  POST /api/ai/    ║
    ║  generate-colors  ║
    ║  (PIL Processing) ║
    ╚════════════════════╝
         │
         ▼
    ✅ Painted Image
```

---

## 📋 API Endpoints

### 1️⃣ **Gemini Analysis** (MUST call first)

```
POST /api/ai-colorize
Content-Type: application/json

Request:
{
  "image": "data:image/png;base64,..." or "base64string",
  "api_key": "your-api-key" (optional, uses .env if not provided)
}

Response (Success - 200 OK):
{
  "success": true,
  "data": {
    "architecturalStyle": "Modern Minimalist",
    "primaryPaint": {
      "name": "Pure White",
      "brand": "Nippon Paint",
      "hex": "#FFFFFF",
      "paintCode": "NP001"
    },
    "accentPaint": {
      "name": "Charcoal Grey",
      "brand": "Nippon Paint", 
      "hex": "#333333",
      "paintCode": "NP002"
    },
    "designReasoning": "..."
  }
}

Response (Rate Limit - 429):
{
  "success": false,
  "error_type": "rate_limit",
  "status_code": 429,
  "message": "❌ Gemini API đã đạt giới hạn yêu cầu. Vui lòng chờ một vài phút rồi thử lại."
}

Response (Quota Exceeded - 400):
{
  "success": false,
  "error_type": "quota_exceeded",
  "status_code": 400,
  "message": "❌ Hạn mức sử dụng Gemini API hôm nay đã được vượt quá. Vui lòng thử lại vào ngày mai."
}

Response (Invalid API Key - 401/403):
{
  "success": false,
  "error_type": "invalid_api_key",
  "status_code": 401,
  "message": "❌ API Key Gemini không hợp lệ hoặc đã hết hạn."
}
```

**⚠️ IMPORTANT**: 
- If `success` is `false`, **DO NOT** proceed to Step 2
- Check `error_type` to determine what went wrong
- Show user the `message` field
- Wait before retrying if rate_limit or quota_exceeded

---

### 2️⃣ **Image Processing** (ONLY after Step 1 success)

```
POST /api/ai/generate-colors
Content-Type: application/json

Request:
{
  "image": "data:image/png;base64,...",
  "projectType": "exterior" or "interior",
  "paintAreas": {
    "wall": "#FFFFFF",           // from primaryPaint.hex
    "accent": "#333333"           // from accentPaint.hex
  }
}

Response (Success):
{
  "success": true,
  "data": {
    "image": "data:image/png;base64,..." // Painted image
  },
  "message": "✨ Ảnh phối màu được tạo thành công (sử dụng PIL processing)"
}

Response (Error):
{
  "success": false,
  "message": "❌ Lỗi khi xử lý ảnh: ..."
}
```

---

## 🔍 Error Handling Rules

### Rule 1: Check Gemini Success First ✅
```javascript
// ✅ CORRECT
const result1 = await colorizeWithGemini(image);
if (!result1.success) {
  showError(result1.message); // "Rate limit reached"
  return; // ⛔ DON'T process image
}

// ✅ Then process image only if success
const result2 = await generateColors(image, result1.data);
displayPaintedImage(result2.data.image);
```

### Rule 2: Handle Rate Limit Specifically ✅
```javascript
// ✅ CORRECT
if (result.error_type === "rate_limit") {
  showError("Please wait a few minutes before trying again");
  setTimeout(retry, 300000); // Retry after 5 minutes
} else if (result.error_type === "quota_exceeded") {
  showError("Daily quota exceeded. Try tomorrow");
}
```

---

## 📊 Current Implementation Status

| Component | Status | Details |
|-----------|--------|---------|
| **Gemini API Integration** | ✅ | Calls gemini-2.5-flash for analysis |
| **Rate Limit Handling (429)** | ✅ | Separate error response with error_type |
| **Quota Exceeded Handling (400)** | ✅ | Separate error response with error_type |
| **Invalid API Key (401/403)** | ✅ | Separate error response with error_type |
| **Flow Enforcement** | ✅ | API expects both calls; frontend should check success |
| **PIL Image Processing** | ✅ | Applies colors using PIL overlay |
| **Separation of Concerns** | ✅ | AI analysis ≠ Image processing |

---

## 🚀 Example Client Code (JavaScript/React)

```javascript
// Correct flow implementation
async function paintBuilding(imageFile) {
  try {
    // Step 1: Get Gemini analysis
    console.log("🤖 Analyzing with Gemini...");
    const analysisResponse = await fetch("/api/ai-colorize", {
      method: "POST",
      body: JSON.stringify({
        image: await imageToBase64(imageFile)
      })
    });
    
    const analysis = await analysisResponse.json();
    
    // Check if analysis succeeded
    if (!analysis.success) {
      // ⛔ STOP HERE - don't process image
      if (analysis.error_type === "rate_limit") {
        showError("API rate limit reached. Please wait a few minutes.");
        // Could implement exponential backoff retry here
      } else if (analysis.error_type === "quota_exceeded") {
        showError("Daily quota exceeded. Try again tomorrow.");
      }
      return;
    }
    
    // Extract colors from Gemini response
    const paintAreas = {
      wall: analysis.data.primaryPaint.hex,
      accent: analysis.data.accentPaint.hex
    };
    
    // Step 2: Apply colors to image (ONLY after success)
    console.log("🎨 Applying colors with PIL...");
    const paintResponse = await fetch("/api/ai/generate-colors", {
      method: "POST",
      body: JSON.stringify({
        image: await imageToBase64(imageFile),
        projectType: "exterior",
        paintAreas: paintAreas
      })
    });
    
    const result = await paintResponse.json();
    
    if (result.success) {
      displayPaintedImage(result.data.image);
    } else {
      showError(result.message);
    }
    
  } catch (error) {
    showError("An unexpected error occurred: " + error.message);
  }
}
```

---

## 💡 Summary

**Your hệ thống now works correctly:**

✅ **Gemini processes FIRST** - analyzes building and recommends colors
- If error → reports it clearly (rate limit, quota, etc.)
- **STOPS immediately** - does NOT proceed to PIL

✅ **PIL processes SECOND** - only after Gemini success
- Takes color recommendations from Gemini
- Applies them to image

✅ **No wasted processing** - if API is limited, PIL never runs

✅ **Clear error messages** - client knows exactly what went wrong
