from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import get_db
from app.deps import require_super_admin
from app.models import Organization, User
from app.schemas import OrganizationCreateRequest, OrganizationOut

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationOut, status_code=201)
def create_organization(
    payload: OrganizationCreateRequest,
    db: Session = Depends(get_db),
    super_admin: User = Depends(require_super_admin),
):
    # Só super_admin cria novas organizações — org_admin administra a
    # própria organização, mas não pode criar outras do zero (isso seria
    # efetivamente um upgrade de plano/tenant novo, decisão de negócio
    # que fica acima do escopo de um admin de organização).
    existing = db.query(Organization).filter(Organization.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Já existe uma organização com esse nome")

    org = Organization(name=payload.name, plan_tier=payload.plan_tier)
    db.add(org)
    db.commit()
    db.refresh(org)

    log_action(
        db, actor_user_id=super_admin.id, action="organization_created",
        resource_type="organization", resource_id=org.id,
    )
    return org


@router.get("", response_model=list[OrganizationOut])
def list_organizations(
    db: Session = Depends(get_db), super_admin: User = Depends(require_super_admin)
):
    return db.query(Organization).all()
