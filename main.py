"""Entry point: start the Chat-DB API server.

Usage:
    python main.py          # http://0.0.0.0:8000

Equivalent to:
    cd src && uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
"""

import sys
from pathlib import Path

# Ensure src/ is on sys.path so `from api.main import app` works.
sys.path.insert(0, str(Path(__file__).parent / "src"))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8002, reload=True)
