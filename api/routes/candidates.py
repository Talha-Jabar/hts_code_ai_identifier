from fastapi import APIRouter, HTTPException, Form
from pathlib import Path
import logging
from typing import List, Dict, Any

from agents.query_agent import QueryAgent
from api.schemas import CandidatesResponse

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_PROCESSED = BASE_DIR / "data" / "processed" / "hts_processed.csv"


@router.post("/", response_model=CandidatesResponse)
def candidates_endpoint(
    kind: str = Form("prefix", description="Search kind: 'prefix' or 'product'"),
    query: str = Form(..., description="Prefix digits (4/6) or product description"),
    top_k: int = Form(10, description="Number of candidates to return"),
    processed_csv: str = Form(None)
):
    """
    Return candidate HTS rows either by prefix or by product description (vector search).
    """
    try:
        processed = Path(processed_csv) if processed_csv else DEFAULT_PROCESSED
        if not processed.exists():
            raise FileNotFoundError(f"Processed CSV not found at {processed}")

        qa_agent = QueryAgent(str(processed))
        candidates: List[Dict[str, Any]] = []

        if kind.lower() == "prefix":
            df = qa_agent.get_candidates_by_prefix(query.strip())
            if df is None or df.empty:
                candidates = []
            else:
                for _, row in df.head(top_k).iterrows():
                    candidates.append(qa_agent.get_candidate_details(row))

        elif kind.lower() in ("product", "desc", "description", "fuzzy"):
            df = qa_agent.get_candidates_by_product(query.strip(), k=top_k)
            if df is None or df.empty:
                candidates = []
            else:
                for _, row in df.head(top_k).iterrows():
                    candidates.append(qa_agent.get_candidate_details(row))
        else:
            raise ValueError("Unsupported kind. Use 'prefix' or 'product'.")

        return {"query": query, "kind": kind, "top_k": top_k, "candidates": candidates}
    except Exception as exc:
        logging.exception("Error in candidates_endpoint")
        raise HTTPException(status_code=500, detail=str(exc))
