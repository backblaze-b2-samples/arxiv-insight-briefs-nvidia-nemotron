"""File-browser HTTP routes — list, get, delete, download, metadata.

Restored from the starter per user request after first-run smoke test;
intentionally unguarded so the user can inspect/delete anything in the
configured B2 prefix, including cached `papers/` PDFs.

Layer rule: no boto3 here, only calls into `app.service.files` /
`app.service.metadata`. Object keys arrive URL-encoded in the path; we
let FastAPI's `{key:path}` converter decode them before validation.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.service import metadata as metadata_svc
from app.service.files import (
    FileKeyError,
    FileNotFoundError,
    get_download_url,
    get_file,
    list_files,
    remove_file,
)
from app.types import FileMetadata, FileMetadataDetail

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/files", response_model=list[FileMetadata])
async def list_files_endpoint(prefix: str = "", limit: int = 100):
    try:
        return list_files(prefix=prefix, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/files/{key:path}/download")
async def download_file_endpoint(key: str):
    """302 to a short-lived presigned GET URL — preserves the starter's
    redirect contract so links can be shared without a JSON round-trip."""
    try:
        url = get_download_url(key)
    except FileKeyError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None
    return RedirectResponse(url=url, status_code=302)


@router.get("/files/{key:path}/metadata", response_model=FileMetadataDetail)
async def get_metadata_endpoint(key: str):
    try:
        return metadata_svc.get_metadata(key)
    except FileKeyError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


@router.get("/files/{key:path}", response_model=FileMetadata)
async def get_file_endpoint(key: str):
    try:
        return get_file(key)
    except FileKeyError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


@router.delete("/files/{key:path}")
async def delete_file_endpoint(key: str):
    """Full CRUD, no guard: deletes the object outright. The user explicitly
    chose this behavior — even `papers/` cache entries can be removed here."""
    try:
        remove_file(key)
    except FileKeyError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Failed to delete file") from None
    logger.info("File deleted: key=%s", key)
    return {"deleted": True, "key": key}
