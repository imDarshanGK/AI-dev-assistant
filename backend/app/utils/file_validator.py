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

def validate_file_extension(filename: str) -> str:
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

def validate_mime_type(ext: str, filecontent: bytes) -> str:
    detected_mime = detect_mime_type(filecontent)
    logger = logging.getLogger(__name__)
    logger.debug("Detected MIME Type: %s", detected_mime)
    
    if detected_mime not in ALLOWED_MIME_TYPES[ext]:
        raise ValueError(
            f"{UPLOAD_ERROR_MESSAGES['invalid_mime']} "
            f"Detected MIME Type: {detected_mime}"
        )
    return detected_mime

def is_disguised_binary(filecontent: bytes) -> bool:
    """
    Light inspection to catch disguised binaries.
    Text-based source code files should not contain null bytes (\\x00).
    We check the first 1024 bytes for performance.
    """
    chunk = filecontent[:1024]
    return b'\x00' in chunk

def validate_file(filename: str, filecontent: bytes) -> str:
    # 1. Validate Extension
    ext = validate_file_extension(filename)
    
    # 2. Validate MIME Type via python-magic
    mime_type = validate_mime_type(ext=ext, filecontent=filecontent)

    # 3. Light inspection to catch disguised binaries
    if is_disguised_binary(filecontent):
        # Using a fallback string in case "disguised_binary" isn't in their config yet
        error_msg = UPLOAD_ERROR_MESSAGES.get(
            "disguised_binary", 
            "Upload rejected: File contains binary data but claims to be standard text/code."
        )
        raise ValueError(error_msg)

    return mime_type