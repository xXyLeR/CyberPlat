"""
Resolve o endereço IP real de um container de lab dentro da sua rede
isolada, e a porta que a aplicação do lab expõe.

Decisão de segurança: o Session Gateway usa o cliente Docker SOMENTE
para operações de LEITURA (`containers.get` + `.attrs`, que é
equivalente a `docker inspect`) — nunca `create`, `run`, `remove` ou
qualquer operação de escrita. Em produção, isso é reforçado com um
"docker-socket-proxy" na frente do socket real, configurado para
permitir apenas GET (ver infra/docker-socket-proxy.md), já que montar o
socket Docker bruto não impõe granularidade de permissões por si só.
"""
from __future__ import annotations


class ContainerNotOnNetworkError(Exception):
    pass


def resolve_container_ip(docker_client, container_id: str, network_name: str) -> str:
    container = docker_client.containers.get(container_id)
    networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
    network_info = networks.get(network_name)
    if not network_info or not network_info.get("IPAddress"):
        raise ContainerNotOnNetworkError(
            f"Container {container_id} não está (ou ainda não terminou de subir) "
            f"na rede {network_name}"
        )
    return network_info["IPAddress"]


def resolve_target_port(lab_definition: dict, default_port: int) -> int:
    machines = lab_definition.get("machines", [])
    if not machines:
        return default_port
    ports = machines[0].get("ports", [])
    return ports[0] if ports else default_port
