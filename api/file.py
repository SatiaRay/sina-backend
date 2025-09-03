from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from typing import List
import os
from uuid import uuid4
import mimetypes

router = APIRouter(prefix="/files", tags=["files"])

UPLOAD_DIR = os.path.join(os.getcwd(), "storage/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", summary="Upload one or multiple files")
async def upload_files(files: List[UploadFile] = File(...)):
    result = []
    for file in files:
        filename = file.filename if file.filename is not None else f"{uuid4().hex}"
        ext = os.path.splitext(filename)[1]
        unique_name = f"{uuid4().hex}{ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)
        with open(file_path, "wb") as f:
            content = await file.read()
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

