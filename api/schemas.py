from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# --- Fetch / Preprocess / Embeddings responses ---
class SimpleResponse(BaseModel):
    message: str
    path: Optional[str] = None

class EmbeddingsResponse(BaseModel):
    message: str
    indexed_count: int

# --- Classification / Candidates ---
class CandidateItem(BaseModel):
    HTS_Number: Optional[str] = None
    Description: Optional[str] = None
    Specifications: Optional[str] = None
    Unit_of_Quantity: Optional[str] = None
    General_Rate_of_Duty: Optional[str] = None
    Special_Rate_of_Duty: Optional[str] = None
    Column_2_Rate_of_Duty: Optional[str] = None
    # allow other keys if present
    extra: Optional[Dict[str, Any]] = None

class ClassifyResponse(BaseModel):
    query: str
    type: str  # "exact", "prefix", "fuzzy"
    results: List[Dict[str, Any]]

class CandidatesResponse(BaseModel):
    query: str
    kind: str  # "prefix" or "product"
    top_k: int
    candidates: List[Dict[str, Any]]

# --- Duty ---
class DutyResult(BaseModel):
    hs_code: str
    base_value: float
    quantity: Optional[int]
    country_iso: Optional[str]
    transport_mode: Optional[str]
    landed_cost: float
    total_duties: float
    details: Dict[str, Any]
