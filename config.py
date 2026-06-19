from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    BOT_TOKEN: str = Field(..., env="BOT_TOKEN")
    GROK_API_KEY: str = Field(..., env="GROK_API_KEY")
    GROQ_API_KEY: str = Field(..., env="GROQ_API_KEY")
    
    GROK_BASE_URL: str = Field("https://api.x.ai/v1", env="GROK_BASE_URL")
    GROQ_BASE_URL: str = Field("https://api.groq.com/openai/v1", env="GROQ_BASE_URL")
    
    MAX_PROMPT_LENGTH: int = 300
    DEFAULT_HISTORY_LENGTH: int = 8
    MAX_HISTORY_LENGTH: int = 12
    DEFAULT_LANGUAGE: str = "ru"
    DEFAULT_DELAY: int = 3  # секунды

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()