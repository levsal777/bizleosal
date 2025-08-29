from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    OPENAI_BASE_URL: Optional[str] = None  # по умолчанию официальный endpoint
    OPENAI_ORG: Optional[str] = None       # если используешь организации

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
