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

    def run_full_pipeline(self) -> dict:
        """
        1. fetch latest raw CSV
        2. preprocess CSV
        3. generate embeddings and upload to Qdrant
        """
        raw_csv = fetch_latest(self.raw_dir)
        processed_csv = preprocess(raw_csv, self.processed_dir)
        points_indexed = create_embeddings(processed_csv)
        return {"raw": raw_csv, "processed": processed_csv, "points_indexed": points_indexed}