# agents/embedding_agent.py
from pathlib import Path
import pandas as pd
import tempfile
from utils.vectorstore import build_vectorstore

def create_embeddings(processed_csv_path: Path, overwrite: bool = False) -> int:
    """
    Embeds only the first 5 rows of the processed CSV and uploads to Qdrant.
    Returns number of points uploaded.
    """
    count = build_vectorstore(processed_csv_path, overwrite=overwrite)
    print(f"Indexed {count} points into Qdrant collection")

    return count