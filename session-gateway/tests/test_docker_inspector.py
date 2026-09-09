import pytest

from app.docker_inspector import (
    ContainerNotOnNetworkError,
    resolve_container_ip,
    resolve_target_port,
)
from tests.conftest import FakeContainer, FakeDockerClient


def test_resolve_container_ip_success():
    client = FakeDockerClient(
        {"c1": FakeContainer({"lab-net-c1": {"IPAddress": "172.20.0.5"}})}
    )
    ip = resolve_container_ip(client, "c1", "lab-net-c1")
    assert ip == "172.20.0.5"


def test_resolve_container_ip_wrong_network_raises():
    client = FakeDockerClient(
        {"c1": FakeContainer({"some-other-network": {"IPAddress": "172.20.0.5"}})}
    )
    with pytest.raises(ContainerNotOnNetworkError):
        resolve_container_ip(client, "c1", "lab-net-c1")


def test_resolve_container_ip_still_provisioning_raises():
    # Container existe mas ainda não tem IP atribuído na rede (corrida
    # entre "container criado" e "rede totalmente configurada").
    client = FakeDockerClient({"c1": FakeContainer({"lab-net-c1": {"IPAddress": ""}})})
    with pytest.raises(ContainerNotOnNetworkError):
        resolve_container_ip(client, "c1", "lab-net-c1")


def test_resolve_target_port_from_definition():
    definition = {"machines": [{"name": "web01", "image": "x", "ports": [9090]}]}
    assert resolve_target_port(definition, default_port=8080) == 9090


def test_resolve_target_port_falls_back_to_default():
    definition = {"machines": [{"name": "web01", "image": "x"}]}
    assert resolve_target_port(definition, default_port=8080) == 8080


def test_resolve_target_port_no_machines_falls_back_to_default():
    assert resolve_target_port({"machines": []}, default_port=8080) == 8080
