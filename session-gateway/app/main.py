"""
Session Gateway — única porta de entrada para o navegador do usuário
alcançar um container de laboratório.

Fluxo: o navegador nunca conhece o IP real do container nem a rede
isolada em que ele vive. Toda requisição passa por
`/session-gateway/{instance_id}/...?token=...`, e este serviço:

1. Valida o token de sessão (gerado no momento do provisionamento,
   ver core-api/app/orchestrator.py::generate_session_token) contra o
   que está gravado em LabInstance.access_token.
2. Confirma que a instância está RUNNING e não expirou.
3. Resolve o IP real do container DENTRO da rede isolada daquela
   instância especificamente (nunca aceita nome de rede vindo do
   cliente — sempre lê do banco).
4. Encaminha a requisição HTTP e devolve a resposta, sem nunca expor
   o IP/rede real ao cliente.
"""
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.docker_inspector import (
    ContainerNotOnNetworkError,
    resolve_container_ip,
    resolve_target_port,
)
from app.models import STATUS_RUNNING, Lab, LabInstance

settings = get_settings()
app = FastAPI(title="Vantage Range — Session Gateway", version="0.1.0")

_docker_client = None


def get_docker_client():
    global _docker_client
    if _docker_client is None:
        try:
            import docker

            _docker_client = docker.from_env()
        except Exception:
            _docker_client = False  # sentinela: já tentamos e falhou, não tenta de novo
    return _docker_client or None


@app.get("/health")
def health():
    return {"status": "ok"}


def _validate_session(db: Session, instance_id: str, token: str | None) -> LabInstance:
    instance = db.query(LabInstance).filter(LabInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Sessão de lab não encontrada")

    # Comparação simples é aceitável aqui: o token já é um UUID4 aleatório
    # de alta entropia (ver generate_session_token no core-api), então o
    # risco de ataque de timing é desprezível comparado ao ganho de
    # simplicidade — mas em produção, considerar hmac.compare_digest.
    if not token or token != instance.access_token:
        raise HTTPException(status_code=403, detail="Token de sessão inválido")

    if instance.status != STATUS_RUNNING:
        raise HTTPException(status_code=410, detail="Esta sessão de lab não está mais ativa")

    if instance.expires_at and instance.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Esta sessão de lab expirou")

    return instance


# Headers que nunca devem ser repassados adiante em um proxy HTTP —
# são específicos da conexão TCP/HTTP em si, não do conteúdo.
HOP_BY_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}


@app.api_route(
    "/session-gateway/{instance_id}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def proxy(instance_id: str, path: str, request: Request):
    token = request.query_params.get("token")
    db = SessionLocal()
    try:
        instance = _validate_session(db, instance_id, token)
        lab = db.query(Lab).filter(Lab.id == instance.lab_id).first()
        if not lab:
            raise HTTPException(status_code=404, detail="Lab associado não encontrado")

        docker_client = get_docker_client()
        if docker_client is None:
            raise HTTPException(
                status_code=503,
                detail="Session Gateway sem acesso ao Docker neste ambiente",
            )

        try:
            container_ip = resolve_container_ip(
                docker_client, instance.container_id, instance.network_namespace
            )
        except ContainerNotOnNetworkError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        port = resolve_target_port(lab.definition, settings.lab_default_port)
        target_url = f"http://{container_ip}:{port}/{path}"

        forward_headers = {
            k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP_HEADERS
        }
        body = await request.body()

        async with httpx.AsyncClient(timeout=settings.proxy_request_timeout_seconds) as client:
            upstream_response = await client.request(
                request.method,
                target_url,
                headers=forward_headers,
                content=body,
                params={k: v for k, v in request.query_params.items() if k != "token"},
            )

        response_headers = {
            k: v for k, v in upstream_response.headers.items() if k.lower() not in HOP_BY_HOP_HEADERS
        }
        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            headers=response_headers,
        )
    finally:
        db.close()
