from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import sessionmaker

from app.models import LabInstance, LabInstanceStatus, Organization, RoleName, User
from app.security import hash_password
from app.worker import expire_overdue_instances
from tests.conftest import FakeOrchestrator


def make_session(db_engine):
    return sessionmaker(bind=db_engine)()


def create_user_and_instance(db_engine, *, status: LabInstanceStatus, expires_at, with_container=True):
    session = make_session(db_engine)
    org = Organization(name="worker-test-org")
    session.add(org)
    session.commit()
    session.refresh(org)

    user = User(
        email="workeruser@example.com",
        password_hash=hash_password("StrongPass123!"),
        role=RoleName.STUDENT,
        organization_id=org.id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    instance = LabInstance(
        lab_id="fake-lab-id",
        user_id=user.id,
        status=status,
        expires_at=expires_at,
        container_id="fake-container-1" if with_container else None,
        network_namespace="lab-net-fake-1",
    )
    session.add(instance)
    session.commit()
    session.refresh(instance)
    session.close()
    return instance.id


def test_expires_overdue_running_instance(db_engine):
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    instance_id = create_user_and_instance(db_engine, status=LabInstanceStatus.RUNNING, expires_at=past)

    session = make_session(db_engine)
    count = expire_overdue_instances(session, FakeOrchestrator())
    assert count == 1

    updated = session.query(LabInstance).filter(LabInstance.id == instance_id).first()
    assert updated.status == LabInstanceStatus.EXPIRED
    assert updated.destroyed_at is not None
    session.close()


def test_does_not_expire_instance_still_within_ttl(db_engine):
    future = datetime.now(timezone.utc) + timedelta(minutes=30)
    instance_id = create_user_and_instance(db_engine, status=LabInstanceStatus.RUNNING, expires_at=future)

    session = make_session(db_engine)
    count = expire_overdue_instances(session, FakeOrchestrator())
    assert count == 0

    updated = session.query(LabInstance).filter(LabInstance.id == instance_id).first()
    assert updated.status == LabInstanceStatus.RUNNING
    session.close()


def test_does_not_touch_already_destroyed_instance(db_engine):
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    instance_id = create_user_and_instance(
        db_engine, status=LabInstanceStatus.DESTROYED, expires_at=past
    )

    session = make_session(db_engine)
    count = expire_overdue_instances(session, FakeOrchestrator())
    assert count == 0  # já destruído manualmente, worker não mexe de novo

    updated = session.query(LabInstance).filter(LabInstance.id == instance_id).first()
    assert updated.status == LabInstanceStatus.DESTROYED
    session.close()


def test_worker_is_resilient_to_orchestrator_failure(db_engine):
    """
    Se o daemon/cluster estiver indisponível no momento da expiração, o
    worker ainda deve marcar a instância como EXPIRED no banco — caso
    contrário, um problema de infraestrutura temporário deixaria
    registros "running" para sempre, mascarando o real estado do mundo.
    """

    class BrokenOrchestrator(FakeOrchestrator):
        def destroy(self, container_id, network_name=None):
            raise RuntimeError("infra indisponível")

    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    instance_id = create_user_and_instance(db_engine, status=LabInstanceStatus.RUNNING, expires_at=past)

    session = make_session(db_engine)
    count = expire_overdue_instances(session, BrokenOrchestrator())
    assert count == 1

    updated = session.query(LabInstance).filter(LabInstance.id == instance_id).first()
    assert updated.status == LabInstanceStatus.EXPIRED
    session.close()
