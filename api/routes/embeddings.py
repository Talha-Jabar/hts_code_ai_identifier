from fastapi import APIRouter, HTTPException, Form # type: ignore
from pathlib import Path
import logging

from agents.embedding_agent import create_embeddings
from api.schemas import EmbeddingsResponse

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parents[2]


@router.post("/", response_model=EmbeddingsResponse)
def embeddings_endpoint(
    processed_csv_path: str = Form(None, description="Path to processed CSV. Defaults to data/processed/hts_processed.csv."),
    overwrite: bool = Form(False, description="If true, forces re-indexing overwrite.")
):
    """
    Build embeddings from the processed CSV and upload to Qdrant (via existing agent).
    Requires environment variables for OpenAI/Qdrant to be set (same as your project).
    """
    try:
        processed = Path(processed_csv_path) if processed_csv_path else BASE_DIR / "data" / "processed" / "hts_processed.csv"
        if not processed.exists():
            raise FileNotFoundError(f"Processed CSV not found at {processed}")
        indexed_count = create_embeddings(processed, overwrite=overwrite)
        return {"message": "Embeddings created and uploaded", "indexed_count": int(indexed_count)}
    except Exception as exc:
        logging.exception("Error in embeddings_endpoint")
        raise HTTPException(status_code=500, detail=str(exc))
