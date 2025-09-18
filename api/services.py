# api/services.py
"""
Core business logic functions for the API endpoints.
This separates the endpoint logic from the core functionality.
"""
import pandas as pd
from typing import List, Dict, Any, Optional
from agents.query_agent import QueryAgent
from services.duty_calculator import DutyCalculator
from api.models import HTSIdentifierRequest, DutyCalculationRequest

def identify_hts_code_service(
    request: HTSIdentifierRequest,
    query_agent: 'QueryAgent'
) -> Dict[str, Any]:
    """
    Performs the HTS code identification using the QueryAgent.
    """
    try:
        # Check if the query is a partial HTS number (digits only)
        if request.query.isdigit():
            candidates = query_agent.get_candidates_by_prefix(request.query)
            if candidates.empty:
                return {
                    "results": [],
                    "notes": [f"No HTS codes found for the prefix '{request.query}'."]
                }
            
            candidate_details = [query_agent.get_candidate_details(c) for _, c in candidates.iterrows()]
            
            # The corrected method name from your query_agent.py file
            smart_question = query_agent.generate_smart_question(candidates)
            
            notes = []
            if smart_question:
                notes.append(smart_question.get("question", "A question could not be generated."))
            
            return {
                "results": candidate_details,
                "notes": notes
            }

        # Otherwise, perform a semantic search
        else:
            candidates = query_agent.get_candidates_by_product(request.query, k=request.k)
            if candidates.empty:
                return {
                    "results": [],
                    "notes": ["No matching HTS codes found. Please try a different product description."]
                }
            
            candidate_details = [query_agent.get_candidate_details(c) for _, c in candidates.iterrows()]
            return {
                "results": candidate_details,
                "notes": []
            }

    except Exception as e:
        print(f"Error during HTS identification: {e}")
        return {
            "results": [],
            "notes": ["An unexpected error occurred during HTS identification. Please check the logs."]
        }


def calculate_duty_service(
    request: DutyCalculationRequest,
    query_agent: 'QueryAgent'
) -> Dict[str, Any]:
    """
    Calculates the duty and landed cost for a given HTS code.
    """
    try:
        hts_code = request.hts_number.strip().replace('.', '')
        
        # Look up the HTS code in the pre-processed data
        hts_data_row = query_agent.df[query_agent.df["HTS_Normalized"] == hts_code]
        
        if hts_data_row.empty:
            return {
                "results": {},
                "notes": [f"HTS code '{request.hts_number}' not found in the dataset."]
            }
        
        hts_data = hts_data_row.iloc[0]
        
        # Instantiate the DutyCalculator
        calculator = DutyCalculator(hts_data=hts_data)
        
        # Perform the calculation
        # Create a dictionary to match the expected `form_data` parameter
        calculation_form_data = {
            "base_value": float(request.product_value),
            "country_of_origin": request.country,
            "transport_mode": request.transport_mode
        }
        
        calculation_result = calculator.calculate_landed_cost(form_data=calculation_form_data)
        
        return {
            "results": calculation_result,
            "notes": calculation_result.get("calculation_notes", [])
        }
        
    except Exception as e:
        print(f"Error during duty calculation: {e}")
        return {
            "results": {},
            "notes": ["An unexpected error occurred during duty calculation. Please check the logs."]
        }
