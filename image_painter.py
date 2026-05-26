#!/usr/bin/env python3
"""
Image Painting Module - AI optimized.

The Gemini step supplies paintable areas. This module turns those coarse AI
areas into soft masks and blends paint while preserving the source lighting.
"""

import base64
import io
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

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
    "window_frame": 50,
    "door": 60,
}


# ============================================================================
# STANDARDIZED MASK PIPELINE - Prevents spillover & improves mask precision
# ============================================================================

class MaskPipeline:
    """
    Standardized 5-stage mask generation pipeline.
    Prevents paint spillover, shadow bleed, and inaccurate layer boundaries.
    """
    
    def __init__(self, image, box, polygon, area_id, project_type="interior", sam_session=None):
        self.image = image
        self.box = box
        self.polygon = polygon
        self.area_id = area_id
        self.project_type = project_type  # "interior" or "exterior"
        self.sam_session = sam_session
        self.width, self.height = image.size
        self.stages = {}  # Track each stage
        self.logger_info = []
        
    def _apply_boundary_constraint(self, mask):
        """
        Constrain mask to safe regions (prevent spillover to sky/ground).
        
        Exterior: Keep TOP 25% free (sky), BOTTOM 10% free (ground)
        Interior: Keep BOTTOM 25% free (floor)
        """
        pil = _load_pil()
        if pil is None:
            return mask
        Image, ImageChops, _, _, _, _ = pil
        
        constraint = Image.new("L", (self.width, self.height), 255)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(constraint)
        
        if self.project_type == "exterior":
            # ❌ Protect sky (top 25%)
            sky_limit = int(self.height * 0.25)
            draw.rectangle([0, 0, self.width, sky_limit], fill=0)
            # ❌ Protect ground (bottom 10%)
            ground_start = int(self.height * 0.90)
            draw.rectangle([0, ground_start, self.width, self.height], fill=0)
        elif self.project_type == "interior":
            # ❌ Protect floor (bottom 25%)
            floor_start = int(self.height * 0.75)
            draw.rectangle([0, floor_start, self.width, self.height], fill=0)
        
        constrained = ImageChops.multiply(mask, constraint)
        self.logger_info.append(f"Boundary constraint applied for {self.project_type}")
        return constrained
    
    def stage_1_shape(self):
        """Stage 1: Create initial shape mask from box/polygon."""
        shape_mask = _make_shape_mask(self.image.size, self.box, self.polygon)
        self.stages["shape"] = {
            "mask": shape_mask,
            "area": _mask_area(shape_mask),
            "source": "geometric"
        }
        self.logger_info.append(f"Stage 1 shape: area={self.stages['shape']['area']}")
        return self
    
    def stage_2_surface_detection(self, seed_points=None):
        """Stage 2: Detect surface using SAM or color-connected (with fallback)."""
        shape_mask = self.stages.get("shape", {}).get("mask")
        if shape_mask is None:
            return self
        
        source = "unknown"
        surface_mask = None
        
        # Try SAM first
        if self.sam_session is not None:
            try:
                surface_mask = self.sam_session.predict_mask(self.box, shape_mask, seed_points)
                source = "sam"
            except Exception:
                surface_mask = None
        
        # Fallback to connected color
        if surface_mask is None:
            surface_mask = _connected_surface_mask(
                self.image, shape_mask, self.box, self.area_id, seed_points
            )
            source = "connected_color"
        
        self.stages["surface"] = {
            "mask": surface_mask,
            "area": _mask_area(surface_mask),
            "source": source
        }
        self.logger_info.append(f"Stage 2 surface: area={self.stages['surface']['area']}, source={source}")
        return self
    
    def stage_3_boundary_constraint(self):
        """Stage 3: Apply regional constraints (sky, floor, etc.)."""
        surface_mask = self.stages.get("surface", {}).get("mask")
        if surface_mask is None:
            return self
        
        constrained = self._apply_boundary_constraint(surface_mask)
        self.stages["constrained"] = {
            "mask": constrained,
            "area": _mask_area(constrained),
            "source": "boundary-constrained"
        }
        self.logger_info.append(f"Stage 3 constrained: area={self.stages['constrained']['area']}")
        return self
    
    def stage_4_merge_and_clean(self):
        """Stage 4: Merge with shape, clean noise, apply STRONG edge detection."""
        pil = _load_pil()
        Image, ImageChops, _, ImageEnhance, ImageFilter, ImageStat = pil
        
        shape_mask = self.stages.get("shape", {}).get("mask")
        constrained_mask = self.stages.get("constrained", {}).get("mask") or self.stages.get("surface", {}).get("mask")
        
        if constrained_mask is None or shape_mask is None:
            return self
        
        # Merge with shape
        merged = ImageChops.multiply(constrained_mask, shape_mask)
        
        # STRONG edge detection to prevent spillover
        gray = ImageEnhance.Contrast(self.image.convert("L")).enhance(1.5)  # ← Stronger
        edges = gray.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(0.3))  # ← Tighter
        edge_threshold = max(18, min(60, int(edges.getextrema()[1] * 0.6)))  # ← Aggressive
        edge_barrier = edges.point(lambda p: 0 if p > edge_threshold else 255)
        
        # Apply edge barrier
        merged = ImageChops.multiply(merged, edge_barrier)
        
        # Conservative median filter to preserve boundaries
        cleaned = merged.filter(ImageFilter.MedianFilter(3))  # ← Smaller kernel
        
        self.stages["merged"] = {
            "mask": cleaned,
            "area": _mask_area(cleaned),
            "source": "merged+edge-detected"
        }
        self.logger_info.append(f"Stage 4 merged: area={self.stages['merged']['area']}")
        return self
    
    def stage_5_soft_blur(self):
        """Stage 5: Apply CONSERVATIVE soft blur (not too much)."""
        pil = _load_pil()
        Image, _, _, _, ImageFilter, _ = pil
        
        cleaned_mask = self.stages.get("merged", {}).get("mask")
        if cleaned_mask is None:
            return self
        
        # Conservative blur: only 0.3px instead of 0.8
        soft_blurred = cleaned_mask.filter(ImageFilter.GaussianBlur(0.3))  # ← Reduced blur
        
        self.stages["final"] = {
            "mask": soft_blurred,
            "area": _mask_area(soft_blurred),
            "source": "soft-blurred"
        }
        self.logger_info.append(f"Stage 5 final: area={self.stages['final']['area']}")
        return self
    
    def build(self):
        """Execute full standardized pipeline."""
        return (
            self.stage_1_shape()
            .stage_2_surface_detection()
            .stage_3_boundary_constraint()
            .stage_4_merge_and_clean()
            .stage_5_soft_blur()
        )
    
    def get_result(self):
        """Return final mask and detailed metadata."""
        if "final" not in self.stages:
            return None, {"error": "Pipeline not executed"}
        
        final_mask = self.stages["final"]["mask"]
        
        if not final_mask or not final_mask.getbbox():
            return None, {"error": "Final mask is empty"}
        
        return final_mask, {
            "stages": {
                name: {
                    "area": info["area"],
                    "source": info["source"],
                    "bbox": _mask_bbox_list(info["mask"])
                }
                for name, info in self.stages.items()
            },
            "pipeline_source": self.stages["surface"].get("source", "unknown"),
            "project_type": self.project_type,
            "debug_log": self.logger_info
        }


