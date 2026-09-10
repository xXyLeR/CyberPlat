"""
Configuração do Session Gateway.

Decisão: este serviço lê a MESMA base de dados do core-api (via
DATABASE_URL), mas nunca escreve nela — só SELECT em LabInstance/Lab
(ver app/models.py, que define as tabelas como somente-leitura por
convenção de uso, já que o schema real é gerenciado pelo core-api).
Isso mantém o Session Gateway como um componente de baixo privilégio:
mesmo que ele seja comprometido, um atacante não consegue escalar para
criar/destruir labs (isso é privilégio exclusivo do Range Orchestrator,
rodando como processo/serviceaccount separado).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///../core-api/dev.db"
    lab_default_port: int = 8080
    proxy_request_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(env_file=".env")


def get_settings() -> Settings:
    return Settings()
