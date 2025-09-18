from fastapi import APIRouter, HTTPException, Form # type: ignore
from pathlib import Path
import logging
from typing import List, Dict, Any

from agents.query_agent import QueryAgent
from api.schemas import ClassifyResponse

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_PROCESSED = BASE_DIR / "data" / "processed" / "hts_processed.csv"


def _row_to_details(cls_agent: QueryAgent, row) -> Dict[str, Any]:
    """
    Utility to normalize row -> dict using agent helper.
    row may be a pandas Series (from df.iterrows()).
    """
    return cls_agent.get_candidate_details(row)


@router.post("/", response_model=ClassifyResponse)
def classify_endpoint(
    query: str = Form(..., description="Full 10-digit HTS, 4/6-digit prefix, or product description"),
    k: int = Form(5, description="Number of top candidates (for prefix/description searches)"),
    processed_csv: str = Form(None, description="Optional processed CSV path")
):
    """
    Classify a query into HTS code(s). Uses QueryAgent (which reads the processed CSV).
    Behavior mirrors Streamlit UI:
      - If query is 10-digit numeric -> exact HTS lookup.
      - If 4/6-digit numeric -> prefix search.
      - Otherwise -> product description (vector search).
    """
    try:
        processed = Path(processed_csv) if processed_csv else DEFAULT_PROCESSED
        if not processed.exists():
            raise FileNotFoundError(f"Processed CSV not found at {processed}")

        qa_agent = QueryAgent(str(processed))
        clean = query.replace(".", "").strip()
        results: List[Dict[str, Any]] = []
        qtype = ""

        if clean.isdigit() and len(clean) == 10:
            qtype = "exact"
            hits = qa_agent.query_exact_hts(query.strip(), k=k)
            # query_exact_hts returns list of {"payload": row_dict, "score": ...}
            results = [h["payload"] for h in hits] if hits else []

        elif clean.isdigit() and len(clean) in (4, 6):
            qtype = "prefix"
            df = qa_agent.get_candidates_by_prefix(query.strip())
            if df is None or df.empty:
                results = []
            else:
                for _, row in df.head(k).iterrows():
                    results.append(_row_to_details(qa_agent, row))

        else:
            qtype = "fuzzy"
            df = qa_agent.get_candidates_by_product(query.strip(), k=k)
            if df is None or df.empty:
                results = []
            else:
                for _, row in df.head(k).iterrows():
                    results.append(_row_to_details(qa_agent, row))

        return {"query": query, "type": qtype, "results": results}
    except Exception as exc:
        logging.exception("Error in classify_endpoint")
        raise HTTPException(status_code=500, detail=str(exc))