def _load_pil():
    try:
        from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageStat
        return Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageStat
    except ImportError:
        return None


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = (hex_color or "").strip().lstrip("#")
    if len(hex_color) != 6:
        return (255, 255, 255)
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _normalize_area_id(area_id: Any) -> str:
    value = str(area_id or "").strip().lower().replace("_", "-")
    if value in {"wall", "walls", "main-wall", "main-walls"}:
        return "wall-main"
    for allowed in ("wall-main", "trim", "column", "detail", "accent", "ceiling", "roof", "window-frame", "door"):
        if value == allowed or value.startswith(f"{allowed}-"):
            return allowed
    return value


def normalize_layer_type(value: Any, fallback_id: Any = None) -> str:
    raw = str(value or fallback_id or "").strip().lower().replace("_", "-")
    if raw in {"walls", "main-wall", "main-walls", "facade", "facade-wall"}:
        return "wall"
    if raw.startswith("wall"):
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


def get_layer_priority(layer_type: Any, area_id: Any = None, explicit_priority: Any = None) -> int:
    try:
        if explicit_priority is not None:
            return int(explicit_priority)
    except (TypeError, ValueError):
        pass
    normalized_type = normalize_layer_type(layer_type, area_id)
    normalized_id = _normalize_area_id(area_id)
    return LAYER_PRIORITY.get(normalized_type, LAYER_PRIORITY.get(normalized_id, 10))


def _area_exact_id(area_id: Any) -> str:
    return str(area_id or "").strip().lower().replace("_", "-")


def _area_lookup_keys(area_id: Any) -> List[str]:
    exact = _area_exact_id(area_id)
    normalized = _normalize_area_id(area_id)
    keys = [exact] if exact else []
    if normalized and normalized not in keys:
        keys.append(normalized)
    return keys


def _decode_image(image_base64: str):
    pil = _load_pil()
    if pil is None:
        return None
    Image, *_ = pil
    if "," in image_base64:
        _, base64_data = image_base64.split(",", 1)
    else:
        base64_data = image_base64
    image_bytes = base64.b64decode(base64_data)
    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


