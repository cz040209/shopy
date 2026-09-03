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
    gemini_model: str = "gemini-3.7-flash"
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen3.6-flash"
    qwen_audio_model: str = "qwen3-omni-30b-a3b-captioner"
    qwen_enable_thinking: bool = True
    frontend_origin: str = "http://localhost:3002"
    transcription_default_language: str = "en"
    transcription_timeout_seconds: float = 60
    ai_log_customer_input: bool = True
    ai_log_agent_node_payloads: bool = True
    auth_cookie_secure: bool = False
    auth_session_days: int = 7
    # A catalog run uses ten graph nodes before a retry. Leave room for two
    # targeted repair cycles instead of failing with a graph recursion error.
    agent_max_graph_iterations: int = 24
    agent_max_tool_calls: int = 8
    # Retrieval reads the catalog snapshot in compact batches, then sends only
    # a verified semantic shortlist to downstream response agents.
    agent_catalog_context_limit: int = 500
    agent_catalog_batch_size: int = 80
    agent_catalog_batch_concurrency: int = 4
    agent_catalog_batch_shortlist_limit: int = 12
    agent_catalog_shortlist_limit: int = 48
    agent_catalog_role_matches_per_need: int = 6
    agent_bundle_options_per_need: int = 12
    agent_bundle_beam_width: int = 800
    agent_max_repair_attempts: int = 2
    agent_response_format_attempts: int = 2
    # Semantic audit findings can be uncertain when the LLM is interpreting
    # shopper intent or catalog taxonomy. Only high-confidence findings block
    # a response; deterministic catalog facts remain strict.
    agent_audit_block_confidence: float = 0.75
    # Near-budget alternatives can be shown when they are explicitly disclosed
    # to the shopper; the customer budget remains the primary target.
    agent_recommendation_budget_tolerance_percent: float = 30
    agent_model_timeout_seconds: float = 30
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
    upload_directory: Path = Path("/tmp/shopy-uploads")
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True

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
