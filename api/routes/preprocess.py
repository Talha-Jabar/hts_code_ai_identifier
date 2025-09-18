from fastapi import APIRouter, HTTPException, Form # type: ignore
from pathlib import Path
import logging

from agents.preprocess_agent import preprocess
from api.schemas import SimpleResponse

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parents[2]


@router.post("/", response_model=SimpleResponse)
def preprocess_endpoint(
    raw_csv_path: str = Form(None, description="Path to raw CSV file. If omitted, default data/raw/hts_latest.csv is used."),
    processed_dir: str = Form(None, description="Directory to write processed CSV. Defaults to data/processed.")
):
    """
    Preprocess a raw HTS CSV into a structured processed CSV.
    """
    try:
        raw = Path(raw_csv_path) if raw_csv_path else BASE_DIR / "data" / "raw" / "hts_latest.csv"
        processed_dir_path = Path(processed_dir) if processed_dir else BASE_DIR / "data" / "processed"
        if not raw.exists():
            raise FileNotFoundError(f"Raw CSV not found at {raw}")
        processed_path = preprocess(raw, processed_dir_path)
        return {"message": "Preprocessing completed", "path": str(processed_path)}
    except Exception as exc:
        logging.exception("Error in preprocess_endpoint")
        raise HTTPException(status_code=500, detail=str(exc))
