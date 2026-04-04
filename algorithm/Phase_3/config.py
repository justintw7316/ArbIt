"""
Phase 3 configuration loaded from .env via python-dotenv.
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class Phase3Config(BaseModel):
    # DeepSeek
    deepseek_api_key: str = Field(default="")
    deepseek_base_url: str = Field(default="https://api.deepseek.com")
    deepseek_model: str = Field(default="deepseek-chat")
    deepseek_temperature: float = Field(default=0.1)
    deepseek_max_retries: int = Field(default=3)

    # OpenAI
    openai_api_key: str = Field(default="")

    # Database
    database_url: str = Field(default="postgresql://localhost:5432/arbit")

    # Phase 3 tuning
    date_tolerance_days: int = Field(default=45)
    entity_match_threshold: float = Field(default=0.85)
    llm_rate_limit_rps: float = Field(default=5.0)
    enable_cache: bool = Field(default=False)

    # Reranker
    reranker_type: str = Field(default="mock")  # "mock" | "openai"


@lru_cache(maxsize=1)
def get_config() -> Phase3Config:
    return Phase3Config(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        deepseek_temperature=float(os.getenv("DEEPSEEK_TEMPERATURE", "0.1")),
        deepseek_max_retries=int(os.getenv("DEEPSEEK_MAX_RETRIES", "3")),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        database_url=os.getenv("DATABASE_URL", "postgresql://localhost:5432/arbit"),
        date_tolerance_days=int(os.getenv("PHASE3_DATE_TOLERANCE_DAYS", "45")),
        entity_match_threshold=float(os.getenv("PHASE3_ENTITY_MATCH_THRESHOLD", "0.85")),
        llm_rate_limit_rps=float(os.getenv("PHASE3_LLM_RATE_LIMIT_RPS", "5")),
        enable_cache=os.getenv("PHASE3_ENABLE_CACHE", "false").lower() == "true",
        reranker_type=os.getenv("PHASE3_RERANKER_TYPE", "mock"),
    )
