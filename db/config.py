from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_hostname: str
    database_port: str
    database_name: str
    database_password: str
    database_username: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    base_url: str
    target_url: str
    target_url_residential: str
    target_url_commercial: str
    city: str


    class Config:
        env_file=".env"
        env_file_encoding="utf-8"


settings = Settings()
