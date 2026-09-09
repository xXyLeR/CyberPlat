"""
Range Orchestrator — único componente autorizado a criar/destruir
containers de laboratório.

Decisão de arquitetura importante: a função `build_container_config` é
PURA (não toca Docker, não tem side-effects) e retorna apenas o
dicionário de configuração que seria enviado à Docker Engine API. Isso
permite testar exaustivamente as regras de segurança (cap_drop, resource
limits, network isolation) sem precisar de um daemon Docker real rodando
— e é exatamente isso que os testes em tests/test_isolation.py fazem.

A função `provision_lab_instance` é a que efetivamente chama o Docker SDK
em produção. No MVP local ela usa Docker Compose/Engine; na Fase 4 é
substituída por chamadas ao Kubernetes API com runtimeClassName: gvisor
(ver docs/architecture para o desenho de like-for-like em K8s).

Todo o hardening abaixo implementa as mitigações descritas na seção 6.2
do documento de arquitetura da Fase 1 (escape de container, abuso de
recursos, pivoting de rede, acesso a secrets, etc).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.config import get_settings

settings = get_settings()

# Nome da rede Docker usada pelo host da plataforma — o container de lab
# NUNCA deve ser anexado a essa rede.
PLATFORM_NETWORK_NAME = "vantage-range-platform-net"


@dataclass
class ProvisionRequest:
    lab_instance_id: str
    image: str
    cpu_limit: str = settings.lab_cpu_limit
    memory_limit: str = settings.lab_memory_limit
    pids_limit: int = settings.lab_pids_limit
    ttl_minutes: int = settings.lab_default_ttl_minutes


def build_network_name(lab_instance_id: str) -> str:
    # Rede dedicada e efêmera por instância — nunca compartilhada entre
    # alunos, nunca reaproveitada.
    return f"lab-net-{lab_instance_id}"


def build_container_config(req: ProvisionRequest) -> dict[str, Any]:
    """
    Monta a configuração de container com todo o hardening de segurança
    obrigatório. Retorna um dict no formato aceito pelo Docker SDK
    (`docker.client.containers.run(**config)` faria `client.containers.run(
    image=config["image"], **{k: v for k, v in config.items() if k != "image"})`).
    """
    network_name = build_network_name(req.lab_instance_id)

    config: dict[str, Any] = {
        "image": req.image,
        "name": f"lab-{req.lab_instance_id}",
        "detach": True,
        # --- Isolamento de rede ---
        # Rede dedicada e isolada; NUNCA conectada à rede da plataforma.
        "network": network_name,
        "network_disabled": False,
        # --- Privilégios ---
        "privileged": False,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "user": "1000:1000",  # non-root dentro do container
        "read_only": True,
        # nosec B108: isto NÃO é um uso inseguro de diretório temporário
        # compartilhado — é o padrão de hardening recomendado: /tmp
        # montado como tmpfs próprio do container, isolado, com
        # noexec+nosuid (não pode ser usado para persistir e executar um
        # binário). Bandit sinaliza qualquer string "/tmp" genericamente.
        "tmpfs": {"/tmp": "rw,noexec,nosuid,size=64m"},  # nosec B108
        # --- Resource limits (anti fork-bomb / cryptomining / DoS) ---
        "nano_cpus": int(float(req.cpu_limit) * 1_000_000_000),
        "mem_limit": req.memory_limit,
        "memswap_limit": req.memory_limit,  # impede swap para burlar mem_limit
        "pids_limit": req.pids_limit,
        # --- Efemeridade ---
        "auto_remove": False,  # removido explicitamente pelo orchestrator (auditável)
        "labels": {
            "vantage.lab_instance_id": req.lab_instance_id,
            "vantage.ttl_minutes": str(req.ttl_minutes),
            "vantage.managed": "true",
        },
    }
    return config


def build_network_config(lab_instance_id: str) -> dict[str, Any]:
    """
    Rede Docker isolada por lab instance:
    - `internal=True` faz o Docker NÃO configurar rota de saída via NAT
      para fora do host, a menos que explicitamente liberado.
    - Nenhuma ligação com PLATFORM_NETWORK_NAME.
    Em produção (Kubernetes), o equivalente é uma NetworkPolicy Cilium
    com egress default-deny + DNS interno restrito (ver seção 6 da
    arquitetura Fase 1).
    """
    return {
        "name": build_network_name(lab_instance_id),
        "driver": "bridge",
        "internal": True,  # sem egress para internet real por padrão
        "labels": {"vantage.lab_instance_id": lab_instance_id, "vantage.managed": "true"},
    }


def assert_never_touches_platform_network(config: dict[str, Any]) -> None:
    """Guard-rail explícito, usado tanto em runtime quanto em teste."""
    if config.get("network") == PLATFORM_NETWORK_NAME:
        raise RuntimeError(
            "SECURITY VIOLATION: tentativa de conectar container de lab "
            "à rede da plataforma foi bloqueada"
        )


class RangeOrchestrator:
    """
    Wrapper fino sobre o Docker SDK. Em ambientes sem Docker disponível
    (como este sandbox de desenvolvimento), `self.client` é None e os
    métodos de execução real levantam RuntimeError — mas a construção de
    configuração (testável) funciona sempre.
    """

    def __init__(self) -> None:
        try:
            import docker  # import local: dependência pesada, só carrega se necessário

            self.client = docker.from_env()
        except Exception:
            self.client = None

    def provision(self, req: ProvisionRequest) -> dict[str, Any]:
        network_cfg = build_network_config(req.lab_instance_id)
        container_cfg = build_container_config(req)
        assert_never_touches_platform_network(container_cfg)

        if self.client is None:
            raise RuntimeError(
                "Docker daemon não disponível neste ambiente — "
                "provisionamento real requer host com Docker Engine"
            )

        network = self.client.networks.create(**network_cfg)
        container = self.client.containers.run(
            image=container_cfg.pop("image"),
            network=network.name,
            **{k: v for k, v in container_cfg.items() if k not in ("network",)},
        )
        return {"container_id": container.id, "network_name": network.name}

    def destroy(self, container_id: str, network_name: str | None = None) -> None:
        if self.client is None:
            raise RuntimeError("Docker daemon não disponível neste ambiente")
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=True)
        finally:
            if network_name:
                try:
                    self.client.networks.get(network_name).remove()
                except Exception as exc:
                    # Não relança — a prioridade é garantir que o
                    # container em si foi removido (já aconteceu acima).
                    # Mas a falha É registrada, nunca engolida em
                    # silêncio: uma rede órfã que não pôde ser limpa é
                    # exatamente o tipo de coisa que precisa aparecer em
                    # log para investigação, mesmo não sendo motivo para
                    # derrubar a operação de destroy inteira.
                    import logging

                    logging.getLogger(__name__).warning(
                        "Falha ao remover rede %s durante destroy: %s", network_name, exc
                    )


_orchestrator_singleton: "object | None" = None


def get_orchestrator():
    """
    FastAPI dependency — permite override em testes (injeção de fake).

    A escolha do provider (Docker local vs Kubernetes) é 100% baseada em
    `settings.range_provider`. O restante da aplicação (routers) nunca
    precisa saber qual dos dois está ativo — ambos expõem a mesma
    interface: `.provision(req) -> {"container_id", "network_name"}` e
    `.destroy(container_id, network_name)`.
    """
    global _orchestrator_singleton
    if _orchestrator_singleton is None:
        if settings.range_provider == "kubernetes":
            from app.providers.kubernetes_provider import KubernetesOrchestrator

            _orchestrator_singleton = KubernetesOrchestrator()
        else:
            _orchestrator_singleton = RangeOrchestrator()
    return _orchestrator_singleton


def generate_session_token() -> str:
    # Token efêmero de sessão única usado pelo Session Gateway — não é o
    # JWT do usuário, é um token à parte com escopo mínimo (acesso a UMA
    # lab instance específica, por tempo limitado).
    return uuid.uuid4().hex
