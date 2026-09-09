"""
Provider Kubernetes do Range Orchestrator (Fase 4).

Mesma filosofia do provider Docker (app/orchestrator.py): as funções que
montam manifests são PURAS (não tocam a API do cluster), para que todo o
hardening de segurança seja testável sem precisar de um cluster real.

Diferenças de hardening em relação ao Docker Compose local (Fase 2):

1. `runtimeClassName: gvisor` — o pod roda sob um kernel de usuário
   sandboxed (gVisor) em vez do runc padrão, que compartilha o kernel do
   host diretamente. Isso é a mitigação mais forte contra escape de
   container disponível hoje sem ir para VMs completas.
2. `automountServiceAccountToken: false` — o pod NUNCA recebe o token da
   ServiceAccount do namespace. Sem isso, qualquer processo dentro do
   pod poderia, em tese, chamar a API do Kubernetes com as permissões
   daquele namespace (risco de lateral movement via API do próprio
   cluster, não só de rede).
3. Namespace dedicado e efêmero por lab instance — o equivalente
   Kubernetes da rede Docker isolada. Uma NetworkPolicy default-deny
   é aplicada a esse namespace (ver `build_network_policy_manifest`).
4. `seccompProfile: RuntimeDefault` — perfil seccomp do próprio
   Kubernetes, reduz ainda mais a superfície de syscalls permitidas
   mesmo dentro do sandbox do gVisor (defesa em profundidade, não
   redundância inútil: gVisor intercepta syscalls, seccomp as filtra
   antes mesmo de chegar lá).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import get_settings

settings = get_settings()

PLATFORM_NAMESPACE = settings.k8s_platform_namespace


@dataclass
class K8sProvisionRequest:
    lab_instance_id: str
    image: str
    cpu_limit: str = settings.lab_cpu_limit
    memory_limit: str = settings.lab_memory_limit
    ttl_minutes: int = settings.lab_default_ttl_minutes


def build_namespace_name(lab_instance_id: str) -> str:
    return f"{settings.k8s_namespace_prefix}{lab_instance_id}"


def build_pod_name(lab_instance_id: str) -> str:
    return f"lab-{lab_instance_id}"


def build_namespace_manifest(lab_instance_id: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": build_namespace_name(lab_instance_id),
            "labels": {
                "vantage.io/managed": "true",
                "vantage.io/lab-instance-id": lab_instance_id,
            },
        },
    }


def build_network_policy_manifest(lab_instance_id: str) -> dict[str, Any]:
    """
    Egress default-deny total, exceto DNS interno (porta 53/UDP) para o
    resolver do cluster — sem isso o pod não resolveria nem os poucos
    hostnames que porventura precisasse. Nenhuma outra saída é permitida:
    nem para a internet, nem para outros namespaces, nem para o
    namespace da plataforma. Ingress só é permitido a partir do Session
    Gateway (identificado pelo label `app: session-gateway`).
    """
    namespace = build_namespace_name(lab_instance_id)
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": "default-deny-with-dns", "namespace": namespace},
        "spec": {
            "podSelector": {},  # aplica a todos os pods do namespace
            "policyTypes": ["Ingress", "Egress"],
            "ingress": [
                {
                    "from": [
                        {
                            "namespaceSelector": {
                                "matchLabels": {"vantage.io/role": "session-gateway"}
                            }
                        }
                    ]
                }
            ],
            "egress": [
                {
                    "to": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}}}],
                    "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}],
                }
            ],
        },
    }


def build_pod_manifest(req: K8sProvisionRequest) -> dict[str, Any]:
    namespace = build_namespace_name(req.lab_instance_id)
    pod_name = build_pod_name(req.lab_instance_id)

    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": pod_name,
            "namespace": namespace,
            "labels": {"vantage.io/managed": "true", "vantage.io/lab-instance-id": req.lab_instance_id},
        },
        "spec": {
            "runtimeClassName": settings.k8s_runtime_class,
            "automountServiceAccountToken": False,
            "restartPolicy": "Never",
            "activeDeadlineSeconds": req.ttl_minutes * 60,  # kubelet mata o pod ao expirar
            "containers": [
                {
                    "name": "lab",
                    "image": req.image,
                    "resources": {
                        "limits": {"cpu": req.cpu_limit, "memory": req.memory_limit},
                        "requests": {"cpu": req.cpu_limit, "memory": req.memory_limit},
                    },
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 1000,
                        "allowPrivilegeEscalation": False,
                        "readOnlyRootFilesystem": True,
                        "capabilities": {"drop": ["ALL"]},
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "volumeMounts": [{"name": "tmp", "mountPath": "/tmp"}],  # nosec B108 - tmpfs isolado, ver volumes abaixo
                }
            ],
            "volumes": [
                {"name": "tmp", "emptyDir": {"sizeLimit": "64Mi"}}
            ],
        },
    }


def assert_pod_never_targets_platform_namespace(pod_manifest: dict[str, Any]) -> None:
    namespace = pod_manifest.get("metadata", {}).get("namespace")
    if namespace == PLATFORM_NAMESPACE:
        raise RuntimeError(
            "SECURITY VIOLATION: tentativa de agendar pod de lab no namespace "
            "da plataforma foi bloqueada"
        )


class KubernetesOrchestrator:
    """
    Wrapper fino sobre o cliente oficial do Kubernetes. Segue o mesmo
    padrão do RangeOrchestrator (Docker): `self.client is None` quando o
    cluster não está acessível (ex: rodando fora de um cluster, como
    neste ambiente de desenvolvimento), e a montagem de manifests
    (testável) funciona sempre, independente disso.
    """

    def __init__(self) -> None:
        try:
            from kubernetes import client, config as k8s_config  # import local

            try:
                k8s_config.load_incluster_config()
            except Exception:
                k8s_config.load_kube_config()
            self.client = client.CoreV1Api()
            self.networking_client = client.NetworkingV1Api()
        except Exception:
            self.client = None
            self.networking_client = None

    def provision(self, req: K8sProvisionRequest) -> dict[str, Any]:
        pod_manifest = build_pod_manifest(req)
        assert_pod_never_targets_platform_namespace(pod_manifest)
        ns_manifest = build_namespace_manifest(req.lab_instance_id)
        netpol_manifest = build_network_policy_manifest(req.lab_instance_id)

        if self.client is None:
            raise RuntimeError(
                "Cluster Kubernetes não disponível neste ambiente — "
                "provisionamento real requer execução dentro/perto de um cluster"
            )

        self.client.create_namespace(body=ns_manifest)
        self.networking_client.create_namespaced_network_policy(
            namespace=ns_manifest["metadata"]["name"], body=netpol_manifest
        )
        self.client.create_namespaced_pod(
            namespace=ns_manifest["metadata"]["name"], body=pod_manifest
        )
        return {
            "container_id": pod_manifest["metadata"]["name"],  # nome do pod
            "network_name": ns_manifest["metadata"]["name"],    # nome do namespace
        }

    def destroy(self, container_id: str, network_name: str | None = None) -> None:
        if self.client is None:
            raise RuntimeError("Cluster Kubernetes não disponível neste ambiente")
        if network_name:
            # Deletar o namespace já remove o pod e a NetworkPolicy junto
            # (garbage collection nativa do Kubernetes) — mais simples e
            # mais seguro do que deletar recurso por recurso.
            self.client.delete_namespace(name=network_name)
