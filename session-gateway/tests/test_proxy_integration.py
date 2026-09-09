from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as main_module
from app.database import SessionLocal
from app.models import STATUS_RUNNING, Base, Lab, LabInstance
from tests.conftest import FakeContainer, FakeDockerClient


def setup_module(_module):
    Base.metadata.create_all(bind=SessionLocal().get_bind())


def seed_running_instance():
    db = SessionLocal()
    lab = Lab(
        id="lab-proxy-test",
        definition={"machines": [{"name": "web01", "image": "x", "ports": [8080]}]},
    )
    instance = LabInstance(
        id="inst-proxy-test",
        lab_id="lab-proxy-test",
        user_id="user-1",
        status=STATUS_RUNNING,
        network_namespace="lab-net-inst-proxy-test",
        container_id="container-proxy-test",
        access_token="valid-token-xyz",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db.merge(lab)
    db.merge(instance)
    db.commit()
    db.close()


def test_proxy_rejects_invalid_token():
    seed_running_instance()
    client = TestClient(main_module.app)
    r = client.get("/session-gateway/inst-proxy-test/profile/1?token=wrong")
    assert r.status_code == 403


def test_proxy_forwards_request_and_returns_upstream_response():
    seed_running_instance()

    fake_docker = FakeDockerClient(
        {"container-proxy-test": FakeContainer({"lab-net-inst-proxy-test": {"IPAddress": "172.30.0.9"}})}
    )

    class FakeUpstreamResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b'{"username": "alice"}'

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def request(self, method, url, **kwargs):
            # Verifica que o proxy resolveu o IP real do container (nunca
            # expõe isso ao cliente, mas internamente tem que estar certo).
            assert url == "http://172.30.0.9:8080/profile/1"
            assert method == "GET"
            return FakeUpstreamResponse()

    with patch.object(main_module, "get_docker_client", return_value=fake_docker), \
         patch("app.main.httpx.AsyncClient", FakeAsyncClient):
        client = TestClient(main_module.app)
        r = client.get("/session-gateway/inst-proxy-test/profile/1?token=valid-token-xyz")

    assert r.status_code == 200
    assert r.json() == {"username": "alice"}


def test_proxy_never_leaks_token_to_upstream_query_params():
    seed_running_instance()
    fake_docker = FakeDockerClient(
        {"container-proxy-test": FakeContainer({"lab-net-inst-proxy-test": {"IPAddress": "172.30.0.9"}})}
    )

    captured = {}

    class FakeUpstreamResponse:
        status_code = 200
        headers = {}
        content = b"ok"

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def request(self, method, url, **kwargs):
            captured["params"] = kwargs.get("params")
            return FakeUpstreamResponse()

    with patch.object(main_module, "get_docker_client", return_value=fake_docker), \
         patch("app.main.httpx.AsyncClient", FakeAsyncClient):
        client = TestClient(main_module.app)
        client.get("/session-gateway/inst-proxy-test/profile/1?token=valid-token-xyz&foo=bar")

    assert "token" not in captured["params"]
    assert captured["params"]["foo"] == "bar"
