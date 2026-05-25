"""
Optional Segment Anything integration.

Set these environment variables to enable SAM:
- SAM_CHECKPOINT: path to a SAM checkpoint file, e.g. models/sam_vit_b_01ec64.pth
- SAM_MODEL_TYPE: vit_b, vit_l, or vit_h. Defaults to vit_b.
- SAM_DEVICE: cpu or cuda. Defaults to cuda when available, otherwise cpu.

The application keeps working without SAM installed; callers receive None and
can fall back to the lightweight Pillow segmentation path.
"""

import os
from pathlib import Path
from functools import lru_cache
from typing import Optional, Tuple

APP_ROOT = Path(__file__).resolve().parent
DEFAULT_CHECKPOINT = APP_ROOT / "models" / "sam_vit_b_01ec64.pth"


def _get_checkpoint_path() -> Optional[str]:
    checkpoint = os.environ.get("SAM_CHECKPOINT")
    if checkpoint:
        path = Path(checkpoint)
        if not path.is_absolute():
            path = APP_ROOT / path
        return str(path)
    if DEFAULT_CHECKPOINT.exists():
        return str(DEFAULT_CHECKPOINT)
    return None


def _load_optional_sam():
    try:
        import numpy as np
        import torch
        from PIL import Image, ImageChops, ImageFilter
        from segment_anything import SamAutomaticMaskGenerator, SamPredictor, sam_model_registry

        return np, torch, Image, ImageChops, ImageFilter, SamPredictor, SamAutomaticMaskGenerator, sam_model_registry
    except Exception:
        return None


@lru_cache(maxsize=1)
def _get_predictor():
    checkpoint = _get_checkpoint_path()
    if not checkpoint or not os.path.exists(checkpoint):
        return None

    loaded = _load_optional_sam()
    if loaded is None:
        return None

    np, torch, _, _, _, SamPredictor, _, sam_model_registry = loaded
    model_type = os.environ.get("SAM_MODEL_TYPE", "vit_b")
    if model_type not in sam_model_registry:
        return None

    device = os.environ.get("SAM_DEVICE")
    if not device:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    sam = sam_model_registry[model_type](checkpoint=checkpoint)
    sam.to(device=device)
    return SamPredictor(sam)


def is_sam_available() -> bool:
    return _get_predictor() is not None


def predict_mask(image, box: Tuple[int, int, int, int], shape_mask=None, seed_points=None) -> Optional[object]:
    """Return a PIL L mask from SAM, or None when SAM is unavailable/fails."""
    checkpoint = _get_checkpoint_path()
    if not checkpoint or not os.path.exists(checkpoint):
        return None

    predictor = _get_predictor()
    loaded = _load_optional_sam()
    if loaded is None or predictor is None:
        return None

    np, _, Image, ImageChops, ImageFilter, _, _, _ = loaded
    try:
        rgb_image = image.convert("RGB")
        predictor.set_image(np.array(rgb_image))

        input_box = np.array(box, dtype=np.float32)
        point_coords = np.array(seed_points, dtype=np.float32) if seed_points else None
        point_labels = np.ones((len(seed_points),), dtype=np.int32) if seed_points else None
        masks, scores, _ = predictor.predict(
            point_coords=point_coords,
            point_labels=point_labels,
            box=input_box,
            multimask_output=True,
        )

        if masks is None or len(masks) == 0:
            return None

        best_index = 0
        best_score = -1.0
        for idx, mask in enumerate(masks):
            mask_img = Image.fromarray((mask.astype("uint8") * 255), mode="L")
            if shape_mask is not None:
                clipped = ImageChops.multiply(mask_img, shape_mask)
                overlap = sum(clipped.histogram()[1:])
                area = max(1, sum(mask_img.histogram()[1:]))
                shape_area = max(1, sum(shape_mask.histogram()[1:]))
                score = (overlap / area) * 0.65 + (overlap / shape_area) * 0.35
            else:
                score = float(scores[idx])
            if score > best_score:
                best_score = score
                best_index = idx

        mask_img = Image.fromarray((masks[best_index].astype("uint8") * 255), mode="L")
        if shape_mask is not None:
            mask_img = ImageChops.multiply(mask_img, shape_mask)

        if not mask_img.getbbox():
            return None

        return mask_img.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(0.8))
    except Exception:
        return None


