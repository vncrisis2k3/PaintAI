import os
import sys
from pathlib import Path

# Add parent directory to path to import server module
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Import the existing app
from server import app as existing_app

# Re-export the app for Vercel
app = existing_app