def _encode_image(image) -> str:
    output_bytes = io.BytesIO()
    image.save(output_bytes, format="PNG", optimize=True)
    result_base64 = base64.b64encode(output_bytes.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{result_base64}"


def encode_pil_image(image) -> str:
    return _encode_image(image)


def _normalize_box(box: List[Any], width: int, height: int) -> Optional[Tuple[int, int, int, int]]:
    if not box or len(box) != 4:
        return None
    try:
        ymin_n, xmin_n, ymax_n, xmax_n = [float(v) for v in box]
    except (TypeError, ValueError):
        return None

    ymin = int((ymin_n / 1000) * height)
    xmin = int((xmin_n / 1000) * width)
    ymax = int((ymax_n / 1000) * height)
    xmax = int((xmax_n / 1000) * width)

    ymin, ymax = sorted((max(0, ymin), min(height, ymax)))
    xmin, xmax = sorted((max(0, xmin), min(width, xmax)))
    if (xmax - xmin) < 4 or (ymax - ymin) < 4:
        return None
    return xmin, ymin, xmax, ymax


def _normalize_polygon(points: Any, width: int, height: int) -> List[Tuple[int, int]]:
    normalized = []
    if not isinstance(points, list):
        return normalized
    for point in points:
        if not isinstance(point, list) or len(point) != 2:
            continue
        try:
            y_n, x_n = float(point[0]), float(point[1])
        except (TypeError, ValueError):
            continue
        x = max(0, min(width, int((x_n / 1000) * width)))
        y = max(0, min(height, int((y_n / 1000) * height)))
        normalized.append((x, y))
    return normalized if len(normalized) >= 3 else []


def _normalize_seed_points(points: Any, width: int, height: int) -> List[Tuple[int, int]]:
    normalized = []
    if not isinstance(points, list):
        return normalized
    for point in points:
        if not isinstance(point, list) or len(point) != 2:
            continue
        try:
            y_n, x_n = float(point[0]), float(point[1])
        except (TypeError, ValueError):
            continue
        x = max(0, min(width - 1, int((x_n / 1000) * width)))
        y = max(0, min(height - 1, int((y_n / 1000) * height)))
        normalized.append((x, y))
    return normalized[:8]


def _make_shape_mask(size: Tuple[int, int], box: Tuple[int, int, int, int], polygon: List[Tuple[int, int]]):
    pil = _load_pil()
    Image, _, ImageDraw, _, ImageFilter, _ = pil
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    if polygon:
        draw.polygon(polygon, fill=255)
    else:
        draw.rectangle(box, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(0.8))


def _clean_mask(mask):
    pil = _load_pil()
    _, _, _, _, ImageFilter, _ = pil
    return (
        mask.point(lambda p: 255 if p > 10 else 0)
        .filter(ImageFilter.MedianFilter(3))
        .filter(ImageFilter.GaussianBlur(0.7))
    )


def _subtract_mask(base_mask, subtract_mask):
    pil = _load_pil()
    _, ImageChops, _, _, _, _ = pil
    return ImageChops.subtract(base_mask, subtract_mask)


def _edge_aware_mask(image, mask, shape_mask):
    pil = _load_pil()
    Image, ImageChops, _, ImageEnhance, ImageFilter, ImageStat = pil
    gray = ImageEnhance.Contrast(image.convert("L")).enhance(1.35)
    edges = gray.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(0.6))
    stats = ImageStat.Stat(edges)
    mean_edge = stats.mean[0] if stats.mean else 18
    edge_threshold = max(22, min(70, int(mean_edge * 1.55)))
    edge_barrier = edges.point(lambda p: 0 if p > edge_threshold else 255)
    constrained = ImageChops.multiply(mask, edge_barrier)
    constrained = ImageChops.multiply(constrained, shape_mask)
    if _mask_area(constrained) >= max(40, int(_mask_area(mask) * 0.35)):
        return constrained.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(0.35))
    return ImageChops.multiply(mask, shape_mask)


def _is_reasonable_surface_seed(rgb: Tuple[int, int, int], area_id: str) -> bool:
    r, g, b = rgb
    mx, mn = max(rgb), min(rgb)
    saturation = mx - mn
    brightness = (r + g + b) / 3

    if brightness < 35:
        return False
    if area_id in {"wall-main", "ceiling", "accent"}:
        return saturation < 95 and brightness < 245
    return brightness < 250


def _sample_seed_colors(
    image,
    shape_mask,
    box: Tuple[int, int, int, int],
    area_id: str,
    explicit_seed_points: Optional[List[Tuple[int, int]]] = None,
) -> List[Tuple[int, int, int]]:
    xmin, ymin, xmax, ymax = box
    seeds = []
    for x, y in explicit_seed_points or []:
        if xmin <= x < xmax and ymin <= y < ymax and shape_mask.getpixel((x, y)) > 0:
            rgb = image.getpixel((x, y))
            if _is_reasonable_surface_seed(rgb, area_id):
                seeds.append(rgb)

    grid = (0.25, 0.4, 0.5, 0.6, 0.75)
    for gy in grid:
        for gx in grid:
            x = int(xmin + (xmax - xmin) * gx)
            y = int(ymin + (ymax - ymin) * gy)
            if shape_mask.getpixel((x, y)) == 0:
                continue
            rgb = image.getpixel((x, y))
            if _is_reasonable_surface_seed(rgb, area_id):
                seeds.append(rgb)

    if not seeds:
        cx, cy = (xmin + xmax) // 2, (ymin + ymax) // 2
        if shape_mask.getpixel((cx, cy)) > 0:
            seeds.append(image.getpixel((cx, cy)))
    return seeds[:16]


