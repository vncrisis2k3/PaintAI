import base64
import colorsys
import io
import os
from typing import Any, Dict, List, Optional, Tuple

import requests
from PIL import Image


SUPPORTED_AI_IMAGE_PROVIDERS = {"openai", "gpt-image", "gemini", "nano-banana"}


def normalize_ai_image_provider(value: Optional[str]) -> str:
    provider = (value or os.environ.get("AI_IMAGE_PROVIDER") or "local").strip().lower()
    if provider in {"gpt", "gpt-image-1"}:
        return "openai"
    if provider in {"nano_banana", "nanobanana", "google"}:
        return "gemini"
    return provider


def is_external_ai_image_provider(provider: Optional[str]) -> bool:
    return normalize_ai_image_provider(provider) in SUPPORTED_AI_IMAGE_PROVIDERS


def _request_timeout() -> int:
    raw_timeout = os.environ.get("AI_IMAGE_REQUEST_TIMEOUT_SECONDS", "90")
    try:
        timeout = int(raw_timeout)
    except (TypeError, ValueError):
        timeout = 90
    return max(10, min(timeout, 180))


def _split_data_url(image_data: str) -> Tuple[str, str]:
    if "," not in image_data:
        return "image/png", image_data

    header, data = image_data.split(",", 1)
    mime_type = "image/png"
    if header.startswith("data:") and ";" in header:
        mime_type = header.split(";", 1)[0].replace("data:", "") or mime_type
    return mime_type, data


def _image_bytes_as_png(image_data: str) -> bytes:
    _, base64_data = _split_data_url(image_data)
    raw = base64.b64decode(base64_data)
    with Image.open(io.BytesIO(raw)) as image:
        output = io.BytesIO()
        image.convert("RGBA").save(output, format="PNG", optimize=True)
        return output.getvalue()


def _as_png_data_url(image_base64: str) -> str:
    return f"data:image/png;base64,{image_base64}"


def _gemini_image_model() -> str:
    model = (os.environ.get("GEMINI_IMAGE_MODEL") or "gemini-2.5-flash-image").strip()
    if model.startswith("models/"):
        model = model.split("/", 1)[1]
    if model.startswith("AIza") or "://" in model or "/" in model:
        return "gemini-2.5-flash-image"
    return model or "gemini-2.5-flash-image"


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    value = (hex_color or "").strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Invalid HEX color: {hex_color}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def hex_to_architectural_color_name(hex_color: str) -> str:
    """Convert a HEX paint color to a stable English architectural color name."""
    r, g, b = _hex_to_rgb(hex_color)
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    hue = h * 360

    if l >= 0.94 and s <= 0.12:
        return "soft warm white" if hue < 75 or hue >= 345 else "clean neutral white"
    if l <= 0.16 and s <= 0.22:
        return "charcoal black"
    if s <= 0.10:
        if l >= 0.82:
            return "light warm gray"
        if l >= 0.58:
            return "architectural greige"
        if l >= 0.34:
            return "medium neutral gray"
        return "deep graphite gray"

    light_prefix = "pale" if l >= 0.82 else "soft" if l >= 0.64 else "deep" if l <= 0.34 else "muted"

    if hue < 18 or hue >= 345:
        return f"{light_prefix} terracotta red" if l < 0.7 else "blush clay"
    if hue < 42:
        if s < 0.45 and l >= 0.48:
            return f"{light_prefix} warm beige"
        return f"{light_prefix} warm taupe" if s < 0.35 else f"{light_prefix} burnt orange"
    if hue < 72:
        if l >= 0.78:
            return "creamy beige"
        return f"{light_prefix} ochre beige"
    if hue < 105:
        return f"{light_prefix} olive green"
    if hue < 155:
        return f"{light_prefix} sage green"
    if hue < 195:
        return f"{light_prefix} blue green"
    if hue < 245:
        return f"{light_prefix} slate blue"
    if hue < 285:
        return f"{light_prefix} lavender gray"
    if hue < 330:
        return f"{light_prefix} mauve"
    return f"{light_prefix} rose taupe"


def _area_display_name(area_id: str, detected_areas: Optional[List[Dict[str, Any]]]) -> str:
    for area in detected_areas or []:
        if not isinstance(area, dict):
            continue
        if str(area.get("id") or "") == area_id:
            return str(area.get("displayLabel") or area.get("label") or area.get("name") or area_id)
    return area_id


def _build_color_spec(paint_areas: Dict[str, str], detected_areas: Optional[List[Dict[str, Any]]]) -> str:
    lines = []
    for area_id, hex_color in paint_areas.items():
        color_name = hex_to_architectural_color_name(hex_color)
        area_name = _area_display_name(area_id, detected_areas)
        lines.append(f"- {area_id} ({area_name}): {color_name}, exact paint HEX {hex_color}")
    return "\n".join(lines)


