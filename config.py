from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    llm_api_key: str = Field(default="dummy", alias="LLM_API_KEY")
    llm_base_url: str = Field(default="http://localhost:8002/v1", alias="LLM_BASE_URL")
    llm_model: str = Field(default="Qwen/Qwen2.5-Coder-7B-Instruct", alias="LLM_MODEL")

    # Qdrant 
    qdrant_url: str = Field(default="http://localhost:6333", env="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")

    # Collection names per strategy
    collection: str = Field(default="python-qa", alias="COLLECTION_NAME")

    # Chunking 
    chunk_size: int = 384

    # Retrieval 
    top_k: int = 5

    # Generation 
    max_tokens: int = 1024
    temperature: float = 0
    top_p: float = 0.7

    # App 
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


settings = Settings()