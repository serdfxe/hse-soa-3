from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    flight_service_url: str = "localhost:50051"
    flight_service_api_key: str
    # Circuit breaker config
    cb_failure_threshold: int = 5
    cb_timeout: float = 30.0
    cb_half_open_timeout: float = 60.0

    class Config:
        env_file = ".env"


settings = Settings()
