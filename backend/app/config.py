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
    ai_log_customer_input: bool = env_flag("AI_LOG_CUSTOMER_INPUT", True)
    auth_cookie_secure: bool = env_flag("AUTH_COOKIE_SECURE", False)
    auth_session_days: int = int(os.getenv("AUTH_SESSION_DAYS", "7"))
    agent_max_graph_iterations: int = int(os.getenv("AGENT_MAX_GRAPH_ITERATIONS", "12"))
    agent_max_tool_calls: int = int(os.getenv("AGENT_MAX_TOOL_CALLS", "8"))
    agent_max_repair_attempts: int = int(os.getenv("AGENT_MAX_REPAIR_ATTEMPTS", "2"))
    agent_response_format_attempts: int = int(os.getenv("AGENT_RESPONSE_FORMAT_ATTEMPTS", "2"))
    agent_model_timeout_seconds: float = float(os.getenv("AGENT_MODEL_TIMEOUT_SECONDS", "30"))
    agent_tool_timeout_seconds: float = float(os.getenv("AGENT_TOOL_TIMEOUT_SECONDS", "5"))
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://shopy@localhost:5433/shopy",
    )


settings = Settings()
