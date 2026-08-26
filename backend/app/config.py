from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def env_flag(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3002")
    whisper_model: str = os.getenv("WHISPER_MODEL", "small")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")
    whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    whisper_default_language: str = os.getenv("WHISPER_DEFAULT_LANGUAGE", "en")
    ai_log_customer_input: bool = env_flag("AI_LOG_CUSTOMER_INPUT", True)
    auth_cookie_secure: bool = env_flag("AUTH_COOKIE_SECURE", False)
    auth_session_days: int = int(os.getenv("AUTH_SESSION_DAYS", "7"))
    # A catalog run uses ten graph nodes before a retry. Leave room for two
    # targeted repair cycles instead of failing with a graph recursion error.
    agent_max_graph_iterations: int = int(os.getenv("AGENT_MAX_GRAPH_ITERATIONS", "24"))
    agent_max_tool_calls: int = int(os.getenv("AGENT_MAX_TOOL_CALLS", "8"))
    agent_max_repair_attempts: int = int(os.getenv("AGENT_MAX_REPAIR_ATTEMPTS", "2"))
    agent_response_format_attempts: int = int(os.getenv("AGENT_RESPONSE_FORMAT_ATTEMPTS", "2"))
    # Semantic audit findings can be uncertain when the LLM is interpreting
    # shopper intent or catalog taxonomy. Only high-confidence findings block
    # a response; deterministic catalog facts remain strict.
    agent_audit_block_confidence: float = float(os.getenv("AGENT_AUDIT_BLOCK_CONFIDENCE", "0.75"))
    agent_model_timeout_seconds: float = float(os.getenv("AGENT_MODEL_TIMEOUT_SECONDS", "30"))
    agent_tool_timeout_seconds: float = float(os.getenv("AGENT_TOOL_TIMEOUT_SECONDS", "5"))
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://shopy@localhost:5433/shopy",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    shopping_memory_ttl_seconds: int = int(os.getenv("SHOPPING_MEMORY_TTL_SECONDS", "1800"))
    shopping_memory_recent_turns: int = int(os.getenv("SHOPPING_MEMORY_RECENT_TURNS", "8"))
    redis_socket_timeout_seconds: float = float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "1"))


settings = Settings()
