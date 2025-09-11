# utils/downloader.py
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin

ARCHIVE_URL = "https://www.usitc.gov/harmonized_tariff_information/hts/archive/list"

def _download_stream(url: str, dest: Path, chunk_size: int = 8192) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
    return dest

def _find_csv_links(soup: BeautifulSoup, base_url: str):
    links = []
    for a in soup.find_all("a", href=True):
        href = a.get("href") # type: ignore
        text = (a.get_text() or "").lower()
        if href and (href.lower().endswith(".csv") or "csv" in text): # type: ignore
            links.append(urljoin(base_url, href)) # type: ignore
    return links

def download_csv_via_requests(list_page_url: str, dest_path: Path) -> Path:
    resp = requests.get(list_page_url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    csv_links = _find_csv_links(soup, list_page_url)
    if not csv_links:
        raise RuntimeError("No CSV links found.")
    chosen = csv_links[0]
    return _download_stream(chosen, dest_path)

def download_latest_hts_csv(dest_folder: Path, filename: str = "hts_latest.csv") -> Path:
    dest_folder.mkdir(parents=True, exist_ok=True)
    dest = dest_folder / filename
    if dest.exists():
        dest.unlink()
    print("Using requests-based scraper.")
    return download_csv_via_requests(ARCHIVE_URL, dest)
