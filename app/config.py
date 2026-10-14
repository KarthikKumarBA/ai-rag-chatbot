"""All settings come from environment variables (.env)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    openai_model_id: str
    anthropic_model_id: str
    bedrock_model_id: str
    aws_region: str
    embedding_provider: str
    openai_embedding_model: str
    bedrock_embedding_model: str
    docs_source: str
    docs_dir: Path
    wiki_base_url: str
    wiki_public_url: str
    wiki_api_token: str
    vectorstore_dir: Path
    collection_name: str
    chunk_size: int
    chunk_overlap: int
    top_k: int
    min_relevance: float
    max_tokens: int
    history_turns: int


def get_settings() -> Settings:
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
    wiki_base_url = os.getenv("WIKI_BASE_URL", "http://127.0.0.1:8088").rstrip("/")
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "openai").lower(),
        # gpt-4o-mini: fastest and cheapest in our evaluation, passes leak + refusal tests
        openai_model_id=os.getenv("OPENAI_MODEL_ID", "gpt-4o-mini"),
        anthropic_model_id=os.getenv("ANTHROPIC_MODEL_ID", "claude-haiku-4-5"),
        bedrock_model_id=os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        embedding_provider=embedding_provider,
        openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        bedrock_embedding_model=os.getenv("BEDROCK_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0"),
        docs_source=os.getenv("DOCS_SOURCE", "wiki").lower(),
        docs_dir=Path(os.getenv("DOCS_DIR", str(ROOT / "data" / "docs"))),
        wiki_base_url=wiki_base_url,
        wiki_public_url=os.getenv("WIKI_PUBLIC_URL", wiki_base_url).rstrip("/"),
        wiki_api_token=os.getenv("WIKI_API_TOKEN", ""),
        vectorstore_dir=Path(os.getenv("VECTORSTORE_DIR", str(ROOT / "vectorstore"))),
        # One collection per embedding provider: vectors from different models never mix
        collection_name=os.getenv("COLLECTION_NAME", f"company_docs_{embedding_provider}"),
        chunk_size=int(os.getenv("CHUNK_SIZE", "800")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "120")),
        top_k=int(os.getenv("TOP_K", "4")),
        min_relevance=float(os.getenv("MIN_RELEVANCE", "0.3")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "400")),
        history_turns=int(os.getenv("HISTORY_TURNS", "3")),
    )
