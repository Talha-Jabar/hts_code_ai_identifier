# chains/hts_chain.py
from pathlib import Path
from agents.fetch_agent import fetch_latest
from agents.preprocess_agent import preprocess
from agents.embedding_agent import create_embeddings

class HTSOrchestrator:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.raw_dir = base_dir / "data" / "raw"
        self.processed_dir = base_dir / "data" / "processed"
        self.emb_dir = base_dir / "data" / "embeddings"

    def run_preprocessing_pipeline(self) -> Path:
        """
        ✨ NEW ✨
        Runs the fast part of the pipeline:
        1. Fetches the latest raw CSV.
        2. Preprocesses the CSV.
        Returns the path to the processed CSV file.
        """
        raw_csv = fetch_latest(self.raw_dir)
        processed_csv = preprocess(raw_csv, self.processed_dir)
        return processed_csv

    def run_embedding_pipeline(self, processed_csv_path: Path) -> int:
        """
        ✨ NEW ✨
        Runs the slow part of the pipeline:
        1. Generates embeddings from the processed CSV.
        2. Uploads embeddings to the vector store (Qdrant).
        Returns the number of points indexed.
        """
        points_indexed = create_embeddings(processed_csv_path, overwrite=True)
        return points_indexed