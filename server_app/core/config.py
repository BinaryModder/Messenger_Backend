from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    API_TITLE: str = "Cluster"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql://cluster_user:password@db:5432/clusterdb"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )


settings = Settings()
