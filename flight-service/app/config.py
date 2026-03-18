from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    grpc_port: int = 50051
    redis_master_name: str = "mymaster"
    redis_sentinel_hosts: str = "localhost:26379"  # comma-separated host:port
    redis_password: str = ""
    api_key: str
    cache_ttl: int = 600  # 10 minutes

    class Config:
        env_file = ".env"


settings = Settings()
