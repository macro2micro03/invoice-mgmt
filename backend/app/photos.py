import uuid
from pathlib import Path

from . import config


def save_photo(image_bytes: bytes, original_filename: str) -> str:
    ext = Path(original_filename).suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = config.PHOTOS_DIR / filename
    dest.write_bytes(image_bytes)
    return str(dest.relative_to(config.STORAGE_DIR)).replace("\\", "/")
