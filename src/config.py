from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    azure_client_id: str
    azure_client_secret: str
    azure_authority: str = "https://login.microsoftonline.com/common"
    azure_scopes: list[str] = [
        "User.Read",
        "Tasks.ReadWrite",
        "Group.Read.All",
        "OnlineMeetings.Read",
        "OnlineMeetingTranscript.Read.All",
        "Calendars.Read",
        "Mail.Read",
        "Chat.Read",
    ]
    redirect_uri: str = "http://localhost:8000/auth/callback"

    session_secret_key: str = "change-this-to-a-random-secret-key"
    session_max_age: int = 8 * 60 * 60  # 8 hours

    database_url: str = "sqlite+aiosqlite:///./elephandroid.db"

    # LLM provider: "ollama" | "claude" | "openai" | "gemini"
    llm_provider: str = "ollama"

    # Ollama (offline SLM)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    ollama_timeout: int = 120

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Google Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # Azure Communication Services (meeting bot)
    acs_connection_string: str = ""
    acs_callback_url: str = "http://localhost:8000/bot/callbacks"

    # Teams Bot (Azure Bot Service)
    bot_app_id: str = ""
    bot_app_password: str = ""

    # Chat
    chat_max_history: int = 20

    # Stripe
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_pro_price_id: str = ""
    stripe_enterprise_price_id: str = ""

    # CORS
    cors_origins: list[str] = ["*"]

    # Rate limiting (requests per minute per IP)
    rate_limit_rpm: int = 120

    # Logging
    log_level: str = "INFO"
    log_json: bool = False  # True for structured JSON logs in production

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


settings = Settings()
