from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import get_db
from app.deps import get_current_user, require_instructor_or_admin
from app.lab_schema import LabDefinitionError, validate_lab_definition
from app.models import Lab, User
from app.schemas import LabCreateRequest, LabOut
from app.security import sha256_hex
from app.models import Flag

router = APIRouter(prefix="/labs", tags=["labs"])


@router.post("", response_model=LabOut, status_code=201)
def create_lab(
    payload: LabCreateRequest,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor_or_admin),
):
    try:
        validate_lab_definition(payload.definition)
    except LabDefinitionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    existing = db.query(Lab).filter(Lab.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Slug já utilizado por outro lab")

    lab = Lab(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        category=payload.category,
        difficulty=payload.difficulty,
        estimated_minutes=payload.estimated_minutes,
        definition=payload.definition,
        status="published",
        created_by=instructor.id,
    )
    db.add(lab)
    db.commit()
    db.refresh(lab)

    # As flags reais nunca são armazenadas em texto puro — apenas o hash.
    for flag_def in payload.definition.get("flags", []):
        db.add(
            Flag(
                lab_id=lab.id,
                flag_key=flag_def["id"],
                flag_hash=sha256_hex(flag_def.get("value", flag_def["id"])),
                points=flag_def.get("points", 100),
            )
        )
    db.commit()

    log_action(
        db, actor_user_id=instructor.id, action="lab_created",
        resource_type="lab", resource_id=lab.id, metadata={"slug": lab.slug},
    )
    return lab


@router.get("", response_model=list[LabOut])
def list_labs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Lab).filter(Lab.status == "published").all()


@router.get("/{lab_id}", response_model=LabOut)
def get_lab(lab_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise HTTPException(status_code=404, detail="Lab não encontrado")
    return lab
