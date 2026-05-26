import os
import sqlite3
import urllib.request
import urllib.parse
import urllib.error
import io
import json
import base64
import uuid
import socket
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

import tempfile


def _choose_db_path() -> str:
    """Pick a writable SQLite path: prefer env var, then repo file, then system temp, then in-memory."""
    env_path = os.environ.get("DATABASE_PATH")
    if env_path:
        return env_path
    repo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")
    try:
        # Try creating the file to verify write access
        conn = sqlite3.connect(repo_path)
        conn.close()
        return repo_path
    except Exception:
        try:
            tmp = os.path.join(tempfile.gettempdir(), "database.db")
            conn = sqlite3.connect(tmp)
            conn.close()
            return tmp
        except Exception:
            # Last resort: use in-memory DB (not persistent across invocations)
            return ":memory:"


DB_PATH = _choose_db_path()
APP_ROOT = Path(__file__).parent


def _choose_paint_sessions_dir() -> Path:
    """Return a writable Path for paint_sessions.

    Preference order:
    1. `PAINT_SESSIONS_DIR` env var (absolute or repo-relative)
    2. repo `paint_sessions/` if writable
    3. system temp directory under `paint_sessions/`
    4. plain system temp directory (last resort)
    """
    env_path = os.environ.get("PAINT_SESSIONS_DIR")
    if env_path:
        p = Path(env_path)
        if not p.is_absolute():
            p = APP_ROOT / p
    else:
        p = APP_ROOT / "paint_sessions"

    try:
        p.mkdir(parents=True, exist_ok=True)
        return p
    except OSError:
        # Repo path is not writable (serverless). Try system temp dir.
        tmp = Path(tempfile.gettempdir()) / "paint_sessions"
        try:
            tmp.mkdir(parents=True, exist_ok=True)
            return tmp
        except Exception:
            # As a last resort return the plain temp dir (no nested folder)
            return Path(tempfile.gettempdir())


PAINT_SESSIONS_DIR = _choose_paint_sessions_dir()

def normalize_ai_area_id(area_id: Any) -> str:
    value = str(area_id or "").strip().lower().replace("_", "-")
    if value in {"wall", "walls", "main-wall", "main-walls"}:
        return "wall-main"
    for allowed in ("wall-main", "trim", "column", "detail", "accent", "ceiling", "roof", "window-frame", "door"):
        if value == allowed or value.startswith(f"{allowed}-"):
            return allowed
    return value


def normalize_layer_type(value: Any, fallback_id: Any = None) -> str:
    raw = str(value or fallback_id or "").strip().lower().replace("_", "-")
    if raw in {"walls", "main-wall", "main-walls", "facade", "facade-wall"} or raw.startswith("wall"):
        return "wall"
    if raw.startswith("column") or raw in {"pillar", "pilaster"}:
        return "column"
    if raw.startswith("trim") or raw in {"molding", "cornice", "border", "detail", "decorative-detail"}:
        return "trim"
    if raw.startswith("window"):
        return "window-frame"
    if raw.startswith("door"):
        return "door"
    if raw.startswith("roof"):
        return "roof"
    if raw.startswith("ceiling"):
        return "ceiling"
    if raw.startswith("accent"):
        return "accent"
    return raw or "wall"


LAYER_PRIORITY = {
    "wall": 10,
    "wall-main": 10,
    "accent": 15,
    "ceiling": 15,
    "roof": 20,
    "column": 30,
    "trim": 40,
    "detail": 40,
    "window-frame": 50,
    "door": 60,
}


def get_layer_priority(layer_type: Any, area_id: Any = None, explicit_priority: Any = None) -> int:
    try:
        if explicit_priority is not None:
            return int(explicit_priority)
    except (TypeError, ValueError):
        pass
    layer_type = normalize_layer_type(layer_type, area_id)
    area_id = normalize_ai_area_id(area_id)
    return LAYER_PRIORITY.get(layer_type, LAYER_PRIORITY.get(area_id, 10))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _session_dir(image_id: str) -> Path:
    clean_id = "".join(ch for ch in image_id if ch.isalnum() or ch in {"-", "_"})
    if not clean_id:
        raise HTTPException(status_code=400, detail="image_id không hợp lệ")
    path = PAINT_SESSIONS_DIR / clean_id
    if not path.resolve().is_relative_to(PAINT_SESSIONS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="image_id không hợp lệ")
    return path