def _color_distance(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> float:
    # Green channel carries more perceived luminance, so weight it slightly.
    return (
        ((a[0] - b[0]) * 0.85) ** 2
        + ((a[1] - b[1]) * 1.15) ** 2
        + ((a[2] - b[2]) * 0.9) ** 2
    ) ** 0.5


def _connected_mask_from_click(
    image,
    click: Tuple[int, int],
    threshold: int = 42,
    max_area_ratio: float = 0.65,
):
    pil = _load_pil()
    Image, ImageChops, ImageDraw, _, ImageFilter, ImageStat = pil
    width, height = image.size
    sx, sy = click
    if sx < 0 or sx >= width or sy < 0 or sy >= height:
        return None

    seed = image.getpixel((sx, sy))
    if not _is_reasonable_surface_seed(seed, "wall-main"):
        threshold = min(threshold, 48)

    max_pixels = int(width * height * max_area_ratio)
    visited = bytearray(width * height)
    q = deque([(sx, sy)])
    visited[sy * width + sx] = 1
    pixels = []

    while q:
        x, y = q.popleft()
        rgb = image.getpixel((x, y))
        if _color_distance(rgb, seed) > threshold:
            continue
        pixels.append((x, y))
        if len(pixels) > max_pixels:
            break
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < 0 or nx >= width or ny < 0 or ny >= height:
                continue
            idx = ny * width + nx
            if visited[idx]:
                continue
            visited[idx] = 1
            q.append((nx, ny))

    if len(pixels) < max(40, int(width * height * 0.00025)):
        return None

    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    rows: Dict[int, List[int]] = {}
    for x, y in pixels:
        rows.setdefault(y, []).append(x)
    for y, xs in rows.items():
        xs.sort()
        start = prev = xs[0]
        for x in xs[1:]:
            if x == prev + 1:
                prev = x
                continue
            draw.line((start, y, prev, y), fill=205)
            start = prev = x
        draw.line((start, y, prev, y), fill=205)

    mask = mask.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.0))
    stat = ImageStat.Stat(mask)
    if stat.extrema and stat.extrema[0][1] < 90:
        mask = mask.point(lambda p: min(205, int(p * 1.5)))
    return mask


def create_click_mask(image, x: int, y: int):
    for threshold in (42, 55, 70, 85):
        mask = _connected_mask_from_click(image, (x, y), threshold=threshold, max_area_ratio=0.45)
        if mask is not None:
            return mask
    return None


def _component_from_mask(mask, click: Tuple[int, int], min_value: int = 8):
    pil = _load_pil()
    Image, _, ImageDraw, _, ImageFilter, _ = pil
    width, height = mask.size
    sx, sy = click
    if sx < 0 or sx >= width or sy < 0 or sy >= height:
        return None
    if mask.getpixel((sx, sy)) <= min_value:
        return None

    visited = bytearray(width * height)
    q = deque([(sx, sy)])
    visited[sy * width + sx] = 1
    pixels = []

    while q:
        x, y = q.popleft()
        if mask.getpixel((x, y)) <= min_value:
            continue
        pixels.append((x, y))
        for nx, ny in (
            (x - 1, y),
            (x + 1, y),
            (x, y - 1),
            (x, y + 1),
            (x - 1, y - 1),
            (x + 1, y - 1),
            (x - 1, y + 1),
            (x + 1, y + 1),
        ):
            if nx < 0 or nx >= width or ny < 0 or ny >= height:
                continue
            idx = ny * width + nx
            if visited[idx]:
                continue
            visited[idx] = 1
            q.append((nx, ny))

    if len(pixels) < max(80, int(width * height * 0.0006)):
        return None

    component = Image.new("L", mask.size, 0)
    draw = ImageDraw.Draw(component)
    rows: Dict[int, List[int]] = {}
    for x, y in pixels:
        rows.setdefault(y, []).append(x)
    for y, xs in rows.items():
        xs.sort()
        start = prev = xs[0]
        for x in xs[1:]:
            if x == prev + 1:
                prev = x
                continue
            draw.line((start, y, prev, y), fill=255)
            start = prev = x
        draw.line((start, y, prev, y), fill=255)
    return component.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(0.6))


def refine_mask_for_click(image, mask, x: int, y: int):
    """Keep only the clicked mask island and tighten broad masks by color."""
    pil = _load_pil()
    _, ImageChops, _, _, ImageFilter, _ = pil
    width, height = image.size
    if mask.size != image.size:
        mask = mask.resize(image.size)

    component = _component_from_mask(mask, (x, y))
    if component is None:
        return None

    component_area = _mask_area(component)
    image_area = width * height
    color_mask = _connected_mask_from_click(image, (x, y), threshold=50, max_area_ratio=0.36)
    if color_mask is None:
        return component

    color_mask = color_mask.point(lambda p: 255 if p > 8 else 0)
    component_binary = component.point(lambda p: 255 if p > 8 else 0)
    tightened = ImageChops.multiply(component_binary, color_mask)
    tightened_area = _mask_area(tightened)

    if tightened_area >= max(120, int(component_area * 0.18)):
        return tightened.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(0.7))
    if component_area > int(image_area * 0.36):
        return color_mask.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(0.7))
    return component


def _mask_area(mask) -> int:
    return sum(count for value, count in enumerate(mask.histogram()) if value > 0)


def _mask_bbox_list(mask) -> Optional[List[int]]:
    bbox = mask.getbbox()
    if not bbox:
        return None
    return [bbox[0], bbox[1], bbox[2], bbox[3]]


