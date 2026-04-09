from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    debug: bool = False
    app_name: str = "MedBot API"

    # Database
    database_url: str = "postgresql+asyncpg://medbot:medbot@localhost:5432/medbot"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"

    # Security / JWT
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # CORS
    allowed_origins: list[str] = [
        "http://localhost:4200",
        "http://localhost:4201",
    ]

    # Ollama / OpenRouter (compativel com OpenAI API)
    openrouter_api_key: str = "ollama"
    openrouter_base_url: str = "http://localhost:11434/v1"

    # Modelos IA (Ollama local)
    model_economico: str = "llama3.1:8b"
    model_medico: str = "cniongolo/biomistral:latest"
    model_premium: str = "llama3.1:8b"
    model_rag: str = "cniongolo/biomistral:latest"
    model_embed: str = "nomic-embed-text"

    # Billing Limits
    daily_limit_usd: float = 10.00
    monthly_limit_usd: float = 200.00
    alert_threshold_pct: int = 80

    # WhatsApp / Evolution API
    evolution_api_url: str = "http://localhost:8080"
    evolution_api_key: str = ""
    whatsapp_instance: str = "medbot"
    whatsapp_provider: str = "evolution"  # "evolution" | "uazapi" | "zapi" | "meta"

    # SMS / Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Email / SendGrid
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = ""


settings = Settings()


# Roteamento de modelos por feature — NUNCA alterar sem aprovacao
ROUTING_RULES: dict[str, str] = {
    "saudacao": settings.model_economico,
    "coleta_dados": settings.model_economico,
    "triagem_clinica": settings.model_medico,
    "rag_protocolo": settings.model_rag,
    "caso_complexo": settings.model_premium,
    "agendamento": settings.model_economico,
}

# Licenciamento — trial e quotas por plano
TRIAL_DIAS: int = 14

PLANO_QUOTAS: dict[str, dict] = {
    "basico": {
        "max_medicos": 1,
        "max_consultas_mes": 100,
        "whatsapp": False,
        "canais": ["PORTAL", "INTERNO"],
    },
    "pro": {
        "max_medicos": 10,
        "max_consultas_mes": 1000,
        "whatsapp": True,
        "canais": ["PORTAL", "INTERNO", "WHATSAPP"],
    },
    "enterprise": {
        "max_medicos": None,  # ilimitado
        "max_consultas_mes": None,  # ilimitado
        "whatsapp": True,
        "canais": ["PORTAL", "INTERNO", "WHATSAPP"],
    },
}

# Precos por modelo (USD por token)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "llama3.1:8b": {"input": 0.0, "output": 0.0},
    "cniongolo/biomistral:latest": {"input": 0.0, "output": 0.0},
    "nomic-embed-text": {"input": 0.0, "output": 0.0},
}

# Features para billing
FEATURES: list[str] = ["TRIAGEM", "AGENDAMENTO", "RAG", "RESUMO", "GERAL"]

# Deteccao de emergencia — prioridade absoluta
EMERGENCY_KEYWORDS: list[str] = [
    "dor no peito",
    "falta de ar",
    "nao consigo respirar",
    "desmaiei",
    "perda de consciencia",
    "paralisia",
    "AVC",
    "derrame",
    "convulsao",
    "sangramento intenso",
]


