"""
Mesma filosofia de tests/test_isolation.py, mas para o provider
Kubernetes (Fase 4): validamos os manifests gerados sem precisar de um
cluster real.
"""
import pytest

from app.providers.kubernetes_provider import (
    PLATFORM_NAMESPACE,
    K8sProvisionRequest,
    assert_pod_never_targets_platform_namespace,
    build_namespace_manifest,
    build_network_policy_manifest,
    build_pod_manifest,
)


def make_request(**overrides):
    defaults = dict(lab_instance_id="k8s-instance-123", image="vantage-range/web-fundamentals:latest")
    defaults.update(overrides)
    return K8sProvisionRequest(**defaults)


def test_pod_never_scheduled_in_platform_namespace():
    pod = build_pod_manifest(make_request())
    assert pod["metadata"]["namespace"] != PLATFORM_NAMESPACE
    assert pod["metadata"]["namespace"] == "vantage-lab-k8s-instance-123"


def test_assert_blocks_platform_namespace_violation():
    pod = build_pod_manifest(make_request())
    pod["metadata"]["namespace"] = PLATFORM_NAMESPACE
    with pytest.raises(RuntimeError, match="SECURITY VIOLATION"):
        assert_pod_never_targets_platform_namespace(pod)


def test_pod_uses_hardened_runtime_class():
    pod = build_pod_manifest(make_request())
    assert pod["spec"]["runtimeClassName"] == "gvisor"


def test_pod_does_not_automount_service_account_token():
    """
    Crítico: sem isso, qualquer processo dentro do pod de lab poderia
    chamar a API do Kubernetes com as permissões da ServiceAccount do
    namespace — um vetor de lateral movement totalmente diferente (e tão
    perigoso quanto) o escape de container.
    """
    pod = build_pod_manifest(make_request())
    assert pod["spec"]["automountServiceAccountToken"] is False


def test_pod_container_security_context_is_hardened():
    container = build_pod_manifest(make_request())["spec"]["containers"][0]
    ctx = container["securityContext"]
    assert ctx["runAsNonRoot"] is True
    assert ctx["allowPrivilegeEscalation"] is False
    assert ctx["readOnlyRootFilesystem"] is True
    assert ctx["capabilities"]["drop"] == ["ALL"]
    assert ctx["seccompProfile"]["type"] == "RuntimeDefault"


def test_pod_has_resource_limits():
    container = build_pod_manifest(make_request(cpu_limit="2.0", memory_limit="1Gi"))["spec"]["containers"][0]
    assert container["resources"]["limits"]["cpu"] == "2.0"
    assert container["resources"]["limits"]["memory"] == "1Gi"
    # requests == limits de propósito: evita "burst" imprevisível de CPU/RAM
    # que dificultaria o bin-packing do cluster e abriria brecha para
    # nós ficarem sobrecarregados por labs "educados" na superfície mas
    # gulosos por baixo.
    assert container["resources"]["requests"] == container["resources"]["limits"]


def test_pod_has_active_deadline_matching_ttl():
    pod = build_pod_manifest(make_request(ttl_minutes=30))
    assert pod["spec"]["activeDeadlineSeconds"] == 30 * 60


def test_network_policy_denies_egress_by_default_except_dns():
    netpol = build_network_policy_manifest("k8s-instance-123")
    egress_rules = netpol["spec"]["egress"]
    assert len(egress_rules) == 1
    ports = egress_rules[0]["ports"]
    allowed_ports = {(p["protocol"], p["port"]) for p in ports}
    assert allowed_ports == {("UDP", 53), ("TCP", 53)}  # só DNS


def test_network_policy_ingress_only_from_session_gateway():
    netpol = build_network_policy_manifest("k8s-instance-123")
    ingress_rules = netpol["spec"]["ingress"]
    selector = ingress_rules[0]["from"][0]["namespaceSelector"]["matchLabels"]
    assert selector == {"vantage.io/role": "session-gateway"}


def test_each_lab_instance_gets_dedicated_namespace():
    ns_a = build_namespace_manifest("instance-A")
    ns_b = build_namespace_manifest("instance-B")
    assert ns_a["metadata"]["name"] != ns_b["metadata"]["name"]


def test_kubernetes_orchestrator_fails_safely_without_cluster():
    from app.providers.kubernetes_provider import KubernetesOrchestrator

    orch = KubernetesOrchestrator()
    orch.client = None

    with pytest.raises(RuntimeError):
        orch.provision(make_request())
