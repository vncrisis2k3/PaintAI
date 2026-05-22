# GEMINI_API_KEY Environment Variable Setup

## ❌ Error Encountered
```
Environment Variable "GEMINI_API_KEY" references Secret "GEMINI_API_KEY", which does not exist.
```

This error occurs because Vercel couldn't find the `GEMINI_API_KEY` secret in your Vercel project.

---

## ✅ Solution: Add Environment Variable to Vercel

### Step-by-Step Instructions

#### 1. Go to Vercel Dashboard
- Open: https://vercel.com/dashboard
- Select your project: **AI-Colors**

#### 2. Navigate to Settings
- Click **Settings** (in top menu)
- Click **Environment Variables** (left sidebar)

#### 3. Add GEMINI_API_KEY
- Click **Add New** button
- Fill in the form:
  ```
  Name:                GEMINI_API_KEY
  Value:               AIzaSyBXZlSXCvfDpzDNPvVqoUdw6hS_WSGDFR0
  (Use your actual API key from .env)
  ```

#### 4. Select Environments
Check all three:
- ✅ **Production**
- ✅ **Preview**  
- ✅ **Development**

#### 5. Save
- Click **Save** button

#### 6. Redeploy
- Go to **Deployments** tab
- Find your failed deployment
- Click **Redeploy**
- Wait for build to complete

---

## 📝 Local Development

For local testing, `.env` file already has:
```bash
GEMINI_API_KEY=AIzaSyBXZlSXCvfDpzDNPvVqoUdw6hS_WSGDFR0
```

When you run `python server.py` locally:
```python
api_key = payload.api_key or os.environ.get("GEMINI_API_KEY")
```
↑ Will automatically use `.env` value

---

## 🔄 Fallback Options

### Option A: Frontend Passes API Key (Less Secure)
```javascript
// User enters API key in frontend
fetch('/api/ai-colorize', {
  method: 'POST',
  body: JSON.stringify({
    image: imageBase64,
    api_key: userProvidedApiKey  // ← From frontend input
  })
})
```

### Option B: vercel.json with Required Secret (Current - Needs Setup)
```json
{
  "env": {
    "GEMINI_API_KEY": "@GEMINI_API_KEY"  // ← Must exist on Vercel
  }
}
```

### Option C: vercel.json without Env (Current Fix - Optional)
```json
// No env section - server.py handles missing key gracefully
```

---

## 🔐 Security Best Practices

⚠️ **NEVER commit API key to Git!**
- `.env` file should be in `.gitignore` ✅ (already is)
- Only store API key on Vercel Dashboard
- Rotate API key periodically

---

## 🧪 Testing on Vercel

After adding environment variable and redeploying:

```bash
# Test API endpoint (replace with your Vercel URL)
curl -X POST https://ai-colors-xxxxx.vercel.app/api/ai/test-key \
  -H "Content-Type: application/json"

# Expected response:
# {
#   "success": true,
#   "message": "✅ Gemini API Key hợp lệ và hoạt động tốt!"
# }
```

---

## 📋 Checklist

- [ ] Go to Vercel Dashboard
- [ ] Select AI-Colors project
- [ ] Add GEMINI_API_KEY to Environment Variables
- [ ] Select all 3 environments (Production, Preview, Development)
- [ ] Save changes
- [ ] Redeploy from Deployments tab
- [ ] Test `/api/ai/test-key` endpoint
- [ ] Verify deployment successful

---

## ❓ Troubleshooting

### Still getting "Secret not found" error?
- Clear Vercel cache: **Deployments** → **Redeploy** with **Use cache** unchecked
- Wait 2-3 minutes for environment to apply

### API key doesn't work?
- Verify API key is correct: Check `.env` file
- Check quota: Go to https://ai.google.dev/account
- Try regenerating API key in Google Cloud Console

### Want to test locally first?
```bash
python server.py
curl http://localhost:8000/api/ai/test-key
```

---

## 📚 Reference

- Vercel Environment Variables Docs: https://vercel.com/docs/projects/environment-variables
- Google Gemini API: https://ai.google.dev/
