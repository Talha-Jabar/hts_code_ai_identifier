# api/main.py
"""
The main FastAPI application for the HTS project.
Contains two endpoints for HTS identification and duty calculation.
To run this file, navigate to your project directory in the terminal and run:
`uvicorn api.main:app --reload`
"""
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import ValidationError
from api.dependencies import get_query_agent
from api.models import HTSIdentifierRequest, HTSIdentifierResponse, \
    DutyCalculationRequest, DutyCalculationResponse
from api.services import identify_hts_code_service, calculate_duty_service
from agents.query_agent import QueryAgent

# Initialize the FastAPI application
app = FastAPI(
    title="HTS Intelligent Assistant API",
    description="A microservice for HTS code identification and import duty calculation."
)

@app.on_event("startup")
async def startup_event():
    """
    Event handler to run on application startup.
    Initializes the QueryAgent to load the data into memory.
    """
    try:
        get_query_agent()
    except Exception as e:
        print(f"Failed to initialize QueryAgent at startup: {e}")
        # Optionally, raise an exception to prevent the app from starting if data is critical.
        # For this example, we'll let it fail gracefully and handle errors in the endpoints.

@app.post(
    "/identify-hts",
    response_model=HTSIdentifierResponse,
    summary="Identify HTS Number",
    description="Identifies a potential 10-digit HTS number based on a product description or a partial HTS number."
)
async def identify_hts_code(
    request: HTSIdentifierRequest,
    query_agent: QueryAgent = Depends(get_query_agent)
):
    """
    **Identify HTS Number Endpoint**
    
    This endpoint takes a product description or a partial HTS number and returns
    a list of the most likely HTS codes with their details.
    
    - **`query`**: The product description (e.g., "men's cotton shirts") or a partial HTS number (e.g., "6205").
    - **`k`**: The number of search results to retrieve (default: 20).
    - **`prefix`**: An optional HTS prefix to further narrow down the search.
    
    Returns:
    - A list of candidate HTS codes with their descriptions and rates.
    - Notes or questions to help the user refine their search.
    """
    try:
        if query_agent is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="HTS data is not yet loaded. Please try again in a moment."
            )
        
        response_data = identify_hts_code_service(request, query_agent)
        return HTSIdentifierResponse(**response_data)
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request body: {e.errors()}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}"
        )

@app.post(
    "/calculate-duty",
    response_model=DutyCalculationResponse,
    summary="Calculate Tariff Duty",
    description="Calculates the total tariff duty and landed cost for a specific product."
)
async def calculate_duty(
    request: DutyCalculationRequest,
    query_agent: QueryAgent = Depends(get_query_agent)
):
    """
    **Calculate Tariff Duty Endpoint**
    
    This endpoint calculates the estimated landed cost for an import based on the
    HTS number, product value, country of origin, and transport mode.
    
    - **`hts_number`**: The 10-digit HTS number (e.g., "6205.20.2010").
    - **`product_value`**: The base value of the product in USD.
    - **`country`**: The country of origin's ISO 3166-1 alpha-2 code (e.g., "CN" for China).
    - **`transport_mode`**: The mode of transport (e.g., "Air", "Ocean", "Truck").
    
    Returns:
    - A detailed breakdown of the calculation, including base duty, surcharges, and total landed cost.
    - Notes about the calculation, such as applicable exemptions.
    """
    try:
        if query_agent is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="HTS data is not yet loaded. Please try again in a moment."
            )

        response_data = calculate_duty_service(request, query_agent)
        return DutyCalculationResponse(**response_data)
    
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request body: {e.errors()}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}"
        )
