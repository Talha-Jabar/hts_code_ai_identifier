# HTS Code Identifier

Automates:

1. Downloading latest HTS CSV from USITC archive (scraper).
2. Preprocessing raw CSV into a cleaned `processed` CSV with combined `text` for embeddings.
3. Generating OpenAI embeddings and storing them in Qdrant Cloud (per-row payload includes `hts_code`, `prefix4`, `prefix6`).
4. Streamlit interactive UI: exact HTS query, partial prefix narrowing, product-name narrowing with query-driven clarifying questions.

## Requirements

- Python 3.10+
- Environment variables:
  - `OPENAI_API_KEY`
  - `QDRANT_URL`
  - `QDRANT_API_KEY`

## Quickstart

1. Create venv & install:

   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