def generate_click_masks(image, max_masks: int = 60) -> Tuple[List[Tuple[str, object, Dict[str, Any]]], str]:
    """Generate reusable masks for the click-to-paint API.

    SAM automatic masks are preferred when configured. A lightweight connected
    color-region fallback keeps the API usable in local/dev environments.
    """
    pil = _load_pil()
    if pil is None:
        return [], "pillow_unavailable"

    try:
        from sam_segmenter import generate_auto_masks

        sam_masks = generate_auto_masks(image, max_masks=max_masks)
        if sam_masks:
            results = []
            for idx, mask in enumerate(sam_masks[:max_masks], start=1):
                area = _mask_area(mask)
                bbox = _mask_bbox_list(mask)
                if area <= 0 or not bbox:
                    continue
                results.append((
                    f"mask_{idx:03d}",
                    mask,
                    {"area": area, "bbox": bbox, "source": "sam"},
                ))
            if results:
                return results, "sam"
    except Exception:
        pass

    width, height = image.size
    points = []
    for gy in (0.12, 0.22, 0.32, 0.42, 0.52, 0.62, 0.72, 0.82, 0.92):
        for gx in (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90):
            points.append((int(width * gx), int(height * gy)))

    results = []
    occupied_centers = set()
    for x, y in points:
        if len(results) >= max_masks:
            break
        key = (x // 40, y // 40)
        if key in occupied_centers:
            continue
        mask = _connected_mask_from_click(image, (x, y))
        if mask is None:
            continue
        area = _mask_area(mask)
        bbox = _mask_bbox_list(mask)
        if not bbox or area < max(200, int(width * height * 0.002)):
            continue
        duplicate = False
        for _, existing, _ in results:
            if existing.getpixel((x, y)) > 0:
                duplicate = True
                break
        if duplicate:
            continue
        occupied_centers.add(key)
        results.append((
            f"mask_{len(results) + 1:03d}",
            mask,
            {"area": area, "bbox": bbox, "source": "connected_color"},
        ))
    return results, "connected_color"


def paint_with_hsv_mask(base_image, mask, target_hex: str, strength: float = 0.88):
    pil = _load_pil()
    Image, _, _, ImageEnhance, ImageFilter, _ = pil
    target_rgb = hex_to_rgb(target_hex)
    target_hsv = Image.new("RGB", (1, 1), target_rgb).convert("HSV").getpixel((0, 0))

    base_hsv = base_image.convert("HSV")
    h, s, v = base_hsv.split()
    target_h = Image.new("L", base_image.size, target_hsv[0])
    target_s = Image.new("L", base_image.size, max(18, target_hsv[1]))
    recolored = Image.merge("HSV", (target_h, target_s, v)).convert("RGB")
    painted = Image.blend(base_image, recolored, strength)
    soft_mask = mask.filter(ImageFilter.GaussianBlur(0.8))
    result = Image.composite(painted, base_image, soft_mask)
    return ImageEnhance.Contrast(result).enhance(1.02)


def _refine_shape_mask(
    image,
    shape_mask,
    box: Tuple[int, int, int, int],
    area_id: str,
    explicit_seed_points: Optional[List[Tuple[int, int]]] = None,
):
    pil = _load_pil()
    Image, ImageChops, ImageDraw, _, ImageFilter, ImageStat = pil
    seeds = _sample_seed_colors(image, shape_mask, box, area_id, explicit_seed_points)
    if not seeds:
        return shape_mask.point(lambda p: 150 if p else 0)

    xmin, ymin, xmax, ymax = box
    refined = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(refined)
    threshold = 92 if area_id in {"wall-main", "accent", "ceiling"} else 110

    included = 0
    shape_pixels = 0
    for y in range(ymin, ymax):
        run_start = None
        for x in range(xmin, xmax):
            if shape_mask.getpixel((x, y)) == 0:
                if run_start is not None:
                    draw.line((run_start, y, x - 1, y), fill=175)
                    run_start = None
                continue

            shape_pixels += 1
            rgb = image.getpixel((x, y))
            mx, mn = max(rgb), min(rgb)
            brightness = sum(rgb) / 3
            saturation = mx - mn
            min_dist = min(_color_distance(rgb, seed) for seed in seeds)

            is_surface = min_dist <= threshold
            if area_id in {"wall-main", "accent", "ceiling"}:
                # Large painted surfaces are usually continuous, moderately
                # saturated planes. This avoids obvious glass/sky/tree blocks.
                is_surface = is_surface or (saturation < 55 and 45 < brightness < 238)

            if is_surface:
                included += 1
                if run_start is None:
                    run_start = x
            elif run_start is not None:
                draw.line((run_start, y, x - 1, y), fill=175)
                run_start = None

        if run_start is not None:
            draw.line((run_start, y, xmax - 1, y), fill=175)

    if not shape_pixels or included / shape_pixels < 0.08:
        # AI box is valid but the local refinement was too strict; use a soft,
        # low-strength area instead of returning no visible result.
        return shape_mask.point(lambda p: 115 if p else 0).filter(ImageFilter.GaussianBlur(1.2))

    refined = refined.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.3))
    refined = ImageChops.multiply(refined, shape_mask)

    # Keep the mask from becoming overly faint after multiplication.
    stat = ImageStat.Stat(refined.crop(box))
    if stat.extrema and stat.extrema[0][1] < 80:
        refined = refined.point(lambda p: min(185, int(p * 1.8)))
    return refined


