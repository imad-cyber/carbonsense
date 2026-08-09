"""
Vercel serverless entry for CarbonSense FastAPI backend.
"""
import sys
import traceback
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from mangum import Mangum

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Top-level `app` required by @vercel/python static analysis
app: FastAPI = FastAPI(title="CarbonSense")

try:
    from app.main import app as _fastapi_app

    app = _fastapi_app
except Exception:
    _boot_trace = traceback.format_exc()

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def _boot_error(path: str = ""):
        return PlainTextResponse(
            f"CarbonSense failed to boot:\n\n{_boot_trace}",
            status_code=500,
        )

handler = Mangum(app, lifespan="off")
