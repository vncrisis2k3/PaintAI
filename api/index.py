import os
import sys
from pathlib import Path

# Add parent directory to path to import server module
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Import the existing app
from server import app as existing_app

# Re-export the app for Vercel
app = existing_app

# Mount static files
static_path = parent_dir / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Serve index.html at root
@app.get("/")
async def root():
    from fastapi.responses import FileResponse
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "PaintAI API is running"}