def _connected_surface_mask(
    image,
    shape_mask,
    box: Tuple[int, int, int, int],
    area_id: str,
    explicit_seed_points: Optional[List[Tuple[int, int]]] = None,
):
    """Create a connected pixel mask from seed colors inside the AI polygon/box."""
    pil = _load_pil()
    Image, ImageChops, ImageDraw, _, ImageFilter, ImageStat = pil
    seeds = _sample_seed_colors(image, shape_mask, box, area_id, explicit_seed_points)
    if not seeds:
        return _refine_shape_mask(image, shape_mask, box, area_id, explicit_seed_points)

    xmin, ymin, xmax, ymax = box
    width = max(1, xmax - xmin)
    height = max(1, ymax - ymin)
    threshold = 55 if area_id in {"wall-main", "accent", "ceiling"} else 65

    candidate = bytearray(width * height)
    seed_points = []
    for y in range(ymin, ymax):
        for x in range(xmin, xmax):
            if shape_mask.getpixel((x, y)) == 0:
                continue
            rgb = image.getpixel((x, y))
            brightness = sum(rgb) / 3
            saturation = max(rgb) - min(rgb)
            min_dist = min(_color_distance(rgb, seed) for seed in seeds)
            is_candidate = min_dist <= threshold
            if area_id in {"wall-main", "accent", "ceiling"}:
                is_candidate = is_candidate or (saturation < 48 and 50 < brightness < 235)
            if is_candidate:
                idx = (y - ymin) * width + (x - xmin)
                candidate[idx] = 1

    for sx, sy in explicit_seed_points or []:
        if sx < xmin or sx >= xmax or sy < ymin or sy >= ymax:
            continue
        idx = (sy - ymin) * width + (sx - xmin)
        if candidate[idx]:
            seed_points.append((sx, sy))

    for gy in (0.28, 0.42, 0.5, 0.58, 0.72):
        for gx in (0.28, 0.42, 0.5, 0.58, 0.72):
            sx = int(xmin + width * gx)
            sy = int(ymin + height * gy)
            if sx < xmin or sx >= xmax or sy < ymin or sy >= ymax:
                continue
            idx = (sy - ymin) * width + (sx - xmin)
            if candidate[idx]:
                seed_points.append((sx, sy))

    if not seed_points:
        return _refine_shape_mask(image, shape_mask, box, area_id, explicit_seed_points)

    visited = bytearray(width * height)
    q = deque(seed_points)
    for sx, sy in seed_points:
        visited[(sy - ymin) * width + (sx - xmin)] = 1

    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < xmin or nx >= xmax or ny < ymin or ny >= ymax:
                continue
            idx = (ny - ymin) * width + (nx - xmin)
            if visited[idx] or not candidate[idx]:
                continue
            visited[idx] = 1
            q.append((nx, ny))

    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    included = 0
    for y in range(ymin, ymax):
        run_start = None
        for x in range(xmin, xmax):
            idx = (y - ymin) * width + (x - xmin)
            if visited[idx]:
                included += 1
                if run_start is None:
                    run_start = x
            elif run_start is not None:
                draw.line((run_start, y, x - 1, y), fill=190)
                run_start = None
        if run_start is not None:
            draw.line((run_start, y, xmax - 1, y), fill=190)

    shape_area = sum(1 for p in candidate if p)
    if not shape_area or included / shape_area < 0.12:
        return _refine_shape_mask(image, shape_mask, box, area_id, explicit_seed_points)

    mask = mask.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.1))
    mask = ImageChops.multiply(mask, shape_mask)
    stat = ImageStat.Stat(mask.crop(box))
    if stat.extrema and stat.extrema[0][1] < 90:
        mask = mask.point(lambda p: min(190, int(p * 1.6)))
    return mask


def _sam_or_connected_mask(
    image,
    shape_mask,
    box: Tuple[int, int, int, int],
    area_id: str,
    explicit_seed_points: Optional[List[Tuple[int, int]]] = None,
):
    try:
        from sam_segmenter import predict_mask

        sam_mask = predict_mask(image, box, shape_mask, explicit_seed_points)
        if sam_mask is not None:
            return sam_mask
    except Exception:
        pass
    return _connected_surface_mask(image, shape_mask, box, area_id, explicit_seed_points)


def _session_sam_or_connected_mask(
    sam_session,
    image,
    shape_mask,
    box: Tuple[int, int, int, int],
    area_id: str,
    explicit_seed_points: Optional[List[Tuple[int, int]]] = None,
):
    if sam_session is not None:
        sam_mask = sam_session.predict_mask(box, shape_mask, explicit_seed_points)
        if sam_mask is not None:
            return sam_mask, True
    return _connected_surface_mask(image, shape_mask, box, area_id, explicit_seed_points), False


