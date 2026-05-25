# Segment Anything (SAM) Setup

SAM is optional. When it is installed and configured, the backend uses SAM to
create pixel-level masks from Gemini's `box_2d` / `polygon_2d` regions. When it
is missing, the app falls back to the internal Pillow segmentation path.

Install:

```bash
pip install torch torchvision
pip install git+https://github.com/facebookresearch/segment-anything.git
```

Configure `.env`:

```env
SAM_CHECKPOINT=models/sam_vit_b_01ec64.pth
SAM_MODEL_TYPE=vit_b
SAM_DEVICE=cpu
```

Use `SAM_DEVICE=cuda` when CUDA is available.

Check status:

```http
GET /api/ai/sam-status
```

Expected ready response:

```json
{
  "success": true,
  "sam_available": true,
  "model_type": "vit_b",
  "device": "cpu",
  "checkpoint_configured": true
}
```
