import os
import sqlite3
import urllib.request
import urllib.parse
import io
import json
import base64
from typing import Optional, Any, Dict, List
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator

# Load environment variables from .env file
from pathlib import Path
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

# Initialize FastAPI
app = FastAPI(
    title="Architectural Real-Time Color Visualizer API",
    description="Senior Backend API for real-time architectural layer-based compositions and paint catalogs",
    version="1.1.0"
)

# Enable CORS for frontend flexibility
# This is crucial when the frontend resides on a different domain or local server
# and performs raw pixel manipulation on HTML5 Canvas.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom exception handler for validation errors
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Handle Pydantic validation errors with user-friendly messages."""
    errors = []
    for error in exc.errors():
        field = '.'.join(str(x) for x in error['loc'][1:]) if len(error['loc']) > 1 else str(error['loc'][0])
        msg = error['msg']
        errors.append(f"{field}: {msg}")
    
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error_type": "validation_error",
            "message": "Request validation failed",
            "details": errors
        }
    )

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ==========================================================================
# IMAGE CORS BYPASS PROXY
# ==========================================================================
@app.get("/api/proxy-image")
def proxy_image(url: str):
    """
    Proxy external WebP/PNG images from external CDN to bypass strict CORS blocks in modern browsers.
    This prevents the 'Tainted Canvas' security exception when calling HTML5 Canvas getImageData()
    for high-speed real-time pixel-level color blending on the client.
    """
    try:
        # Request with a standard User-Agent header to avoid server denials
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            image_data = response.read()
            content_type = response.headers.get('Content-Type', 'image/webp')
            
            # Return identical image content with robust CORS headers
            return Response(
                content=image_data, 
                media_type=content_type,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=86400",
                    "Pragma": "public"
                }
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

# ==========================================================================
# 1. API DANH MỤC LOẠI CÔNG TRÌNH
# ==========================================================================
@app.get("/api/project-types")
def get_project_types():
    """Get list of architectural project types for filters."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, slug FROM project_types ORDER BY name ASC")
        rows = cursor.fetchall()
        conn.close()
        
        return {
            "success": True,
            "message": "Lấy danh mục loại công trình thành công",
            "data": [dict(row) for row in rows]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================================================
# OTHER FILTER APIS (BRANDS)
# ==========================================================================
@app.get("/api/brands")
def get_brands():
    """Get list of paint brands for filters."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM brands ORDER BY name ASC")
        rows = cursor.fetchall()
        conn.close()
        
        return {
            "success": True,
            "message": "Lấy danh sách hãng sơn thành công",
            "data": [dict(row) for row in rows]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================================================
# 2. API DANH SÁCH MẪU NHÀ (PHÂN TRANG)
# ==========================================================================
@app.get("/api/collections")
def get_collections(
    project_type_id: int = Query(None, description="Lọc theo ID loại công trình"),
    number_of_floors: int = Query(None, alias="number_of_floors", description="Lọc theo số tầng"),
    floors: int = Query(None, alias="floors", description="Lọc theo số tầng (Alias cho frontend)"),
    number_of_facades: int = Query(None, alias="number_of_facades", description="Lọc theo số mặt tiền"),
    facades: int = Query(None, alias="facades", description="Lọc theo số mặt tiền (Alias cho frontend)"),
    q: str = Query(None, alias="q", description="Tìm kiếm theo mã hoặc tên mẫu nhà"),
    search: str = Query(None, alias="search", description="Tìm kiếm (Alias cho frontend)"),
    page: int = Query(1, ge=1, description="Trang hiện tại"),
    limit: int = Query(12, ge=1, le=100, description="Số lượng mẫu nhà mỗi trang")
):
    """
    Get paginated list of architectural collections (house models).
    Excludes the 'layers' array to optimize data transfer size over the wire.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Fallback values to support both clean required parameters and frontend queries
        floors_filter = number_of_floors if number_of_floors is not None else floors
        facades_filter = number_of_facades if number_of_facades is not None else facades
        search_filter = q if q is not None else search
        
        # Build dynamic query
        query = "SELECT c.*, p.name as project_type_name FROM collections c LEFT JOIN project_types p ON c.project_type_id = p.id WHERE 1=1"
        params = []
        
        if project_type_id is not None:
            query += " AND c.project_type_id = ?"
            params.append(project_type_id)
        
        if floors_filter is not None:
            query += " AND c.number_of_floors = ?"
            params.append(floors_filter)
            
        if facades_filter is not None:
            query += " AND c.number_of_facades = ?"
            params.append(facades_filter)
            
        if search_filter:
            query += " AND (c.name LIKE ? OR c.description LIKE ?)"
            params.append(f"%{search_filter}%")
            params.append(f"%{search_filter}%")
            
        # Count total records for pagination metadata
        count_query = "SELECT COUNT(*) FROM (" + query + ")"
        cursor.execute(count_query, params)
        total_items = cursor.fetchone()[0]
        
        # Paginate results
        offset = (page - 1) * limit
        query += " ORDER BY c.id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Attach proxied thumbnail for each collection to ensure CORS compliance in preview grids
        collections_list = []
        for row in rows:
            col_dict = dict(row)
            col_id = col_dict["id"]
            
            # Fetch first layer image as a thumbnail preview
            cursor.execute(
                "SELECT image_url FROM layers WHERE collection_id = ? ORDER BY z_index ASC LIMIT 1", 
                (col_id,)
            )
            thumb_row = cursor.fetchone()
            if thumb_row and thumb_row["image_url"]:
                # Wrap URL with our local CORS-proof proxy
                col_dict["thumbnail_url"] = f"/api/proxy-image?url={urllib.parse.quote_plus(thumb_row['image_url'])}"
            else:
                col_dict["thumbnail_url"] = None
                
            collections_list.append(col_dict)
            
        conn.close()
        
        last_page = max(1, (total_items + limit - 1) // limit)
        
        return {
            "success": True,
            "message": "Lấy danh sách mẫu nhà thành công",
            "data": collections_list,
            "meta": {
                "current_page": page,
                "per_page": limit,
                "total": total_items,
                "last_page": last_page,
                "has_more_pages": page < last_page
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================================================
# 3. API CHI TIẾT LAYER CỦA MỘT MẪU NHÀ
# ==========================================================================
@app.get("/api/collections/{id}/layers")
def get_collection_layers(id: str):
    """
    Get all transparent overlay layers of a house model.
    STRICT REQUIREMENT: Returned array is ordered by zIndex ascending (bottom layers to top details).
    Conforms to the exact properties: id, name, layer_type, layer_type_display, zIndex, opacity, visible, imageFile.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify collection exists
        cursor.execute("SELECT id, name, description FROM collections WHERE id = ?", (id,))
        collection = cursor.fetchone()
        if not collection:
            conn.close()
            raise HTTPException(status_code=404, detail="Không tìm thấy mẫu nhà phù hợp")
            
        # Fetch layers and sort by z_index ascending (crucial for visual composition order)
        cursor.execute("""
            SELECT id, name, image_url, image_path, image_mime_type, layer_type, layer_type_display, z_index, opacity, visible
            FROM layers 
            WHERE collection_id = ? 
            ORDER BY z_index ASC
        """, (id,))
        rows = cursor.fetchall()
        
        # Map DB fields to the exact camelCase structure and imageFile sub-object
        layers_data = []
        for row in rows:
            layer_dict = dict(row)
            
            original_url = layer_dict.get("image_url")
            image_path = layer_dict.get("image_path") or ""
            image_mime_type = layer_dict.get("image_mime_type") or "image/webp"
            z_index = layer_dict.get("z_index")
            db_visible = layer_dict.get("visible")
            
            # Construct CORS bypass proxy URL for canvas compatibility
            proxied_url = f"/api/proxy-image?url={urllib.parse.quote_plus(original_url)}" if original_url else None
            
            # Inject standardized API fields & keep snake_case fallbacks
            layer_dict["image_url"] = proxied_url
            layer_dict["z_index"] = z_index
            layer_dict["zIndex"] = z_index
            layer_dict["visible"] = bool(db_visible)
            layer_dict["imageFile"] = {
                "url": proxied_url,
                "path": image_path,
                "mimeType": image_mime_type
            }
            
            layers_data.append(layer_dict)
            
        conn.close()
        
        return {
            "success": True,
            "message": f"Lấy danh sách layer của mẫu nhà {collection['name']} thành công",
            "data": layers_data,
            # Extra metadata to support frontend single collection details retrieval
            "collection": dict(collection)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================================================
# 4. API DANH SÁCH BẢNG MÀU SƠN (PHÂN TRANG)
# ==========================================================================
@app.get("/api/colors")
def get_colors(
    brand_id: int = Query(None, description="Lọc theo ID hãng sơn"),
    category: str = Query(None, description="Lọc theo phân khúc/loại sơn (ví dụ: APEX, Odourless...)"),
    q: str = Query(None, alias="q", description="Tìm kiếm theo mã màu (paint_code) hoặc tên màu"),
    search: str = Query(None, alias="search", description="Tìm kiếm (Alias cho frontend)"),
    page: int = Query(1, ge=1, description="Trang hiện tại"),
    limit: int = Query(24, ge=1, le=100, description="Số lượng màu mỗi trang (mặc định 24)")
):
    """
    Get paginated paint color catalog.
    Enables instant filtering and search with indices-boosted queries.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        search_filter = q if q is not None else search
        
        query = "SELECT c.*, b.name as brand_name FROM paint_colors c LEFT JOIN brands b ON c.brand_id = b.id WHERE 1=1"
        params = []
        
        if brand_id is not None:
            query += " AND c.brand_id = ?"
            params.append(brand_id)
            
        if category:
            query += " AND c.category = ?"
            params.append(category)
            
        if search_filter:
            query += " AND (c.name LIKE ? OR c.paint_code LIKE ? OR c.hex_code LIKE ?)"
            params.append(f"%{search_filter}%")
            params.append(f"%{search_filter}%")
            params.append(f"%{search_filter}%")
            
        # Count total records for pagination metadata
        count_query = "SELECT COUNT(*) FROM (" + query + ")"
        cursor.execute(count_query, params)
        total_items = cursor.fetchone()[0]
        
        # Paginate results
        offset = (page - 1) * limit
        query += " ORDER BY c.id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        last_page = max(1, (total_items + limit - 1) // limit)
        
        return {
            "success": True,
            "message": "Lấy danh sách bảng màu sơn thành công",
            "data": [dict(row) for row in rows],
            "meta": {
                "current_page": page,
                "per_page": limit,
                "total": total_items,
                "last_page": last_page,
                "has_more_pages": page < last_page
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================================================
# SAVED DESIGNS (PORTABILITY & PERSISTENCE)
# ==========================================================================
class SavedDesignCreate(BaseModel):
    name: str
    collection_id: str
    colors: dict

def init_saved_designs_table():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_designs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                collection_id TEXT NOT NULL,
                colors TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (collection_id) REFERENCES collections(id)
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error creating saved_designs table: {e}")

def init_favorite_colors_table():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS favorite_colors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                color_id INTEGER NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (color_id) REFERENCES paint_colors(id)
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error creating favorite_colors table: {e}")

# Run database table initialization
init_saved_designs_table()
init_favorite_colors_table()

@app.post("/api/saved-designs")
def save_design(design: SavedDesignCreate):
    """Save a custom colored configuration mapping to SQLite."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify collection exists
        cursor.execute("SELECT id FROM collections WHERE id = ?", (design.collection_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Không tìm thấy mẫu nhà phù hợp")
            
        colors_str = json.dumps(design.colors)
        cursor.execute(
            "INSERT INTO saved_designs (name, collection_id, colors) VALUES (?, ?, ?)",
            (design.name, design.collection_id, colors_str)
        )
        design_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": f"Lưu thiết kế '{design.name}' thành công",
            "data": {
                "id": design_id,
                "name": design.name,
                "collection_id": design.collection_id
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/saved-designs")
def get_saved_designs():
    """Retrieve all previously saved architectural color designs."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.id, s.name, s.collection_id, s.colors, s.created_at, c.name as collection_name
            FROM saved_designs s
            LEFT JOIN collections c ON s.collection_id = c.id
            ORDER BY s.created_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        designs = []
        for row in rows:
            row_dict = dict(row)
            row_dict["colors"] = json.loads(row_dict["colors"]) if row_dict["colors"] else {}
            designs.append(row_dict)
            
        return {
            "success": True,
            "message": "Lấy danh sách thiết kế đã lưu thành công",
            "data": designs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/saved-designs/{id}")
def delete_saved_design(id: int):
    """Delete a saved design configuration by its SQLite row ID."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify existence
        cursor.execute("SELECT id FROM saved_designs WHERE id = ?", (id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Không tìm thấy phương án thiết kế để xóa")
            
        cursor.execute("DELETE FROM saved_designs WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": "Xóa thiết kế thành công",
            "data": {"id": id}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================================================
# FAVORITE COLORS APIS
# ==========================================================================
@app.post("/api/favorites/colors/{color_id}")
def add_favorite_color(color_id: int):
    """Add a specific paint color to favorites catalog."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify color exists in catalog
        cursor.execute("SELECT id, name FROM paint_colors WHERE id = ?", (color_id,))
        color = cursor.fetchone()
        if not color:
            conn.close()
            raise HTTPException(status_code=404, detail="Mã màu không tồn tại trong danh mục")
            
        try:
            cursor.execute("INSERT INTO favorite_colors (color_id) VALUES (?)", (color_id,))
            conn.commit()
        except sqlite3.IntegrityError:
            # Already favorited, ignore duplicate key error
            pass
            
        conn.close()
        return {
            "success": True,
            "message": f"Đã thêm màu {color['name']} vào danh sách yêu thích thành công",
            "data": {"color_id": color_id}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/favorites/colors/{color_id}")
def remove_favorite_color(color_id: int):
    """Remove a color from favorites list."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM favorite_colors WHERE color_id = ?", (color_id,))
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": "Đã xóa màu khỏi danh sách yêu thích thành công",
            "data": {"color_id": color_id}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/favorites/colors")
def get_favorite_colors():
    """Retrieve full detail catalog of favorited paint colors."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pc.*, b.name as brand_name
            FROM favorite_colors fc
            JOIN paint_colors pc ON fc.color_id = pc.id
            LEFT JOIN brands b ON pc.brand_id = b.id
            ORDER BY fc.created_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        return {
            "success": True,
            "message": "Lấy danh sách màu yêu thích thành công",
            "data": [dict(row) for row in rows]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================================================
# GEMINI API INTEGRATION ENDPOINT
# ==========================================================================
class AIColorizeRequest(BaseModel):
    image: str
    api_key: str = None

@app.post("/api/ai-colorize")
def ai_colorize(payload: AIColorizeRequest):
    """
    Call Google Gemini 2.5 Flash API to analyze building structure and recommend paint colors.
    Implements proper error handling for rate limits and quota exceeded.
    
    Flow:
    1. Check Gemini API quota status
    2. If limit reached → return error immediately (NO image processing)
    3. If OK → call Gemini for analysis
    4. Return results (PIL/OpenCV processing happens in separate endpoint)
    """
    api_key = payload.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {
            "success": False,
            "error_type": "apikey_missing",
            "message": "Không tìm thấy API Key Gemini. Vui lòng cấu hình biến môi trường GEMINI_API_KEY hoặc nhập khóa trong phần cài đặt."
        }

    # Validate image format
    try:
        if "," in payload.image:
            header, base64_data = payload.image.split(",", 1)
            mime_type = header.split(";")[0].split(":")[1]
        else:
            base64_data = payload.image
            mime_type = "image/jpeg"
    except Exception as e:
        raise HTTPException(status_code=400, detail="Mã hóa ảnh Base64 không hợp lệ.")

    system_prompt = """
You are a computer vision and architectural analysis engine integrated into a paint-coloring application.

Your task is to analyze the provided building image and return only a single valid JSON object that matches this schema exactly:
{
  "space_type": "exterior" | "interior",
  "detected_areas": [
    {
      "id": "wall-main" | "trim" | "column" | "detail" | "accent" | "ceiling",
      "name_vi": "string",
      "box_2d": [ymin, xmin, ymax, xmax]
    }
  ],
  "suggested_palettes": [
    {
      "style_name": "string",
      "colors": {
        "<area-id>": "#RRGGBB"
      }
    }
  ]
}

Rules:
- Detect whether the image is exterior or interior and set space_type accordingly.
- Use only the allowed IDs for the detected space.
- For each detected area, provide a normalized bounding box on a 0-1000 scale in [ymin, xmin, ymax, xmax] order.
- Include at most 2 suggested palettes.
- Use valid HEX colors only.
- If an area is not visible, omit it.
- Return JSON only. Do not include markdown fences, comments, explanations, or extra text.
"""

    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={api_key}"

    request_data = {
        "contents": [
            {
                "parts": [
                    {"text": "Analyze the building image and return the requested JSON schema with detected areas, normalized bounding boxes, and suggested palettes."},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": base64_data
                        }
                    }
                ]
            }
        ],
        "systemInstruction": {
            "parts": [
                {"text": system_prompt}
            ]
        },
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    try:
        req_body = json.dumps(request_data).encode("utf-8")
        req = urllib.request.Request(
            gemini_url,
            data=req_body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)

            candidates = res_json.get("candidates", [])
            if not candidates:
                return {"success": False, "message": "Không nhận được câu trả lời từ Gemini API."}

            text_content = candidates[0]["content"]["parts"][0]["text"]
            ai_data = json.loads(text_content)

            return {
                "success": True,
                "data": ai_data
            }
    
    except urllib.error.HTTPError as e:
        """Handle specific HTTP errors from Gemini API"""
        error_body = e.read().decode("utf-8") if e.fp else ""
        error_status = e.code
        
        try:
            error_json = json.loads(error_body) if error_body else {}
            error_msg = error_json.get("error", {}).get("message", "Unknown error")
        except:
            error_msg = error_body
        
        # Handle Rate Limit (429)
        if error_status == 429:
            return {
                "success": False,
                "error_type": "rate_limit",
                "status_code": 429,
                "message": f"❌ Gemini API đã đạt giới hạn yêu cầu. Vui lòng chờ một vài phút rồi thử lại.",
                "detail": error_msg
            }
        
        # Handle Quota Exceeded (400 - sometimes returned as quota error)
        elif error_status == 400 and ("quota" in error_msg.lower() or "exceeded" in error_msg.lower()):
            return {
                "success": False,
                "error_type": "quota_exceeded",
                "status_code": 400,
                "message": f"❌ Hạn mức sử dụng Gemini API hôm nay đã được vượt quá. Vui lòng thử lại vào ngày mai hoặc nâng cấp gói API.",
                "detail": error_msg
            }
        
        # Handle Invalid API Key
        elif error_status == 401 or error_status == 403:
            return {
                "success": False,
                "error_type": "invalid_api_key",
                "status_code": error_status,
                "message": f"❌ API Key Gemini không hợp lệ hoặc đã hết hạn.",
                "detail": error_msg
            }
        
        # Generic HTTP error
        else:
            return {
                "success": False,
                "error_type": "gemini_api_error",
                "status_code": error_status,
                "message": f"❌ Lỗi từ Gemini API (HTTP {error_status})",
                "detail": error_msg
            }
    
    except Exception as e:
        """Handle other exceptions"""
        return {
            "success": False,
            "error_type": "unknown_error",
            "message": f"❌ Lỗi khi gọi Gemini API: {str(e)}"
        }

# ==========================================================================
# AI PAINT AREA GENERATION - GEMINI 2.5 FLASH
# ==========================================================================
class AIGenerateColorsRequest(BaseModel):
    image: str = Field(..., description="Base64 image data (required)")
    projectType: str = Field(..., description="'interior' or 'exterior' (required)")
    paintAreas: dict = Field(..., description="Color mapping: { 'area-id': 'hex-color' } (required)")
    detected_areas: Optional[List[Dict[str, Any]]] = Field(None, description="Optional AI-detected bounding boxes")
    api_key: Optional[str] = Field(None, description="Optional Gemini API key")
    
    @field_validator('image')
    @classmethod
    def validate_image(cls, v):
        if not v or len(v) == 0:
            raise ValueError("Image data cannot be empty")
        return v
    
    @field_validator('projectType')
    @classmethod
    def validate_project_type(cls, v):
        if v not in ['interior', 'exterior']:
            raise ValueError("projectType must be 'interior' or 'exterior'")
        return v
    
    @field_validator('paintAreas')
    @classmethod
    def validate_paint_areas(cls, v):
        if not v or len(v) == 0:
            raise ValueError("paintAreas cannot be empty - must have at least one color selection")
        return v

class TestGeminiKeyRequest(BaseModel):
    api_key: Optional[str] = Field(None, description="Optional Gemini API key")

@app.api_route("/api/ai/test-key", methods=["GET", "POST"])
def test_gemini_key(api_key: Optional[str] = Query(None), payload: Optional[TestGeminiKeyRequest] = None):
    """Test if Gemini API key is valid and accessible."""
    api_key = api_key or (payload.api_key if payload else None) or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {
            "success": False,
            "message": "Không tìm thấy API Key Gemini. Vui lòng cấu hình GEMINI_API_KEY hoặc nhập khóa trong phần cài đặt."
        }
    
    try:
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={api_key}"
        
        test_request = {
            "contents": [{
                "parts": [{"text": "Say OK"}]
            }],
            "generationConfig": {
                "responseMimeType": "text/plain"
            }
        }
        
        req_body = json.dumps(test_request).encode("utf-8")
        req = urllib.request.Request(
            gemini_url,
            data=req_body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            
            if res_json.get("candidates"):
                return {
                    "success": True,
                    "message": "✅ Gemini API Key hợp lệ và hoạt động tốt!"
                }
            else:
                return {
                    "success": False,
                    "message": "API Key hợp lệ nhưng không nhận được phản hồi"
                }
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8")
        try:
            error_json = json.loads(error_msg)
            error_detail = error_json.get("error", {}).get("message", str(e))
        except:
            error_detail = error_msg
        
        return {
            "success": False,
            "message": f"❌ API Key không hợp lệ hoặc đã hết hạn: {error_detail}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"❌ Lỗi kết nối: {str(e)}"
        }

@app.post("/api/ai/generate-colors")
def ai_generate_colors(payload: AIGenerateColorsRequest):
    """
    Apply paint colors to image using local image processing (PIL).
    
    ⚠️ IMPORTANT FLOW:
    This endpoint should ONLY be called AFTER successful Gemini analysis.
    Call sequence:
    1. Call POST /api/ai-colorize with image → get Gemini analysis
    2. If error_type in response → STOP (rate limit, quota exceeded, etc.)
    3. If success=true → create paintAreas dict from Gemini response
    4. Call POST /api/ai/generate-colors with paintAreas → get styled image
    
    This ensures:
    - No API processing waste when Gemini is limited
    - Clean error reporting when limits are reached
    - Proper separation: AI analysis → Image processing
    
    NOTE: This uses PIL color overlay for quick implementation.
    For production photorealistic results, use:
    - Stable Diffusion for image inpainting
    - DALL-E 3 for professional quality
    - Custom ControlNet for precise area targeting
    """
    
    try:
        # Import the image painter module
        from image_painter import apply_paint_color_ai, apply_paint_color_advanced
        
        # Prefer AI-detected bounding boxes when available, otherwise fallback to geometric masking
        if payload.detected_areas:
            result_image = apply_paint_color_ai(
                payload.image,
                payload.paintAreas,
                payload.detected_areas,
                payload.projectType
            )
        else:
            result_image = apply_paint_color_advanced(
                payload.image,
                payload.paintAreas,
                payload.projectType
            )
        
        return {
            "success": True,
            "data": {
                "image": result_image
            },
            "message": "✨ Ảnh phối màu được tạo thành công (sử dụng PIL processing)",
            "note": "Để có kết quả photorealistic hơn, hãy sử dụng Stable Diffusion hoặc DALL-E 3"
        }
        
    except ImportError:
        return {
            "success": False,
            "message": "❌ Module image_painter chưa được cài đặt. Vui lòng tạo file image_painter.py"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"❌ Lỗi khi xử lý ảnh: {str(e)}"
        }

# ==========================================================================
# STATIC FILE SERVING FOR SPA COMPATIBILITY
# ==========================================================================
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)

# Mount static folder
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Catch-all routes to serve index.html for Single Page Applications
@app.get("/")
def read_root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"success": False, "message": "Static assets index.html is missing. Place it inside the 'static' directory."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
