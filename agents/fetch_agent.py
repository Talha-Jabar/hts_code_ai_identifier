# agents/fetch_agent.py
from pathlib import Path
from utils.downloader import download_latest_hts_csv

def fetch_latest(raw_dir: Path) -> Path:
    """
    Download the latest HTS CSV into raw_dir and return the file path.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    downloaded = download_latest_hts_csv(raw_dir, filename="hts_latest.csv")
    print("Downloaded HTS CSV to:", downloaded)
    return Path(downloaded)