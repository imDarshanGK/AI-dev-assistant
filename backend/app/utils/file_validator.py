from pathlib import Path
import logging
import magic

from .upload_config import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    BLOCKED_EXTENSIONS,
    UPLOAD_ERROR_MESSAGES
    )

def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lower()

def has_double_extension(filename: str) -> bool:
    suffixes = Path(filename).suffixes

    if len(suffixes) <= 1:
        return False

    return any(ext in BLOCKED_EXTENSIONS for ext in suffixes[:-1])

def validate_file_extension(filename: str) -> None:
    extension = get_file_extension(filename)

    if not extension:
        raise ValueError(
            UPLOAD_ERROR_MESSAGES["invalid_extension"]
        )

    if has_double_extension(filename):
        raise ValueError(
            UPLOAD_ERROR_MESSAGES["blocked_file"]
        )

    if extension in BLOCKED_EXTENSIONS:
        raise ValueError(
            UPLOAD_ERROR_MESSAGES["blocked_file"]
        )

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            UPLOAD_ERROR_MESSAGES["invalid_extension"]
        )
    return extension

def detect_mime_type(file_content: bytes) -> str:
    mime = magic.Magic(mime=True)
    return mime.from_buffer(file_content)

def validate_mime_type(ext:str, filecontent:bytes) -> None:
    detected_mime = detect_mime_type(filecontent)
    logger = logging.getLogger(__name__)
    logger.debug("Detected MIME Type: %s", detected_mime)
    if detected_mime not in ALLOWED_MIME_TYPES[ext]:
        raise ValueError(
            f"{UPLOAD_ERROR_MESSAGES['invalid_mime']}"
            f"Detected MIME Type : {detected_mime}"
        )
    return detected_mime

def validate_file(filename: str, filecontent:bytes) -> None:
    ext = validate_file_extension(filename)
    mime_type = validate_mime_type(ext=ext,filecontent=filecontent)

    return mime_type
