from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and ``.env``."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    frontend_origin: str = "http://localhost:3002"
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_default_language: str = "en"
    ai_log_customer_input: bool = True
    auth_cookie_secure: bool = False
    auth_session_days: int = 7
    # A catalog run uses ten graph nodes before a retry. Leave room for two
    # targeted repair cycles instead of failing with a graph recursion error.
    agent_max_graph_iterations: int = 24
    agent_max_tool_calls: int = 8
    agent_max_repair_attempts: int = 2
    agent_response_format_attempts: int = 2
    # Semantic audit findings can be uncertain when the LLM is interpreting
    # shopper intent or catalog taxonomy. Only high-confidence findings block
    # a response; deterministic catalog facts remain strict.
    agent_audit_block_confidence: float = 0.75
    agent_model_timeout_seconds: float = 30
    agent_tool_timeout_seconds: float = 5
    database_url: str = "postgresql+psycopg://shopy@localhost:5433/shopy"
    redis_url: str = "redis://localhost:6379/0"
    shopping_memory_ttl_seconds: int = 1800
    shopping_memory_recent_turns: int = 8
    redis_socket_timeout_seconds: float = 1


settings = Settings()
