import sys
import os

# Add parent directory to path so we can import core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.inspector import main

if __name__ == "__main__":
    main()
