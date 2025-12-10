from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    cdek_client_id: str
    cdek_client_secret: str
    cdek_api_url: str
    database_url: str
    
    class Config:
        env_file = ".env"


settings = Settings()
