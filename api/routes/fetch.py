from fastapi import APIRouter, HTTPException # type: ignore
from pathlib import Path
import logging
from typing import Optional

from agents.fetch_agent import fetch_latest
from api.schemas import SimpleResponse

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parents[2]  # project root


@router.post("/", response_model=SimpleResponse)
def fetch_endpoint(raw_dir: Optional[str] = None):
    """
    Download latest HTS CSV into <project_root>/data/raw by default.
    Download latest HTS CSV into <project_root>/data/raw by default.
    Optional: provide raw_dir (absolute or relative) to override target folder.
    """
    try:
        raw_dir_path = Path(raw_dir) if raw_dir else BASE_DIR / "data" / "raw"
        raw_dir_path.mkdir(parents=True, exist_ok=True)
        downloaded = fetch_latest(raw_dir_path)
        return {"message": "Fetched latest HTS CSV", "path": str(downloaded)}
    except Exception as exc:
        logging.exception("Error in fetch_endpoint")
        raise HTTPException(status_code=500, detail=str(exc))
