from fastapi import UploadFile, APIRouter, HTTPException, status
import mimetypes

from app.utils.file_validator import validate_file
from app.utils.upload_config import max_file_size

router = APIRouter(
    tags=['Upload Files']
)


@router.get('/')
def index_upload():
    return {
        "message": "upload file endpoint"
    }


@router.post('/validate')
async def upload_file(file: UploadFile):

    if file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded"
        )
    
    

    filename = file.filename
    # print(filetype)
    
    
    filecontent = await file.read()
    # print(filecontent)
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
