import os
import sys
from pathlib import Path

# Automatically inject the workspace root into sys.path to support execution from any directory
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.langtrace.cli import main

if __name__ == "__main__":
    main()