def _paint_with_mask(base_image, target_rgb: Tuple[int, int, int], mask):
    pil = _load_pil()
    Image, _, _, ImageEnhance, ImageFilter, _ = pil
    mask = mask.point(lambda p: 255 if p > 35 else 0).filter(ImageFilter.GaussianBlur(0.4))
    
    # Convert to HSV to preserve shadows and brightness information
    target_hsv = Image.new("RGB", (1, 1), target_rgb).convert("HSV").getpixel((0, 0))
    base_hsv = base_image.convert("HSV")
    h, s, v = base_hsv.split()
    
    # Apply new hue & saturation while preserving original Value (brightness/shadows)
    # This ensures shadows, highlights, and depth remain unchanged
    target_h = Image.new("L", base_image.size, target_hsv[0])
    target_s = Image.new("L", base_image.size, max(18, target_hsv[1]))
    recolored = Image.merge("HSV", (target_h, target_s, v)).convert("RGB")
    
    # Blend for natural appearance without flat color bands
    painted = Image.blend(base_image, recolored, 0.86)
    result = Image.composite(painted, base_image, mask)
    return ImageEnhance.Contrast(result).enhance(1.02)


def _mask_coverage(mask) -> int:
    return sum(value * count for value, count in enumerate(mask.histogram()))