def _load_session_meta(image_id: str) -> Dict[str, Any]:
    meta_path = _session_dir(image_id) / "metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên ảnh")
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _save_session_meta(image_id: str, meta: Dict[str, Any]) -> None:
    meta_path = _session_dir(image_id) / "metadata.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _gemini_request_timeout() -> int:
    """Return a bounded timeout for Gemini calls.

    The default is kept below common client/proxy read timeouts so slow model
    responses fail fast with a clear error instead of surfacing as an opaque
    upstream timeout.
    """
    raw_timeout = os.environ.get("GEMINI_REQUEST_TIMEOUT_SECONDS", "45")
    try:
        timeout = int(raw_timeout)
    except (TypeError, ValueError):
        timeout = 45
    return max(5, min(timeout, 120))

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

@app.get("/api/ai/sam-status")
def get_sam_status():
    """Return whether optional Segment Anything integration is ready."""
    try:
        from sam_segmenter import _get_checkpoint_path, is_sam_available

        checkpoint = _get_checkpoint_path()
        missing = []
        try:
            import segment_anything  # noqa: F401
        except Exception:
            missing.append("segment_anything")
        try:
            import numpy as np
            numpy_version = np.__version__
            if int(str(numpy_version).split(".", 1)[0]) >= 2:
                missing.append("numpy<2")
        except Exception:
            numpy_version = None
            missing.append("numpy")
        try:
            import torch
            torch_version = torch.__version__
        except Exception:
            torch_version = None
            missing.append("torch")

        return {
            "success": True,
            "sam_available": bool(is_sam_available()),
            "model_type": os.environ.get("SAM_MODEL_TYPE", "vit_b"),
            "device": os.environ.get("SAM_DEVICE", "auto"),
            "checkpoint_configured": bool(checkpoint),
            "checkpoint_path": checkpoint or None,
            "missing_requirements": missing,
            "numpy_version": numpy_version,
            "torch_version": torch_version,
        }
    except Exception as e:
        return {
            "success": True,
            "sam_available": False,
            "error": str(e),
        }

# ==========================================================================
# 2. API DANH SÁCH MẪU NHÀ (PHÂN TRANG)
# ==========================================================================
class UploadPaintImageRequest(BaseModel):
    image: str = Field(..., description="Base64 image data")


class ApplyPaintRequest(BaseModel):
    image_id: str = Field(..., description="ID returned by /api/upload-image")
    x: int = Field(..., ge=0, description="Click X coordinate in image pixels")
    y: int = Field(..., ge=0, description="Click Y coordinate in image pixels")
    color: str = Field(..., description="Target HEX color, e.g. #D8C3A5")
    blend_space: str = Field("hsv", description="Currently supports hsv")

    @field_validator("color")
    @classmethod
    def validate_color(cls, value):
        color = (value or "").strip()
        if color.startswith("#"):
            color = color[1:]
        if len(color) != 6:
            raise ValueError("color must be a valid #RRGGBB HEX value")
        try:
            int(color, 16)
        except ValueError as exc:
            raise ValueError("color must be a valid #RRGGBB HEX value") from exc
        return f"#{color.upper()}"