def _paint_prompt(project_type: str, paint_areas: Dict[str, str], detected_areas: Optional[List[Dict[str, Any]]]) -> str:
    colors = _build_color_spec(paint_areas, detected_areas)
    areas = []
    for area in detected_areas or []:
        if not isinstance(area, dict):
            continue
        area_id = area.get("id") or area.get("type") or "paintable-area"
        label = area.get("displayLabel") or area.get("label") or area_id
        box = area.get("box_2d") or area.get("bbox")
        if box:
            areas.append(f"- {area_id}: {label}; normalized box {box}")
        else:
            areas.append(f"- {area_id}: {label}")
    area_hint = "\n".join(areas[:20]) if areas else "Use the visible architectural paintable surfaces that match the area ids."

    return (
        "You are an architectural paint visualization engine. Edit the provided architectural photo into a realistic paint color preview.\n"
        f"Scene type: {project_type} architecture.\n\n"
        "Paint schedule. Use the English color name for natural material interpretation, but match the exact HEX tone as closely as possible:\n"
        f"{colors}\n\n"
        "Target architectural elements:\n"
        f"{area_hint}\n\n"
        "Strict editing rules:\n"
        "- Repaint only the requested architectural surfaces.\n"
        "- Preserve the original camera angle, composition, structure, proportions, openings, trims, edges, material texture, lighting, shadows, and reflections.\n"
        "- Do not repaint glass, doors, furniture, plants, roof tiles, sky, floor, ground, pavement, lamps, signs, people, vehicles, or decor unless explicitly listed.\n"
        "- Do not redesign the building, add objects, remove objects, change geometry, change camera, or stylize the image.\n"
        "- Keep the output photorealistic, like a professional paint manufacturer color preview."
    )


def edit_image_with_ai_provider(
    *,
    provider: str,
    image: str,
    project_type: str,
    paint_areas: Dict[str, str],
    detected_areas: Optional[List[Dict[str, Any]]] = None,
    api_key: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    normalized_provider = normalize_ai_image_provider(provider)
    prompt = _paint_prompt(project_type, paint_areas, detected_areas)

    if normalized_provider in {"openai", "gpt-image"}:
        return _edit_with_openai(image, prompt, api_key)
    if normalized_provider in {"gemini", "nano-banana"}:
        return _edit_with_gemini(image, prompt, api_key)

    raise ValueError(f"Unsupported AI image provider: {provider}")


def _edit_with_openai(image: str, prompt: str, api_key: Optional[str]) -> Tuple[str, Dict[str, Any]]:
    resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not resolved_key:
        raise ValueError("OPENAI_API_KEY is required for provider=openai")

    png_bytes = _image_bytes_as_png(image)
    model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
    size = os.environ.get("OPENAI_IMAGE_SIZE", "1024x1024")
    quality = os.environ.get("OPENAI_IMAGE_QUALITY", "medium")

    response = requests.post(
        "https://api.openai.com/v1/images/edits",
        headers={"Authorization": f"Bearer {resolved_key}"},
        data={
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "n": "1",
        },
        files={"image": ("input.png", png_bytes, "image/png")},
        timeout=_request_timeout(),
    )
    response.raise_for_status()
    data = response.json()
    first = (data.get("data") or [{}])[0]
    image_base64 = first.get("b64_json")
    if image_base64:
        return _as_png_data_url(image_base64), {"provider": "openai", "model": model}

    image_url = first.get("url")
    if image_url:
        image_response = requests.get(image_url, timeout=_request_timeout())
        image_response.raise_for_status()
        return _as_png_data_url(base64.b64encode(image_response.content).decode("ascii")), {
            "provider": "openai",
            "model": model,
        }

    raise ValueError("OpenAI image edit response did not contain an image")


def _edit_with_gemini(image: str, prompt: str, api_key: Optional[str]) -> Tuple[str, Dict[str, Any]]:
    resolved_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not resolved_key:
        raise ValueError("GEMINI_API_KEY is required for provider=gemini/nano-banana")

    mime_type, base64_data = _split_data_url(image)
    model = _gemini_image_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    response = requests.post(
        url,
        headers={
            "x-goog-api-key": resolved_key,
            "Content-Type": "application/json",
        },
        json={
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inlineData": {"mimeType": mime_type, "data": base64_data}},
                    ]
                }
            ],
            "generationConfig": {"responseModalities": ["Image"]},
        },
        timeout=_request_timeout(),
    )
    response.raise_for_status()
    data = response.json()
    for candidate in data.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            inline_data = part.get("inlineData") or part.get("inline_data")
            if inline_data and inline_data.get("data"):
                return _as_png_data_url(inline_data["data"]), {"provider": "gemini", "model": model}

    raise ValueError("Gemini image response did not contain an image")