def _build_detected_area_index(detected_areas: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    areas_map: Dict[str, List[Dict[str, Any]]] = {}
    for area in detected_areas:
        if not isinstance(area, dict):
            continue
        raw_area_id = area.get("id") or area.get("area_id") or area.get("type")
        for area_id in _area_lookup_keys(raw_area_id):
            areas_map.setdefault(area_id, []).append(area)
    return areas_map


def _matching_detected_areas(
    area_id: Any,
    areas_map: Dict[str, List[Dict[str, Any]]],
) -> Tuple[str, List[Dict[str, Any]]]:
    search_keys = _area_lookup_keys(area_id)
    search_key = search_keys[0] if search_keys else _normalize_area_id(area_id)
    for key in search_keys:
        matching_areas = areas_map.get(key, [])
        if matching_areas:
            return key, matching_areas
    return search_key, []


def build_layer_masks(
    image,
    paint_areas: Dict[str, str],
    detected_areas: List[Dict[str, Any]],
    project_type: str = "interior",
    sam_session=None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Turn Gemini hints into cleaned, priority-aware masks using standardized pipeline.
    Uses MaskPipeline to prevent spillover to sky/ground and ensure accurate layer boundaries.
    """
    pil = _load_pil()
    if pil is None:
        return [], {"used_sam": False, "detected_area_ids": []}
    Image, ImageChops, _, _, ImageFilter, _ = pil
    width, height = image.size
    areas_map = _build_detected_area_index(detected_areas)
    layers = []
    used_sam = False
    skipped_area_ids = []
    layers_debug = []

    for area_id, hex_color in paint_areas.items():
        search_key, matching_areas = _matching_detected_areas(area_id, areas_map)
        if not matching_areas:
            skipped_area_ids.append(search_key)
            continue

        layer_type = normalize_layer_type(matching_areas[0].get("type"), search_key)
        priority = get_layer_priority(layer_type, search_key, matching_areas[0].get("priority"))

        for idx, area in enumerate(matching_areas, start=1):
            box = _normalize_box(area.get("box_2d") or area.get("box2d"), width, height)
            if not box:
                continue
            instance_type = normalize_layer_type(area.get("type"), search_key)
            instance_priority = get_layer_priority(instance_type, search_key, area.get("priority"))
            polygon = _normalize_polygon(
                area.get("polygon_2d") or area.get("polygon2d") or area.get("polygon"),
                width,
                height,
            )
            seed_points = _normalize_seed_points(
                area.get("seed_points_2d")
                or area.get("seedPoints2d")
                or area.get("seed_points")
                or area.get("seedPoints"),
                width,
                height,
            )
            
            # ✅ Use standardized MaskPipeline
            pipeline = MaskPipeline(
                image, box, polygon, search_key,
                project_type=project_type,
                sam_session=sam_session
            )
            area_mask, pipeline_meta = pipeline.build().get_result()
            
            if area_mask is None or not area_mask.getbbox():
                skipped_area_ids.append(search_key)
                continue
            
            # Track SAM usage
            used_sam = used_sam or (pipeline_meta.get("pipeline_source") == "sam")
            
            instance_id = search_key if len(matching_areas) == 1 else f"{search_key}-{idx:02d}"
            layers.append({
                "id": instance_id,
                "group_id": search_key,
                "type": instance_type,
                "priority": instance_priority,
                "color": hex_color,
                "mask": area_mask,
                "area": _mask_area(area_mask),
                "bbox": _mask_bbox_list(area_mask),
            })
            
            layers_debug.append({
                "id": instance_id,
                "pipeline_metadata": pipeline_meta
            })

        if not any(layer.get("group_id", layer["id"]) == search_key for layer in layers):
            skipped_area_ids.append(search_key)

    resolved_layers = resolve_mask_overlap(layers)
    meta = {
        "used_sam": used_sam,
        "project_type": project_type,
        "skipped_area_ids": skipped_area_ids,
        "detected_area_ids": sorted(areas_map.keys()),
        "layers_debug": layers_debug,  # ← For troubleshooting
    }
    return resolved_layers, meta


def resolve_mask_overlap(layers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Let higher-priority, usually smaller detail masks win overlaps."""
    if not layers:
        return []
    pil = _load_pil()
    Image, ImageChops, _, _, ImageFilter, _ = pil
    resolved = []
    higher_priority_coverage = Image.new("L", layers[0]["mask"].size, 0)

    for layer in sorted(layers, key=lambda item: (item["priority"], -item["area"]), reverse=True):
        mask = _subtract_mask(layer["mask"], higher_priority_coverage)
        mask = mask.filter(ImageFilter.GaussianBlur(0.3))
        if not mask.getbbox():
            continue
        layer = dict(layer)
        layer["mask"] = mask
        layer["area"] = _mask_area(mask)
        layer["bbox"] = _mask_bbox_list(mask)
        resolved.append(layer)
        higher_priority_coverage = ImageChops.lighter(
            higher_priority_coverage,
            mask.point(lambda p: 255 if p > 8 else 0),
        )

    return sorted(resolved, key=lambda item: (item["priority"], item["area"]))


def apply_paint_color_ai(
    image_base64: str,
    paint_areas: Dict[str, str],
    detected_areas: List[Dict[str, Any]],
    project_type: str,
) -> str:
    """Apply selected colors to AI-detected paintable areas."""
    try:
        pil = _load_pil()
        if pil is None:
            return image_base64
        Image, _, _, ImageEnhance, _, _ = pil

        working_image = _decode_image(image_base64)
        if working_image is None or not paint_areas or not detected_areas:
            return image_base64

        result_image = working_image.copy()
        sam_session = None
        try:
            from sam_segmenter import create_session

            sam_session = create_session(result_image)
        except Exception:
            sam_session = None

        layers, _ = build_layer_masks(
            result_image, paint_areas, detected_areas,
            project_type=project_type,  # ← Pass project_type
            sam_session=sam_session
        )
        for layer in layers:
            result_image = _paint_with_mask(result_image, hex_to_rgb(layer["color"]), layer["mask"])

        return _encode_image(ImageEnhance.Contrast(result_image).enhance(1.03))
    except Exception as e:
        print(f"apply_paint_color_ai error: {e}")
        return image_base64


def apply_paint_color_ai_with_meta(
    image_base64: str,
    paint_areas: Dict[str, str],
    detected_areas: List[Dict[str, Any]],
    project_type: str,
) -> Tuple[str, Dict[str, Any]]:
    """Apply paint and return debug metadata used by the API response."""
    pil = _load_pil()
    if pil is None:
        return image_base64, {"painted_pixels": 0, "reason": "pillow_unavailable"}
    Image, _, _, ImageEnhance, _, _ = pil

    working_image = _decode_image(image_base64)
    if working_image is None or not paint_areas or not detected_areas:
        return image_base64, {"painted_pixels": 0, "reason": "missing_image_or_inputs"}

    result_image = working_image.copy()
    total_coverage = 0
    painted_area_ids = []
    sam_session = None
    try:
        from sam_segmenter import create_session

        sam_session = create_session(result_image)
    except Exception:
        sam_session = None

    layers, layer_meta = build_layer_masks(
        result_image, paint_areas, detected_areas,
        project_type=project_type,  # ← Pass project_type to pipeline
        sam_session=sam_session
    )
    layer_debug = []
    for layer in layers:
        coverage = _mask_coverage(layer["mask"])
        if layer["mask"].getbbox() and coverage > 0:
            total_coverage += coverage
            painted_area_ids.append(layer["id"])
            layer_debug.append({
                "id": layer["id"],
                "type": layer["type"],
                "priority": layer["priority"],
                "area": layer["area"],
                "bbox": layer["bbox"],
            })
            result_image = _paint_with_mask(result_image, hex_to_rgb(layer["color"]), layer["mask"])

    changed = result_image.tobytes() != working_image.tobytes()
    meta = {
        "painted_pixels": total_coverage,
        "changed": changed,
        "painted_area_ids": painted_area_ids,
        "skipped_area_ids": layer_meta["skipped_area_ids"],
        "paint_area_ids": [_area_exact_id(area_id) for area_id in paint_areas.keys()],
        "detected_area_ids": layer_meta["detected_area_ids"],
        "used_sam": layer_meta["used_sam"],
        "layers": layer_debug,
    }
    return _encode_image(ImageEnhance.Contrast(result_image).enhance(1.03)), meta


def apply_paint_color_advanced(image_base64: str, paint_areas: Dict[str, str], project_type: str) -> str:
    """Legacy fallback kept for manual diagnostics only."""
    try:
        pil = _load_pil()
        if pil is None:
            return image_base64
        Image, _, ImageDraw, _, ImageFilter, _ = pil
        working_image = _decode_image(image_base64)
        if working_image is None or not paint_areas:
            return image_base64

        width, height = working_image.size
        result_image = working_image.copy()
        primary_rgb = hex_to_rgb(next(iter(paint_areas.values())))
        wall_start, wall_end = int(height * 0.25), int(height * 0.90)
        mask = Image.new("L", result_image.size, 0)
        ImageDraw.Draw(mask).rectangle([0, wall_start, width, wall_end], fill=100)
        mask = mask.filter(ImageFilter.GaussianBlur(1.2))
        return _encode_image(_paint_with_mask(result_image, primary_rgb, mask))
    except Exception as e:
        print(f"apply_paint_color_advanced error: {e}")
        return image_base64
