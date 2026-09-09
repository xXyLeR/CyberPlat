import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.achievements import ensure_default_badges
from app.database import Base, get_db
from app.main import app
from app.orchestrator import ProvisionRequest, RangeOrchestrator, get_orchestrator
from app.rate_limit import reset_for_tests


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    # Badges default precisam existir também no banco de teste — a
    # chamada equivalente em app/main.py roda contra o banco de
    # produção/dev, não contra este engine efêmero em memória.
    TestingSessionLocal = sessionmaker(bind=engine)
    seed_session = TestingSessionLocal()
    ensure_default_badges(seed_session)
    seed_session.close()

    yield engine
    Base.metadata.drop_all(bind=engine)


class FakeOrchestrator(RangeOrchestrator):
    """
    Orchestrator fake para testes: NÃO usa Docker real, mas exercita as
    mesmas validações de segurança (build_container_config,
    assert_never_touches_platform_network) antes de "simular" o
    provisionamento. Isso garante que os testes de fluxo (start lab
    session) validam a mesma lógica de segurança que rodaria em produção.
    """

    def __init__(self):
        self.client = "fake"  # não None, para não cair no branch de erro

    def provision(self, req: ProvisionRequest):
        from app.orchestrator import (
            assert_never_touches_platform_network,
            build_container_config,
            build_network_config,
        )

        network_cfg = build_network_config(req.lab_instance_id)
        container_cfg = build_container_config(req)
        assert_never_touches_platform_network(container_cfg)
        return {"container_id": f"fake-container-{req.lab_instance_id}", "network_name": network_cfg["name"]}

    def destroy(self, container_id, network_name=None):
        return None


@pytest.fixture()
def client(db_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_orchestrator] = lambda: FakeOrchestrator()

    reset_for_tests()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def register_and_login(client, email="user@example.com", password="StrongPass123!"):
    client.post("/auth/register", json={"email": email, "password": password})
    resp = client.post("/auth/login", data={"username": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
