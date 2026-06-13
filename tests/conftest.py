import os

os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("LLM_BASE_URL", "http://test-llm:8000/v1")
os.environ.setdefault("QDRANT_URL", "http://test-qdrant:6333")
os.environ.setdefault("QDRANT_API_KEY", "test-qdrant-key")
os.environ.setdefault("COLLECTION_NAME", "test-collection")
