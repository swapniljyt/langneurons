import sys
import os

# Append root directory and backend directory to path so imports work correctly
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, "backend"))

# Import the FastAPI app instance from frontend.server
from frontend.server import app
