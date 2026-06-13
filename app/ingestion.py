import os

import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
)
from qdrant_client.http.models import (
    PointStruct,
    Document,
)

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

COLLECTION_NAME = "python-qa"
PARQUET_FILE = "data/stack_overflow_rag.parquet"

MODEL_NAME = "sentence-transformers/all-minilm-l6-v2"
VECTOR_SIZE = 384

BATCH_SIZE = 100

print("Loading dataset...")
df = pd.read_parquet(PARQUET_FILE)

print(f"Documents: {len(df):,}")

client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
    cloud_inference=True,
    check_compatibility=False,
)

if client.collection_exists(COLLECTION_NAME):
    print("Deleting existing collection...")
    client.delete_collection(COLLECTION_NAME)

print("Creating collection...")

client.create_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(
        size=VECTOR_SIZE,
        distance=Distance.COSINE,
    ),
)

print("Uploading documents...")

for start in tqdm(range(0, len(df), BATCH_SIZE)):
    batch = df.iloc[start:start + BATCH_SIZE]

    points = []

    for _, row in batch.iterrows():
        points.append(
            PointStruct(
                id=int(row["Id"]),
                vector=Document(
                    text=str(row["document"]),
                    model=MODEL_NAME,
                ),
                payload={
                    "question_id": int(row["Id"]),
                    "title": str(row["Title"]),
                    "tags": str(row["Tags"]),
                    "question_score": int(row["question_score"]),
                    "document": str(row["document"]),
                },
            )
        )

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
        wait=False,
    )

print("Done.")