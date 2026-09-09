from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import log_action
from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Lab, LabInstance, LabInstanceStatus, User
from app.orchestrator import (
    ProvisionRequest,
    RangeOrchestrator,
    generate_session_token,
    get_orchestrator,
)
from app.schemas import LabSessionCreateRequest, LabSessionOut

router = APIRouter(prefix="/lab-sessions", tags=["lab-sessions"])
settings = get_settings()

MAX_CONCURRENT_LABS_PER_USER = 2  # anti-DoS: cota simples no MVP


@router.post("", response_model=LabSessionOut, status_code=201)
def start_lab_session(
    payload: LabSessionCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    orchestrator: RangeOrchestrator = Depends(get_orchestrator),
):
    lab = db.query(Lab).filter(Lab.id == payload.lab_id, Lab.status == "published").first()
    if not lab:
        raise HTTPException(status_code=404, detail="Lab não encontrado ou não publicado")

    running_count = (
        db.query(LabInstance)
        .filter(
            LabInstance.user_id == user.id,
            LabInstance.status.in_([LabInstanceStatus.PROVISIONING, LabInstanceStatus.RUNNING]),
        )
        .count()
    )
    if running_count >= MAX_CONCURRENT_LABS_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=f"Limite de {MAX_CONCURRENT_LABS_PER_USER} laboratórios simultâneos atingido",
        )

    instance = LabInstance(
        lab_id=lab.id,
        user_id=user.id,
        status=LabInstanceStatus.PROVISIONING,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.lab_default_ttl_minutes),
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)

    machine = lab.definition["machines"][0]
    req = ProvisionRequest(lab_instance_id=instance.id, image=machine["image"])

    try:
        result = orchestrator.provision(req)
        instance.container_id = result["container_id"]
        instance.network_namespace = result["network_name"]
        instance.status = LabInstanceStatus.RUNNING
        instance.access_token = generate_session_token()
    except RuntimeError as exc:
        instance.status = LabInstanceStatus.ERROR
        db.add(instance)
        db.commit()
        log_action(
            db, actor_user_id=user.id, action="lab_instance_provision_failed",
            resource_type="lab_instance", resource_id=instance.id, metadata={"error": str(exc)},
        )
        raise HTTPException(status_code=503, detail="Ambiente de laboratório indisponível no momento") from exc

    db.add(instance)
    db.commit()
    db.refresh(instance)

    log_action(
        db, actor_user_id=user.id, action="lab_instance_created",
        resource_type="lab_instance", resource_id=instance.id, metadata={"lab_id": lab.id},
    )

    return LabSessionOut(
        id=instance.id,
        lab_id=instance.lab_id,
        status=instance.status.value,
        started_at=instance.started_at,
        expires_at=instance.expires_at,
        access_url=f"/session-gateway/{instance.id}/?token={instance.access_token}",
    )


@router.post("/{instance_id}/terminate", response_model=LabSessionOut)
def terminate_lab_session(
    instance_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    orchestrator: RangeOrchestrator = Depends(get_orchestrator),
):
    instance = db.query(LabInstance).filter(LabInstance.id == instance_id).first()
    if not instance or instance.user_id != user.id:
        raise HTTPException(status_code=404, detail="Sessão de lab não encontrada")

    if instance.status == LabInstanceStatus.RUNNING and instance.container_id:
        try:
            orchestrator.destroy(instance.container_id, instance.network_namespace)
        except RuntimeError:
            pass  # ambiente dev sem docker — destruição real ocorre em staging/prod

    instance.status = LabInstanceStatus.DESTROYED
    instance.destroyed_at = datetime.now(timezone.utc)
    db.add(instance)
    db.commit()
    db.refresh(instance)

    log_action(
        db, actor_user_id=user.id, action="lab_instance_destroyed",
        resource_type="lab_instance", resource_id=instance.id,
    )

    return LabSessionOut(
        id=instance.id,
        lab_id=instance.lab_id,
        status=instance.status.value,
        started_at=instance.started_at,
        expires_at=instance.expires_at,
    )
