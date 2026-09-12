from decimal import Decimal
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
PROJECT_DIRECTORY = BACKEND_DIRECTORY.parent
ENV_FILE = PROJECT_DIRECTORY / ".env"
DEFAULT_UPLOAD_DIRECTORY = BACKEND_DIRECTORY / "data" / "uploads"


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
    gemini_model: str = "gemini-3.7-flash"
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen3.7-max-2026-06-08"
    # Available in the Model Studio free quota and accepts image input through
    # the OpenAI-compatible chat-completions endpoint.
    qwen_vision_model: str = "qwen3.5-omni-plus"
    # Dedicated ASR model for short recorded voice requests. It returns the
    # spoken text directly instead of an audio description.
    qwen_audio_model: str = "qwen3-asr-flash-2025-09-08"
    qwen_enable_thinking: bool = True
    frontend_origin: str = "http://localhost:8002"
    transcription_default_language: str = "en"
    transcription_timeout_seconds: float = 60
    ai_log_customer_input: bool = True
    ai_log_agent_node_payloads: bool = True
    auth_cookie_secure: bool = False
    auth_session_days: int = 7
    # Wallet rules are delivered by the API so clients do not invent their own
    # thresholds or infer usage from a partial transaction history.
    wallet_minimum_top_up: Decimal = Field(default=Decimal("10.00"), gt=0, max_digits=12, decimal_places=2)
    # Covers the longest vision + planning + compatibility + final-audit path.
    # This is a node safety bound, not a retry count.
    agent_max_graph_iterations: int = 24
    agent_max_tool_calls: int = 8
    # Retrieval asks the database for a bounded set per intent-derived product
    # role. The full catalog is never copied into an LLM prompt.
    agent_catalog_shortlist_limit: int = 36
    agent_catalog_role_matches_per_need: int = 8
    agent_bundle_options_per_need: int = 12
    agent_bundle_beam_width: int = 800
    agent_response_format_attempts: int = 2
    # Product selection is always performed once by the configured LLM. A
    # failed selection is surfaced; it is never replaced or retried by a
    # deterministic recommendation path.
    # Near-budget alternatives can be shown when they are explicitly disclosed
    # to the shopper; the customer budget remains the primary target.
    agent_recommendation_budget_tolerance_percent: float = 40
    agent_model_timeout_seconds: float = 30
    # Intent extraction can contain six roles with several query variants, and
    # product selection includes a reason for every chosen catalog ID.
    agent_model_max_output_tokens: int = 1600
    # A complete multi-role intent contract is larger than ordinary response
    # prose. A separate ceiling prevents valid JSON from being cut off without
    # making every other LLM call unnecessarily verbose.
    agent_intent_max_output_tokens: int = 5000
    agent_selector_max_output_tokens: int = 5000
    # Optional semantic enrichments must never hold the verified deterministic
    # workflow open for a full provider timeout.
    agent_optional_model_timeout_seconds: float = 8
    # Optional rewriting is skipped once the verified draft approaches common
    # reverse-proxy request limits. The already-audited answer remains valid.
    agent_response_soft_deadline_seconds: float = 75
    agent_tool_timeout_seconds: float = 5
    database_url: str = "postgresql+psycopg://shopy@localhost:5433/shopy"
    redis_url: str = "redis://localhost:6379/0"
    shopping_memory_ttl_seconds: int = 1800
    shopping_memory_recent_turns: int = 8
    redis_socket_timeout_seconds: float = 1
    # Keep uploaded account assets outside the OS temporary directory.  The
    # default survives backend restarts; production should point this setting
    # at a mounted persistent volume or object-storage-backed path.
    upload_directory: Path = DEFAULT_UPLOAD_DIRECTORY
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True

    @field_validator("upload_directory", mode="before")
    @classmethod
    def resolve_upload_directory(cls, value: str | Path) -> Path:
        """Resolve relative upload paths from ``backend``, not the launch CWD."""
        path = Path(value)
        return path if path.is_absolute() else BACKEND_DIRECTORY / path

    @property
    def receipt_email_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_from_email)

    @property
    def active_llm_model(self) -> str:
        """Report the provider that will receive the next text or vision request."""
        return self.qwen_model if self.qwen_api_key else self.gemini_model

    @property
    def llm_provider_configured(self) -> bool:
        return bool(self.qwen_api_key or self.gemini_api_key)


settings = Settings()
