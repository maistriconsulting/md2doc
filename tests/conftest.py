import os
import sys
from pathlib import Path

# WeasyPrint su Mac con Homebrew: le librerie (pango) stanno in /opt/homebrew/lib
if sys.platform == "darwin" and Path("/opt/homebrew/lib").is_dir():
    os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
