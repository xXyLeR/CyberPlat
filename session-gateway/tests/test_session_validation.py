from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.main import _validate_session
from app.models import STATUS_RUNNING, LabInstance


def make_instance(db_session, **overrides):
    defaults = dict(
        id="inst-1",
        lab_id="lab-1",
        user_id="user-1",
        status=STATUS_RUNNING,
        network_namespace="lab-net-inst-1",
        container_id="container-1",
        access_token="secret-token-abc",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    defaults.update(overrides)
    instance = LabInstance(**defaults)
    db_session.add(instance)
    db_session.commit()
    return instance


def test_valid_session_passes(db_session):
    make_instance(db_session)
    instance = _validate_session(db_session, "inst-1", "secret-token-abc")
    assert instance.id == "inst-1"


def test_wrong_token_rejected(db_session):
    make_instance(db_session)
    with pytest.raises(HTTPException) as exc_info:
        _validate_session(db_session, "inst-1", "wrong-token")
    assert exc_info.value.status_code == 403


def test_missing_token_rejected(db_session):
    make_instance(db_session)
    with pytest.raises(HTTPException) as exc_info:
        _validate_session(db_session, "inst-1", None)
    assert exc_info.value.status_code == 403


def test_nonexistent_instance_returns_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        _validate_session(db_session, "does-not-exist", "any-token")
    assert exc_info.value.status_code == 404


def test_non_running_instance_rejected(db_session):
    make_instance(db_session, status="DESTROYED")
    with pytest.raises(HTTPException) as exc_info:
        _validate_session(db_session, "inst-1", "secret-token-abc")
    assert exc_info.value.status_code == 410


def test_expired_instance_rejected_even_if_status_still_says_running(db_session):
    """
    Defesa em profundidade: mesmo que o worker de expiração (Fase 4)
    ainda não tenha rodado e o status no banco ainda diga RUNNING, o
    Session Gateway checa `expires_at` independentemente — nunca confia
    em um único sinal para decidir se uma sessão é válida.
    """
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    make_instance(db_session, expires_at=past)
    with pytest.raises(HTTPException) as exc_info:
        _validate_session(db_session, "inst-1", "secret-token-abc")
    assert exc_info.value.status_code == 410


def test_instance_without_expiry_set_is_not_rejected_for_expiry(db_session):
    make_instance(db_session, expires_at=None)
    instance = _validate_session(db_session, "inst-1", "secret-token-abc")
    assert instance.id == "inst-1"