@app.post("/api/upload-image")
def upload_paint_image(payload: UploadPaintImageRequest):
    """Store an uploaded image and precompute click-selectable paint masks."""
    try:
        from image_painter import _decode_image, generate_click_masks

        image = _decode_image(payload.image)
        if image is None:
            raise HTTPException(status_code=400, detail="Không thể đọc ảnh upload")

        image_id = uuid.uuid4().hex
        session_path = _session_dir(image_id)
        masks_path = session_path / "masks"
        masks_path.mkdir(parents=True, exist_ok=True)

        image.save(session_path / "original.png", format="PNG")
        image.save(session_path / "current.png", format="PNG")

        mask_meta = []
        layer_meta = None
        masks, source = generate_click_masks(image)
        for mask_id, mask, meta in masks:
            mask.save(masks_path / f"{mask_id}.png", format="PNG", optimize=True)
            mask_meta.append({
                "id": mask_id,
                "type": normalize_layer_type(meta.get("type"), mask_id),
                "path": f"masks/{mask_id}.png",
                "priority": get_layer_priority(meta.get("type"), mask_id, meta.get("priority")),
                "area": meta.get("area", 0),
                "bbox": meta.get("bbox"),
                "source": meta.get("source", source),
            })


        metadata = {
            "image_id": image_id,
            "width": image.size[0],
            "height": image.size[1],
            "current_version": 0,
            "mask_source": source,
            "layer_meta": layer_meta,
            "masks": mask_meta,
        }
        _save_session_meta(image_id, metadata)

        return {
            "success": True,
            "image_id": image_id,
            "image_url": f"/api/paint-image/{image_id}",
            "masks_ready": len(mask_meta) > 0,
            "mask_source": source,
            "mask_count": len(mask_meta),
            "data": metadata,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi upload/tạo mask: {str(e)}")


@app.post("/api/apply-paint")
def apply_paint(payload: ApplyPaintRequest):
    """Apply a selected HEX color to the precomputed mask under click X/Y."""
    try:
        from PIL import Image
        from image_painter import create_click_mask, encode_pil_image, paint_with_hsv_mask, refine_mask_for_click

        session_path = _session_dir(payload.image_id)
        metadata = _load_session_meta(payload.image_id)
        current_path = session_path / "current.png"
        original_path = session_path / "original.png"
        if not current_path.exists():
            raise HTTPException(status_code=404, detail="Không tìm thấy ảnh hiện tại")

        current = Image.open(current_path).convert("RGB")
        mask_source_image = Image.open(original_path).convert("RGB") if original_path.exists() else current
        width, height = current.size
        if payload.x >= width or payload.y >= height:
            raise HTTPException(status_code=400, detail="Tọa độ click nằm ngoài ảnh")

        selected_mask = None
        selected_meta = None
        candidates = []
        for mask_meta in metadata.get("masks", []):
            mask_path = session_path / mask_meta.get("path", "")
            if not mask_path.exists():
                continue
            mask = Image.open(mask_path).convert("L")
            if mask.getpixel((payload.x, payload.y)) > 0:
                candidates.append((mask_meta, mask))

        if candidates:
            selected_meta, raw_mask = sorted(
                candidates,
                key=lambda item: (
                    int(item[0].get("priority", 10)),
                    -int(item[0].get("area", 0)),
                ),
                reverse=True,
            )[0]
            selected_mask = refine_mask_for_click(mask_source_image, raw_mask, payload.x, payload.y)

        if selected_mask is None:
            if metadata.get("mask_source") == "ai_layer_mask":
                return {
                    "success": False,
                    "error_type": "ai_mask_not_found",
                    "message": "KhÃ´ng tÃ¬m tháº¥y AI layer mask táº¡i tá»a Ä‘á»™ click nÃ y. HÃ£y click gáº§n vÃ¹ng Ä‘Ã£ Ä‘Æ°á»£c AI phÃ¢n tÃ¡ch.",
                }
            selected_mask = create_click_mask(mask_source_image, payload.x, payload.y)
            if selected_mask is None:
                return {
                    "success": False,
                    "error_type": "mask_not_found",
                    "message": "Không tìm thấy vùng mask phù hợp tại tọa độ click này.",
                }
            mask_id = f"mask_{len(metadata.get('masks', [])) + 1:03d}"
            masks_path = session_path / "masks"
            masks_path.mkdir(exist_ok=True)
            selected_mask.save(masks_path / f"{mask_id}.png", format="PNG", optimize=True)
            bbox = selected_mask.getbbox()
            selected_meta = {
                "id": mask_id,
                "type": "wall",
                "path": f"masks/{mask_id}.png",
                "priority": get_layer_priority("wall", mask_id),
                "area": sum(count for value, count in enumerate(selected_mask.histogram()) if value > 0),
                "bbox": list(bbox) if bbox else None,
                "source": "click_connected_color",
            }
            metadata.setdefault("masks", []).append(selected_meta)

        result = paint_with_hsv_mask(current, selected_mask, payload.color)
        metadata["current_version"] = int(metadata.get("current_version", 0)) + 1
        result.save(current_path, format="PNG", optimize=True)
        _save_session_meta(payload.image_id, metadata)

        painted_pixels = sum(count for value, count in enumerate(selected_mask.histogram()) if value > 0)
        result_image = encode_pil_image(result)
        image_url = f"/api/paint-image/{payload.image_id}?v={metadata['current_version']}"
        return {
            "success": True,
            "image": result_image,
            "image_url": image_url,
            "mask_id": selected_meta.get("id"),
            "data": {
                "image": result_image,
                "image_url": image_url,
                "paint_meta": {
                    "mask_id": selected_meta.get("id"),
                    "mask_type": selected_meta.get("type"),
                    "priority": selected_meta.get("priority"),
                    "blend_space": "hsv",
                    "painted_pixels": painted_pixels,
                    "mask_source": selected_meta.get("source"),
                },
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi apply-paint: {str(e)}")


@app.get("/api/paint-image/{image_id}")
def get_paint_image(image_id: str):
    current_path = _session_dir(image_id) / "current.png"
    if not current_path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh hiện tại")
    return FileResponse(current_path, media_type="image/png")


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
    project_type: Optional[str] = None
    requested_areas: Optional[List[Dict[str, Any]]] = None

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

    requested_areas = []
    for area in payload.requested_areas or []:
        if not isinstance(area, dict):
            continue
        area_id = str(area.get("id") or "").strip()
        label = str(area.get("label") or area.get("name") or area_id).strip()
        if area_id and label:
            requested_areas.append({"id": area_id, "label": label})

    if requested_areas:
        requested_areas_text = "\n".join(
            f'- "{area["id"]}": {area["label"]}' for area in requested_areas
        )
        schema_id_hint = '"<requested-area-id>"'
        id_rule = (
            "Detect ONLY the user-selected paint areas below. Use exactly these ids. Do not rename, merge, or replace them with generic ids:\n"
            f"{requested_areas_text}\n"
            "Return detected_areas only for selected ids. If the same selected area appears in multiple disconnected parts, return multiple entries with the same id."
        )
    else:
        schema_id_hint = '"wall-main" | "trim" | "column" | "detail" | "accent" | "ceiling"'
        id_rule = "Use only the allowed IDs for the detected space."

    project_type_hint = (
        f'The user selected project_type="{payload.project_type}". Respect it when it matches the image.'
        if payload.project_type in {"interior", "exterior"}
        else "Detect whether the image is exterior or interior and set space_type accordingly."
    )

    system_prompt = f"""
You are a computer vision and architectural analysis engine integrated into a paint-coloring application.

Your task is to analyze the provided building image and return only a single valid JSON object that matches this schema exactly:
{{
  "space_type": "exterior" | "interior",
  "detected_areas": [
    {{
      "id": {schema_id_hint},
      "type": "wall" | "roof" | "column" | "trim" | "window_frame" | "door" | "ceiling" | "accent",
      "name_vi": "string",
      "box_2d": [ymin, xmin, ymax, xmax],
      "polygon_2d": [[y, x], [y, x], [y, x]],
      "seed_points_2d": [[y, x], [y, x]],
      "priority": 10
    }}
  ],
  "suggested_palettes": [
    {{
      "style_name": "string",
      "colors": {{
        "<area-id>": "#RRGGBB"
      }}
    }}
  ]
}}

Rules:
- {project_type_hint}
- {id_rule}
- This system is for paint companies. Accuracy of paintable-region boundaries is more important than finding every possible region.
- For each detected area, provide the tightest possible normalized bounding box on a 0-1000 scale in [ymin, xmin, ymax, xmax] order.
- Also provide polygon_2d points on the same 0-1000 scale when the paintable surface is not rectangular. Trace only the paintable surface, excluding doors, windows, glass, roof tiles, sky, furniture, trees, people, floors, ground, pavement, signs, lamps, and decorative objects that should not receive paint.
- Provide 1 to 5 seed_points_2d inside each detected paintable surface. Put seed points near the center of the material that should change color, not on edges, windows, shadows, plants, furniture, or background.
- Classify each area with type and priority. Use priority wall=10, roof=20, column=30, trim/detail=40, window_frame=50, door=60 unless a requested region clearly maps to a more specific category.
- For trim/phào chỉ, molding, cornice, borders, columns, and small architectural details, use narrow boxes and polygons around only that element. Do not include adjacent wall-main surfaces.
- If the selected area is not clearly visible, omit it instead of guessing.
- Prefer fewer, accurate paintable areas over broad boxes that include non-paint surfaces.
- Keep distinct requested regions separate even when they have similar material or color.
- Include at most 2 suggested palettes.
- Use valid HEX colors only.
- If an area is not visible, omit it.
- Return JSON only. Do not include markdown fences, comments, explanations, or extra text.
"""

    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    request_data = {
        "contents": [
            {
                "parts": [
                    {"text": "Analyze the building image and return the requested JSON schema with only the selected paint areas, normalized bounding boxes, polygons, seed points, and suggested palettes."},
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

        with urllib.request.urlopen(req, timeout=_gemini_request_timeout()) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)

            candidates = res_json.get("candidates", [])
            if not candidates:
                return {"success": False, "message": "Không nhận được câu trả lời từ Gemini API."}

            text_content = candidates[0]["content"]["parts"][0]["text"].strip()
            if text_content.startswith("```"):
                text_content = text_content.strip("`").replace("json\n", "", 1).strip()
            ai_data = json.loads(text_content)
            
            # Be tolerant when Gemini returns a semantically correct but slightly
            # different key shape. The frontend expects data.detected_areas.
            if isinstance(ai_data, list):
                ai_data = {"detected_areas": ai_data}
            detected_areas = (
                ai_data.get("detected_areas")
                or ai_data.get("detectedAreas")
                or ai_data.get("areas")
                or ai_data.get("paintable_areas")
                or ai_data.get("regions")
                or []
            )
            normalized_areas = []
            for area in detected_areas if isinstance(detected_areas, list) else []:
                if not isinstance(area, dict):
                    continue
                box = (
                    area.get("box_2d")
                    or area.get("box2d")
                    or area.get("bbox")
                    or area.get("bounding_box")
                    or area.get("boundingBox")
                )
                raw_area_id = area.get("id") or area.get("area_id") or area.get("type")
                area_id = str(raw_area_id or "").strip()
                if not any(requested["id"] == area_id for requested in requested_areas):
                    area_id = normalize_ai_area_id(raw_area_id)
                if area_id and box and len(box) == 4:
                    normalized = dict(area)
                    normalized["id"] = area_id
                    layer_type = normalize_layer_type(area.get("type"), area_id)
                    normalized["type"] = layer_type
                    normalized["priority"] = get_layer_priority(layer_type, area_id, area.get("priority"))
                    normalized["box_2d"] = box
                    seed_points = (
                        area.get("seed_points_2d")
                        or area.get("seedPoints2d")
                        or area.get("seed_points")
                        or area.get("seedPoints")
                    )
                    if seed_points:
                        normalized["seed_points_2d"] = seed_points
                    normalized_areas.append(normalized)
            ai_data["detected_areas"] = normalized_areas

            return {
                "success": True,
                "data": ai_data
            }
    
    except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
        error_detail = str(e)
        if isinstance(e, urllib.error.URLError) and getattr(e, "reason", None):
            error_detail = str(e.reason)

        if "timed out" in error_detail.lower():
            return {
                "success": False,
                "error_type": "timeout",
                "message": "❌ Gemini phản hồi quá chậm. Vui lòng thử lại hoặc giảm kích thước ảnh trước khi phân tích.",
                "detail": error_detail
            }

        return {
            "success": False,
            "error_type": "network_error",
            "message": "❌ Không thể kết nối tới Gemini API.",
            "detail": error_detail
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
    detectedAreas: Optional[List[Dict[str, Any]]] = Field(default=[], description="Optional AI-detected bounding boxes")
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
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        
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
    
    # Strict behavior: require AI-detected areas. Do NOT fallback to geometric masking.
    # If detectedAreas is missing or empty, raise a 400 so frontend shows a clear message to user.
    if not payload.detectedAreas or len(payload.detectedAreas) == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Không thể phối màu do hệ thống không nhận được dữ liệu phân vùng từ AI "
                "(Có thể do hết hạn mức API hoặc Key lỗi). Vui lòng kiểm tra lại!"
            )
        )

    try:
        # Import only the AI-based painter
        from image_painter import apply_paint_color_ai_with_meta

        result_image, paint_meta = apply_paint_color_ai_with_meta(
            payload.image,
            payload.paintAreas,
            payload.detectedAreas,
            payload.projectType
        )

        if not paint_meta.get("changed") or paint_meta.get("painted_pixels", 0) <= 0:
            return {
                "success": False,
                "error_type": "empty_paint_mask",
                "message": (
                    "AI đã phân tích ảnh nhưng không tạo được mask sơn có hiệu lực. "
                    "Hãy chọn đúng vùng có trong ảnh hoặc thử màu khác/vùng khác."
                ),
                "data": {"paint_meta": paint_meta},
            }

        return {
            "success": True,
            "image": result_image,
            "data": {"image": result_image, "paint_meta": paint_meta},
            "message": "✨ Ảnh phối màu được tạo thành công (sử dụng AI-detected areas)",
        }

    except ImportError:
        raise HTTPException(status_code=500, detail="Module image_painter chưa được cài đặt.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý ảnh: {str(e)}")

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
