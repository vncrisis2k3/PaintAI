import base64
import io

from PIL import Image

from ai_image_provider import (
    _gemini_image_model,
    _image_bytes_as_png,
    _paint_prompt,
    hex_to_architectural_color_name,
    normalize_ai_image_provider,
)


def _tiny_png_data_url():
    image = Image.new("RGB", (1, 1), "#ffffff")
    output = io.BytesIO()
    image.save(output, format="PNG")
    data = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{data}"


def test_normalize_ai_image_provider_aliases():
    assert normalize_ai_image_provider("gpt-image-1") == "openai"
    assert normalize_ai_image_provider("nano_banana") == "gemini"
    assert normalize_ai_image_provider("local") == "local"


def test_gemini_image_model_falls_back_when_env_contains_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_IMAGE_MODEL", "AIza-not-a-model")

    assert _gemini_image_model() == "gemini-2.5-flash-image"


def test_image_bytes_as_png_decodes_data_url():
    png_bytes = _image_bytes_as_png(_tiny_png_data_url())

    assert png_bytes.startswith(b"\x89PNG")


def test_hex_to_architectural_color_name_maps_beige():
    assert hex_to_architectural_color_name("#C8B08A") == "soft warm beige"


def test_paint_prompt_contains_colors_and_preservation_rules():
    prompt = _paint_prompt(
        "exterior",
        {"wall-main": "#C8B08A", "trim": "#222222"},
        [{"id": "wall-main", "label": "main exterior facade wall", "box_2d": [100, 100, 900, 900]}],
    )

    assert "wall-main (main exterior facade wall): soft warm beige, exact paint HEX #C8B08A" in prompt
    assert "trim (trim): charcoal black, exact paint HEX #222222" in prompt
    assert "Preserve the original camera angle" in prompt
