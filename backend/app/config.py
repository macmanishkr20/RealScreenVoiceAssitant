from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_API_VERSION: str = "2025-04-01-preview"
    AZURE_OPENAI_DEPLOYMENT_GPT5: str = "gpt-5"
    AZURE_OPENAI_DEPLOYMENT_GPT5_MINI: str = "gpt-5-mini"
    AZURE_OPENAI_DEPLOYMENT_EMBEDDINGS: str = "text-embedding-3-large"

    AZURE_SPEECH_KEY: str = ""
    AZURE_SPEECH_REGION: str = "eastus"
    AZURE_SPEECH_VOICE: str = "en-US-AvaMultilingualNeural"

    COSMOS_ENDPOINT: str = ""
    COSMOS_KEY: str = ""
    COSMOS_DATABASE: str = "assistant"

    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    SESSION_TOKEN: str = "local-dev-token"

    FRAME_FPS_MAX: float = 1.0
    FRAME_DIFF_THRESHOLD: float = 0.05
    FRAME_MAX_SIDE_PX: int = 512
    FRAME_JPEG_QUALITY: int = 70
    VAD_AGGRESSIVENESS: int = 2
    HISTORY_WINDOW_TOKENS: int = 4000


settings = Settings()
