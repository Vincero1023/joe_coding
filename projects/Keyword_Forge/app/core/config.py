from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "keyword_forge"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/keyword_forge"

    naver_ads_api_id: str | None = None
    naver_ads_customer_id: str | None = None
    naver_ads_access_license: str | None = None
    naver_ads_secret_key: str | None = None

    naver_search_client_id: str | None = None
    naver_search_client_secret: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
