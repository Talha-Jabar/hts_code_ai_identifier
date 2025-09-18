from fastapi import APIRouter, HTTPException, Form # type: ignore
from pathlib import Path
import logging
from datetime import datetime
import pandas as pd

from api.schemas import DutyResult
from agents.query_agent import QueryAgent
from services.duty_calculator import DutyCalculator  # matches your streamlit usage

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_PROCESSED = BASE_DIR / "data" / "processed" / "hts_processed.csv"


@router.post("/", response_model=DutyResult)
def duty_endpoint(
    hs_code: str = Form(..., description="Full 10-digit HTS number"),
    base_value: float = Form(..., description="Base product value (USD)"),
    quantity: int = Form(1, description="Quantity, optional"),
    country_iso: str = Form(None, description="Country of origin ISO code (e.g., CN)"),
    transport_mode: str = Form("Ocean", description="Transport mode: Ocean/Air/Rail/Truck"),
    entry_date: str = Form(None, description="Entry date in YYYY-MM-DD (optional)"),
    has_exclusion: bool = Form(False, description="Apply Chapter 99 exclusion?"),
    metal_percent: int = Form(0, description="Metal content percentage (0-100)")
):
    """
    Calculate landed cost using the project's DutyCalculator.
    This endpoint will:
      - look up the HTS row from the processed CSV via QueryAgent.query_exact_hts
      - build a DutyCalculator with the matched row, run calculate_landed_cost(form_data)
      - return structured result
    """
    try:
        processed = DEFAULT_PROCESSED
        if not processed.exists():
            raise FileNotFoundError(f"Processed CSV not found at {processed}")

        qa_agent = QueryAgent(str(processed))
        hits = qa_agent.query_exact_hts(hs_code, k=5)
        if not hits:
            raise HTTPException(status_code=404, detail=f"No HTS entry found for {hs_code}")

        # Use first exact match
        payload = hits[0]["payload"]  # this is a dict (row.to_dict())
        # convert to pandas Series so DutyCalculator matches streamlit usage
        candidate_series = pd.Series(payload)

        # Build form_data matching the streamlit structure
        form_data = {
            "base_value": float(base_value),
            "country_iso": country_iso,
            "transport_mode": transport_mode,
            "entry_date": datetime.strptime(entry_date, "%Y-%m-%d").date() if entry_date else datetime.today().date(),
            "has_exclusion": bool(has_exclusion),
            "metal_percent": int(metal_percent),
            "quantity": int(quantity)
        }

        calculator = DutyCalculator(candidate_series)
        calc = calculator.calculate_landed_cost(form_data)

        # Ensure keys for response
        landed = float(calc.get("landed_cost", 0.0))
        total_duties = float(calc.get("total_duties", 0.0))
        return {
            "hs_code": hs_code,
            "base_value": base_value,
            "quantity": quantity,
            "country_iso": country_iso,
            "transport_mode": transport_mode,
            "landed_cost": landed,
            "total_duties": total_duties,
            "details": calc
        }
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("Error in duty_endpoint")
        raise HTTPException(status_code=500, detail=str(exc))
