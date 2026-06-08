# backend/app/services/thumbnail.py
import base64
import io
import re
from typing import Optional

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

THUMB_SIZE = (320, 180)   # 16:9, suitable for list-view cards
THUMB_FORMAT = "WEBP"     # best size/quality ratio; fall back to JPEG
THUMB_QUALITY = 72


def _b64_to_pil(data_url: str) -> Optional[Image.Image]:
    """Convert a data URL or raw base64 PNG/JPEG to a Pillow Image."""
    match = re.match(r"data:image/[^;]+;base64,(.+)", data_url)
    raw = match.group(1) if match else data_url
    try:
        return Image.open(io.BytesIO(base64.b64decode(raw)))
    except Exception:
        return None


def generate_thumbnail(image_b64: str) -> Optional[str]:
    """
    Downscale an embedded image to THUMB_SIZE.
    Returns a WebP data-URL string, or None on failure.
    """
    if not PIL_AVAILABLE:
        return None
    img = _b64_to_pil(image_b64)
    if img is None:
        return None
    img.thumbnail(THUMB_SIZE, Image.LANCZOS)
    buf = io.BytesIO()
    fmt = THUMB_FORMAT
    try:
        img.save(buf, format=fmt, quality=THUMB_QUALITY)
    except Exception:
        fmt = "JPEG"
        img = img.convert("RGB")
        img.save(buf, format=fmt, quality=THUMB_QUALITY)
    encoded = base64.b64encode(buf.getvalue()).decode()
    mime = "image/webp" if fmt == "WEBP" else "image/jpeg"
    return f"data:{mime};base64,{encoded}"