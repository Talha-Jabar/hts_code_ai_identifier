# api/dependencies.py
"""
Dependencies for the FastAPI application.
This module handles the initialization of shared resources like QueryAgent.
"""
from pathlib import Path
from typing import Optional
from agents.query_agent import QueryAgent

# Path to the pre-processed HTS data
BASE_DIR = Path(__file__).parent.parent
PROCESSED_CSV_PATH = BASE_DIR / "data" / "processed" / "hts_processed.csv"

# Shared instance of QueryAgent to avoid reloading the CSV file on every request
hts_query_agent: Optional[QueryAgent] = None

def get_query_agent() -> QueryAgent:
    """
    Initializes or returns a cached instance of the QueryAgent.
    This ensures the processed CSV is loaded only once when the application starts.
    """
    global hts_query_agent
    if hts_query_agent is None:
        if not PROCESSED_CSV_PATH.exists():
            raise FileNotFoundError(
                f"Required file not found: {PROCESSED_CSV_PATH}. "
                "Please run the data pipeline (e.g., HTSOrchestrator().run_full_pipeline()) first."
            )
        try:
            hts_query_agent = QueryAgent(processed_csv_path=str(PROCESSED_CSV_PATH))
            print("QueryAgent initialized successfully.")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize QueryAgent: {e}")
    return hts_query_agent
