import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class FakeContainer:
    def __init__(self, networks: dict):
        self.attrs = {"NetworkSettings": {"Networks": networks}}


class FakeDockerClient:
    def __init__(self, containers: dict):
        self._containers = containers

    class _Containers:
        def __init__(self, outer):
            self.outer = outer

        def get(self, container_id):
            if container_id not in self.outer._containers:
                raise KeyError(container_id)
            return self.outer._containers[container_id]

    @property
    def containers(self):
        return FakeDockerClient._Containers(self)
