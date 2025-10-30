# embeddings_qdrant_pipeline_fixed.py

import os
import pandas as pd
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from openai import OpenAI
from dotenv import load_dotenv
from uuid import uuid4
from typing import List, Dict, Any, Sequence


# =========================
# CONFIGURATION
# =========================

COLLECTION_NAME = "csv_embeddings_cluster"
EMBED_MODEL = "text-embedding-3-small"


# =========================
# STEP 1: LOAD ENVIRONMENT
# =========================

def load_environment():
    """Load .env variables and initialize OpenAI and Qdrant clients."""
    load_dotenv()

    openai_api_key = os.getenv("OPENAI_API_KEY")
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not all([openai_api_key, qdrant_url, qdrant_api_key]):
        raise ValueError("Missing one or more API keys in .env file")

    openai_client = OpenAI(api_key=openai_api_key)
    qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    return openai_client, qdrant_client


# =========================
# STEP 2: CREATE COLLECTION
# =========================

def ensure_collection_exists(qdrant_client: QdrantClient, vector_size: int = 1536):
    """Ensure Qdrant collection exists, otherwise create it."""
    existing_collections = [c.name for c in qdrant_client.get_collections().collections]

    if COLLECTION_NAME not in existing_collections:
        qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        print(f"✅ Created new collection: {COLLECTION_NAME}")
    else:
        print(f"ℹ️ Collection '{COLLECTION_NAME}' already exists.")


# =========================
# STEP 3: READ CSV FILES
# =========================

def read_csvs() -> Dict[str, pd.DataFrame]:
    """Read all CSVs into pandas DataFrames."""
    csv_files = {
        "countries_list.csv": pd.read_csv("data/countries/countries_list.csv"),
        "hts_processed.csv": pd.read_csv("data/processed/hts_processed.csv"),
        "other_updated.csv": pd.read_csv("data/tariff_programs/tariff_programs.csv"),
    }
    return csv_files


# =========================
# STEP 4: EMBEDDING CREATION
# =========================

def create_embeddings_for_csv(
    openai_client: OpenAI, df: pd.DataFrame, doc_id: str
) -> List[PointStruct]:
    """Generate embeddings for each row in a DataFrame."""
    points: List[PointStruct] = []

    for i, row in df.iterrows():
        text = " | ".join(map(str, row.values))

        response = openai_client.embeddings.create(
            input=text,
            model=EMBED_MODEL
        )

        # Get embedding safely
        embedding = response.data[0].embedding if response and response.data else None
        if embedding is None:
            continue  # skip any invalid rows

        # Create Qdrant PointStruct
        point = PointStruct(
            id=str(uuid4()),
            vector=embedding,
            payload={
                "document_id": doc_id,
                "row_index": i,
                "content": text
            }
        )
        points.append(point)

    return points


# =========================
# STEP 5: UPLOAD TO QDRANT
# =========================

def upload_embeddings(qdrant_client: QdrantClient, points: Sequence[PointStruct]):
    """Upload a list of embedding points to Qdrant."""
    if not points:
        print("⚠️ No embeddings to upload.")
        return

    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=list(points)
    )


# =========================
# STEP 6: QUERY FUNCTION
# =========================

def query_embeddings(
    openai_client: OpenAI, qdrant_client: QdrantClient, query: str, top_k: int = 5
):
    """Search for the most relevant chunks in Qdrant."""
    query_embedding = openai_client.embeddings.create(
        input=query,
        model=EMBED_MODEL
    ).data[0].embedding

    results = qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_embedding,
        limit=top_k
    )

    print(f"\n🔍 Top {top_k} results for: '{query}'\n")
    for res in results:
        payload = res.payload or {}  # ensure it's a dict, not None
        print(f"Document: {payload.get('document_id', 'Unknown')}")
        print(f"Row Index: {payload.get('row_index', 'N/A')}")
        print(f"Content: {payload.get('content', 'N/A')}")
        print(f"Score: {res.score:.4f}\n")


# =========================
# STEP 7: MAIN PIPELINE
# =========================

def build_and_query_pipeline(query: str):
    """Main orchestrator function."""
    openai_client, qdrant_client = load_environment()
    ensure_collection_exists(qdrant_client)

    csv_data = read_csvs()

    for file_name, df in csv_data.items():
        doc_id = file_name.replace(".csv", "")
        print(f"\n📄 Processing {file_name} ({len(df)} rows)...")

        points = create_embeddings_for_csv(openai_client, df, doc_id)
        upload_embeddings(qdrant_client, points)

        print(f"✅ Uploaded {len(points)} embeddings for {file_name}")

    # Perform a query at the end
    query_embeddings(openai_client, qdrant_client, query)


# =========================
# RUN
# =========================

if __name__ == "__main__":
    sample_query = "Which country has ISO code PK?"
    build_and_query_pipeline(sample_query)
