# ---------------------------
# File: app/schemas.py
# ---------------------------
from typing import List, Optional, Union, Any, Dict
from pydantic import BaseModel, Field
from datetime import date


class ClassifyRequest(BaseModel):
    query: str = Field(..., description="HTS number (4/6/10 digit) or product description")


class OptionOut(BaseModel):
    label: str
    filter_value: Union[str, List[str], None] = None
    expected_count: int = 0


class QuestionOut(BaseModel):
    question_id: int
    question: str
    spec_column: str
    options: List[OptionOut]


class CandidateSummary(BaseModel):
    hts_number: str
    description: str
    specifications: str
    unit_of_quantity: Optional[str]


class ClassifyResponseExact(BaseModel):
    type: str = "exact"
    result: Dict[str, Any]


class ClassifyResponseSession(BaseModel):
    type: str = "session"
    session_id: str
    candidates_count: int
    first_question: Optional[QuestionOut] = None


class AnswerRequest(BaseModel):
    session_id: str
    # Either provide the label of the option or filter_value directly
    selected_label: Optional[str] = None
    selected_filter_value: Optional[Union[str, List[str]]] = None


class ResultResponse(BaseModel):
    final: Optional[Dict[str, Any]]
    candidates_preview: Optional[List[CandidateSummary]]


class CalculateRequest(BaseModel):
    # Provide either session_id (to use the session's final result) or hts_number + payload
    session_id: Optional[str] = None
    hts_payload: Optional[Dict[str, Any]] = None

    base_value: float
    country_iso: str
    transport_mode: str
    entry_date: date
    has_exclusion: bool = False
    metal_percent: int = 0


class CalculateResponse(BaseModel):
    base_value: float
    base_duty: float
    metal_surcharge: float
    exclusion_reduction: float
    total_duties: float
    mpf_hmf_fees: float
    landed_cost: float
    rate_category: str
    duty_rate_pct: float
    calculation_notes: List[str] = []