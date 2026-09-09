"""
Testes específicos de isolamento — validam que a configuração de
container gerada pelo orchestrator segue TODAS as regras de hardening
descritas na arquitetura (seção 6), sem depender de um Docker daemon
real (testamos a função pura `build_container_config`).
"""
import pytest

from app.orchestrator import (
    PLATFORM_NETWORK_NAME,
    ProvisionRequest,
    assert_never_touches_platform_network,
    build_container_config,
    build_network_config,
)


def make_request(**overrides):
    defaults = dict(
        lab_instance_id="instance-123",
        image="vantage-range/web-fundamentals:latest",
    )
    defaults.update(overrides)
    return ProvisionRequest(**defaults)


def test_container_never_uses_platform_network():
    config = build_container_config(make_request())
    assert config["network"] != PLATFORM_NETWORK_NAME
    assert config["network"] == "lab-net-instance-123"


def test_assert_never_touches_platform_network_blocks_violation():
    malicious_config = build_container_config(make_request())
    malicious_config["network"] = PLATFORM_NETWORK_NAME
    with pytest.raises(RuntimeError, match="SECURITY VIOLATION"):
        assert_never_touches_platform_network(malicious_config)


def test_container_has_no_privileges():
    config = build_container_config(make_request())
    assert config["privileged"] is False
    assert config["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in config["security_opt"]
    assert config["user"] == "1000:1000"


def test_container_filesystem_is_read_only():
    config = build_container_config(make_request())
    assert config["read_only"] is True
    # /tmp gravável, mas noexec+nosuid (não pode ser usado para persistir
    # e executar um binário malicioso).
    assert "noexec" in config["tmpfs"]["/tmp"]
    assert "nosuid" in config["tmpfs"]["/tmp"]


def test_container_has_resource_limits_to_prevent_abuse():
    config = build_container_config(make_request(cpu_limit="1.0", memory_limit="512m", pids_limit=100))
    assert config["nano_cpus"] == 1_000_000_000
    assert config["mem_limit"] == "512m"
    assert config["memswap_limit"] == "512m"  # sem swap extra além do limite (anti-bypass)
    assert config["pids_limit"] == 100  # anti fork-bomb


def test_container_is_not_auto_removed_for_auditability():
    config = build_container_config(make_request())
    # auto_remove=False de propósito: o orchestrator remove explicitamente
    # e registra em audit log, em vez de deixar o Docker remover "silenciosamente".
    assert config["auto_remove"] is False


def test_network_is_internal_no_default_egress():
    net_config = build_network_config("instance-456")
    assert net_config["internal"] is True
    assert net_config["name"] == "lab-net-instance-456"


def test_each_lab_instance_gets_a_unique_dedicated_network():
    net_a = build_network_config("instance-A")
    net_b = build_network_config("instance-B")
    assert net_a["name"] != net_b["name"]


def test_orchestrator_without_docker_daemon_fails_safely(monkeypatch):
    """
    Se o Docker daemon não estiver disponível (ex: falha de infra), o
    orchestrator deve falhar de forma segura (RuntimeError) em vez de
    silenciosamente pular o isolamento de rede/recursos.
    """
    from app.orchestrator import RangeOrchestrator

    orch = RangeOrchestrator()
    orch.client = None  # simula daemon indisponível

    with pytest.raises(RuntimeError):
        orch.provision(make_request())
