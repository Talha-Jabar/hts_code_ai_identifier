# utils/vectorstore.py
import os
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "hts_embeddings")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY environment variable is required for embeddings.")

_openai_client = OpenAI(api_key=OPENAI_API_KEY)

def embed_texts(texts: List[str], batch_size: int = 64) -> List[List[float]]:
    vectors = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        resp = _openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=chunk
        )
        for item in resp.data:
            vectors.append(item.embedding)
    return vectors

def get_qdrant_client() -> QdrantClient:
    if not QDRANT_URL or not QDRANT_API_KEY:
        raise RuntimeError("QDRANT_URL and QDRANT_API_KEY must be set for Qdrant usage.")
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)

def ensure_collection_and_indexes(vector_size: int = 1536):
    qdrant = get_qdrant_client()
    collections = qdrant.get_collections()
    existing = [c.name for c in collections.collections]

    if COLLECTION_NAME not in existing:
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=qdrant_models.VectorParams(size=vector_size, distance=qdrant_models.Distance.COSINE),
        )

    # Always ensure indexes exist for fast filtering
    for field in ["prefix4", "prefix6", "hts_code"]:
        try:
            qdrant.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field,
                field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass  # Index may already exist

def build_vectorstore(processed_csv_path: Path, overwrite: bool = False) -> int:
    df = pd.read_csv(processed_csv_path, dtype=str).fillna("")
    if df.empty:
        return 0

    texts, payloads = [], []
    for i, row in df.iterrows():
        # Prefer the "text" column (already built from Spec_Level_* during preprocessing)
        text = str(row.get("text", "")).strip()
        if not text:
            # fallback: concatenate only specification-related columns
            spec_cols = [c for c in df.columns if c.startswith("Spec_Level_")]
            text = " | ".join([row.get(c, "") for c in spec_cols if row.get(c, "")])

        payload = {
            "hts_code": str(row.get("hts_code", "")),
            "prefix4": str(row.get("prefix4", "")),
            "prefix6": str(row.get("prefix6", "")),
            "text": text,
            "source": str(processed_csv_path),
            "row_index": str(i),  # type: ignore
        }

        # Preserve ALL other columns from the CSV (Spec_Level_*, duties, unit, etc.)
        for c in df.columns:
            payload[c] = row.get(c, "")

        texts.append(text)
        payloads.append(payload)

    vectors = embed_texts(texts)
    vector_size = len(vectors[0])
    qdrant = get_qdrant_client()

    ensure_collection_and_indexes(vector_size)

    # count_info = qdrant.count(COLLECTION_NAME)
    # if count_info.count > 0 and not overwrite:
    #     print(f"Collection already has {count_info.count} vectors. Skipping re-embedding.")
    #     return count_info.count

    points = [
        qdrant_models.PointStruct(id=int(i), vector=vectors[i], payload=payloads[i])
        for i in range(len(texts))
    ]

    CHUNK = 64
    for i in range(0, len(points), CHUNK):
        qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=points[i:i+CHUNK],
            wait=True,
        )

    return len(points)

def _build_prefix_filter(prefix4: Optional[str], prefix6: Optional[str], exact_hts: Optional[str]):
    must = []
    if exact_hts:
        must.append(qdrant_models.FieldCondition(
            key="hts_code",
            match=qdrant_models.MatchValue(value=exact_hts)
        ))
    if prefix6:
        must.append(qdrant_models.FieldCondition(
            key="prefix6",
            match=qdrant_models.MatchValue(value=prefix6)
        ))
    if prefix4:
        must.append(qdrant_models.FieldCondition(
            key="prefix4",
            match=qdrant_models.MatchValue(value=prefix4)
        ))
    return qdrant_models.Filter(must=must) if must else None

def search_qdrant(query: str, k: int = 10, prefix4: Optional[str] = None,
                  prefix6: Optional[str] = None, exact_hts: Optional[str] = None) -> List[Dict]:
    qdrant = get_qdrant_client()
    vec = embed_texts([query])[0]
    query_filter = _build_prefix_filter(prefix4, prefix6, exact_hts)
    hits = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=vec,
        limit=k,
        query_filter=query_filter,
    )
    return [{"score": h.score, "payload": h.payload} for h in hits]