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
    # Load first 5 rows
    # df = pd.read_csv(processed_csv_path, nrows=5)

    # Create a temporary file
    # with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as tmp:
    #     df.to_csv(tmp.name, index=False)
    #     temp_path = Path(tmp.name)

    # Build vectorstore from temp file
    # count = build_vectorstore(temp_path, overwrite=overwrite)
    count = build_vectorstore(processed_csv_path, overwrite=overwrite)
    print(f"Indexed {count} points into Qdrant collection")

    return count
