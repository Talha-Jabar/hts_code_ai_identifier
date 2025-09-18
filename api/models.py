# api/models.py
"""
Pydantic models for API request and response bodies.
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from decimal import Decimal

class HTSIdentifierRequest(BaseModel):
    """
    Request model for the HTS number identifier endpoint.
    """
    query: str = Field(..., description="A product description or partial HTS number.")
    k: int = Field(default=20, gt=0, description="The number of search results to return.")
    prefix: Optional[str] = Field(default=None, description="An optional HTS number prefix to refine the search.")

class HTSIdentifierResponse(BaseModel):
    """
    Response model for the HTS number identifier endpoint.
    """
    results: List[Dict[str, Any]] = Field(..., description="A list of matching HTS code candidates.")
    notes: List[str] = Field(default=[], description="Additional notes or questions to refine the search.")

class DutyCalculationRequest(BaseModel):
    """
    Request model for the duty calculation endpoint.
    """
    hts_number: str = Field(..., description="The 10-digit HTS number.")
    product_value: Decimal = Field(..., ge=0, description="The base value of the product in USD.")
    country: str = Field(..., description="The country of origin's ISO 3166-1 alpha-2 code.")
    transport_mode: str = Field(..., description="The mode of transport (e.g., 'Air', 'Ocean', 'Truck').")

class DutyCalculationResponse(BaseModel):
    """
    Response model for the duty calculation endpoint.
    """
    results: Dict[str, Any] = Field(..., description="The detailed duty and landed cost calculation.")
    notes: List[str] = Field(default=[], description="Notes about the calculation.")