class SamImageSession:
    def __init__(self, image):
        loaded = _load_optional_sam()
        predictor = _get_predictor()
        if loaded is None or predictor is None:
            raise RuntimeError("SAM is not available")
        self.np, _, self.Image, self.ImageChops, self.ImageFilter, _, _, _ = loaded
        self.predictor = predictor
        self.predictor.set_image(self.np.array(image.convert("RGB")))

    def predict_mask(self, box: Tuple[int, int, int, int], shape_mask=None, seed_points=None) -> Optional[object]:
        try:
            input_box = self.np.array(box, dtype=self.np.float32)
            point_coords = self.np.array(seed_points, dtype=self.np.float32) if seed_points else None
            point_labels = self.np.ones((len(seed_points),), dtype=self.np.int32) if seed_points else None
            masks, scores, _ = self.predictor.predict(
                point_coords=point_coords,
                point_labels=point_labels,
                box=input_box,
                multimask_output=True,
            )
            if masks is None or len(masks) == 0:
                return None

            best_index = 0
            best_score = -1.0
            for idx, mask in enumerate(masks):
                mask_img = self.Image.fromarray((mask.astype("uint8") * 255), mode="L")
                if shape_mask is not None:
                    clipped = self.ImageChops.multiply(mask_img, shape_mask)
                    overlap = sum(clipped.histogram()[1:])
                    area = max(1, sum(mask_img.histogram()[1:]))
                    shape_area = max(1, sum(shape_mask.histogram()[1:]))
                    score = (overlap / area) * 0.65 + (overlap / shape_area) * 0.35
                else:
                    score = float(scores[idx])
                if score > best_score:
                    best_score = score
                    best_index = idx

            mask_img = self.Image.fromarray((masks[best_index].astype("uint8") * 255), mode="L")
            if shape_mask is not None:
                mask_img = self.ImageChops.multiply(mask_img, shape_mask)
            if not mask_img.getbbox():
                return None
            return mask_img.filter(self.ImageFilter.MedianFilter(5)).filter(self.ImageFilter.GaussianBlur(0.8))
        except Exception:
            return None


def create_session(image) -> Optional[SamImageSession]:
    checkpoint = _get_checkpoint_path()
    if not checkpoint or not os.path.exists(checkpoint):
        return None
    try:
        return SamImageSession(image)
    except Exception:
        return None


def generate_auto_masks(image, max_masks: int = 32):
    """Return PIL L masks from SAM automatic mask generation when available."""
    checkpoint = _get_checkpoint_path()
    if not checkpoint or not os.path.exists(checkpoint):
        return None

    loaded = _load_optional_sam()
    predictor = _get_predictor()
    if loaded is None or predictor is None:
        return None

    np, _, Image, _, ImageFilter, _, SamAutomaticMaskGenerator, _ = loaded
    try:
        generator = SamAutomaticMaskGenerator(
            model=predictor.model,
            points_per_side=24,
            pred_iou_thresh=0.88,
            stability_score_thresh=0.9,
            crop_n_layers=0,
            min_mask_region_area=600,
        )
        rgb_image = image.convert("RGB")
        generated = generator.generate(np.array(rgb_image))
        generated = sorted(
            generated,
            key=lambda item: (item.get("predicted_iou", 0), item.get("area", 0)),
            reverse=True,
        )
        masks = []
        image_area = max(1, rgb_image.size[0] * rgb_image.size[1])
        for item in generated:
            area = int(item.get("area", 0))
            if area < image_area * 0.002 or area > image_area * 0.75:
                continue
            mask = Image.fromarray((item["segmentation"].astype("uint8") * 255), mode="L")
            masks.append(mask.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(0.6)))
            if len(masks) >= max_masks:
                break
        return masks
    except Exception:
        return None
