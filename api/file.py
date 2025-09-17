from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from typing import List
import os
from uuid import uuid4
import mimetypes
import magic  # Add this import

router = APIRouter(prefix="/files", tags=["files"])

UPLOAD_DIR = os.path.join(os.getcwd(), "storage/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", summary="Upload one or multiple files")
async def upload_files(files: List[UploadFile] = File(...)):
    result = []
    # Define allowed content types and max file size (in bytes)
    ALLOWED_CONTENT_TYPES = [
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "application/pdf",
        "text/plain",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    for file in files:
        # Validate content type (browser-provided)
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' has disallowed content type: {file.content_type}",
            )

        filename = file.filename if file.filename is not None else f"{uuid4().hex}"
        ext = os.path.splitext(filename)[1]
        unique_name = f"{uuid4().hex}{ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)
        content = await file.read()
        # Validate file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File '{filename}' exceeds the maximum allowed size of {MAX_FILE_SIZE // (1024 * 1024)} MB.",
            )
        # Detect true MIME type using python-magic
        detected_type = magic.from_buffer(content, mime=True)
        if detected_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"File '{filename}' content does not match allowed types. Detected: {detected_type}",
            )
        with open(file_path, "wb") as f:
            f.write(content)
        url = f"/files/{unique_name}"
        result.append({"filename": filename, "storage_path": file_path, "url": url})
    return {"files": result}


@router.get("/{filename}", summary="Serve uploaded file by filename")
async def get_uploaded_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Guess content type; fallback to image/jpeg if unknown
    media_type, _ = mimetypes.guess_type(file_path)
    if media_type is None:
        media_type = "application/octet-stream"

    return FileResponse(path=file_path, media_type=media_type, filename=filename)
