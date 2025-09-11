# agents/preprocess_agent.py
from pathlib import Path
from utils.preprocessing import flatten_hts_with_indent

def preprocess(raw_csv_path: Path, processed_dir: Path) -> Path:
    processed_dir.mkdir(parents=True, exist_ok=True)
    processed_path = processed_dir / "hts_processed.csv"
    if processed_path.exists():
        processed_path.unlink()
    processed = flatten_hts_with_indent(raw_csv_path, processed_path, max_levels=10)
    print("Processed CSV saved to:", processed)
    return processed
