import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # the source registry uses repo-relative paths (data/pdfs)

needs_pdfs = pytest.mark.skipif(not (ROOT / "data" / "pdfs" / "catechism1.pdf").exists(), reason="source PDFs not present")
needs_v1_store = pytest.mark.skipif(not (ROOT / "chroma_db" / "chroma.sqlite3").exists(), reason="local v1 Chroma store not present")
