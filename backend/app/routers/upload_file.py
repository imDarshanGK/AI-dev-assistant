from fastapi import UploadFile, APIRouter, HTTPException, status
import logging

from ..utils.upload_config import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    BLOCKED_EXTENSIONS,
    max_file_size,
)
from ..utils.file_validator import validate_file

router = APIRouter(
    tags=['Upload Files']
)


@router.get('/')
def index_upload():
    return {
        "max_file_size_MB": f"{ max_file_size / (1024 * 1024):.2f} MB",
        "blocked_extensions": BLOCKED_EXTENSIONS,
        "allowed_extensions": ALLOWED_EXTENSIONS,
        "allowed_mime_types": ALLOWED_MIME_TYPES
    }


@router.post('/validate')
async def upload_file(file: UploadFile):

    if file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded"
        )
    filename = file.filename
    logger = logging.getLogger(__name__)
    filecontent = await file.read()
    logger.debug("Received upload: %s (%d bytes)", filename, len(filecontent))
    filesize = len(filecontent)

    # Validate max size
    if filesize > max_file_size:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File size should not exceed {max_file_size / (1024 * 1024)} MB"
        )

    try:
        detected_mime = validate_file(
            filename=filename,
            filecontent=filecontent
        )

        return {
            "success": True,
            "filename": filename,
            "content_type": detected_mime,
            "size": f'{filesize/1024:.2f} KB'
            # "content": filecontent.decode('utf-8', errors='ignore')
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(e)
        )
