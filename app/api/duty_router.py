# app/api/duty_router.py
from fastapi import APIRouter, HTTPException, Depends # type: ignore
from app.schemas import CalculateRequest, CalculateResponse
from app.services.duty_service import DutyService
from app.session_store import session_store
from app.services.query_service import QueryService
from pathlib import Path
from typing import Optional, Dict, Any
import pandas as pd

router_duty = APIRouter(prefix="/api/duty", tags=["duty"])


# Dependency factory (fresh instance for each request; could be optimized like classify_router if needed)
def get_query_service_dep() -> QueryService:
    default = Path.cwd() / "data" / "processed" / "hts_processed.csv"
    if not default.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Processed HTS CSV not found at {default}. Run pipeline first.",
        )
    return QueryService(default)


@router_duty.post("/calculate", response_model=CalculateResponse)
def calculate_landed_cost(
    req: CalculateRequest, query_svc: QueryService = Depends(get_query_service_dep)
) -> CalculateResponse:
    payload: Optional[Dict[str, Any]] = None

    if req.session_id:
        s = session_store.get(req.session_id)
        if s is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if s.final_result_index is None:
            raise HTTPException(
                status_code=400,
                detail="Session has not resolved to a final HTS candidate yet",
            )

        # Retrieve candidate details safely
        row = query_svc.qa_agent.df.loc[s.final_result_index]
        if not hasattr(query_svc.qa_agent, "get_candidate_details"):
            raise HTTPException(
                status_code=500, detail="QueryAgent is missing get_candidate_details"
            )
        assert isinstance(row, pd.Series)
        payload = query_svc.qa_agent.get_candidate_details(row)

    elif req.hts_payload is not None:
        payload = req.hts_payload

    if payload is None:
        raise HTTPException(
            status_code=400, detail="Provide session_id or hts_payload to calculate duties"
        )

    ds = DutyService(payload)
    form_data = {
        "base_value": req.base_value,
        "country_iso": req.country_iso,
        "transport_mode": req.transport_mode,
        "entry_date": req.entry_date,
        "has_exclusion": req.has_exclusion,
        "metal_percent": req.metal_percent,
    }
    result = ds.calculate(form_data)

    # Map to CalculateResponse fields
    return CalculateResponse(
        base_value=result["base_value"],
        base_duty=result["base_duty"],
        metal_surcharge=result["metal_surcharge"],
        exclusion_reduction=result["exclusion_reduction"],
        total_duties=result["total_duties"],
        mpf_hmf_fees=result["mpf_hmf_fees"],
        landed_cost=result["landed_cost"],
        rate_category=result["rate_category"],
        duty_rate_pct=result["duty_rate_pct"],
        calculation_notes=result.get("calculation_notes", []),
    )
