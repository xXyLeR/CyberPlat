from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import get_db
from app.deps import get_current_user
from app.models import Course, Flag, LabInstance, LabInstanceStatus, Submission, User
from app.rate_limit import is_rate_limited
from app.schemas import SubmissionCreateRequest, SubmissionOut
from app.security import sha256_hex
from app.achievements import check_and_award_achievements, mark_course_completed_if_needed

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionOut, status_code=201)
def submit_flag(
    payload: SubmissionCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rate_key = f"{user.id}:{payload.lab_instance_id}"
    if is_rate_limited(rate_key):
        raise HTTPException(status_code=429, detail="Muitas tentativas — aguarde antes de tentar novamente")

    instance = db.query(LabInstance).filter(LabInstance.id == payload.lab_instance_id).first()
    if not instance or instance.user_id != user.id:
        raise HTTPException(status_code=404, detail="Sessão de lab não encontrada")

    if instance.status != LabInstanceStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Sessão de lab não está em execução")

    submitted_hash = sha256_hex(payload.flag_value.strip())

    matching_flag = (
        db.query(Flag)
        .filter(Flag.lab_id == instance.lab_id, Flag.flag_hash == submitted_hash)
        .first()
    )

    # Evita pontuação duplicada pela mesma flag na mesma instância.
    already_solved = None
    if matching_flag:
        already_solved = (
            db.query(Submission)
            .filter(
                Submission.lab_instance_id == instance.id,
                Submission.flag_id == matching_flag.id,
                Submission.correct == True,  # noqa: E712
            )
            .first()
        )

    correct = bool(matching_flag) and not already_solved
    points = matching_flag.points if correct else 0

    submission = Submission(
        user_id=user.id,
        lab_instance_id=instance.id,
        flag_id=matching_flag.id if matching_flag else None,
        submitted_value_hash=submitted_hash,
        correct=correct,
        points_awarded=points,
    )
    db.add(submission)

    if correct:
        user.xp += points
        user.level = 1 + user.xp // 500  # progressão simples de nível no MVP
        db.add(user)

    db.commit()
    db.refresh(submission)

    if correct:
        # Se algum curso de Learning Path usa este lab como critério de
        # conclusão, marca o progresso e reavalia badges. Isso conecta o
        # Lab/Range Engine (Fase 2) ao Learning Platform (Fase 3) sem que
        # um módulo precise conhecer os detalhes internos do outro.
        linked_courses = db.query(Course).filter(Course.lab_id == instance.lab_id).all()
        for course in linked_courses:
            mark_course_completed_if_needed(db, user.id, course.id)
        check_and_award_achievements(db, user.id)

    log_action(
        db, actor_user_id=user.id, action="flag_submitted",
        resource_type="lab_instance", resource_id=instance.id,
        metadata={"correct": correct, "points_awarded": points},
    )

    return submission
