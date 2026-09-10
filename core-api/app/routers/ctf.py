from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.achievements import check_and_award_achievements
from app.audit import log_action
from app.database import get_db
from app.deps import get_current_user, require_instructor_or_admin
from app.models import Challenge, CTFSubmission, User
from app.rate_limit import is_rate_limited
from app.schemas import (
    ChallengeCreateRequest,
    ChallengeDetailOut,
    ChallengeOut,
    ChallengeSubmitRequest,
    ChallengeSubmitResultOut,
)
from app.security import sha256_hex

router = APIRouter(prefix="/challenges", tags=["ctf"])


def _has_solved(db: Session, user_id: str, challenge_id: str) -> bool:
    return (
        db.query(CTFSubmission)
        .filter(
            CTFSubmission.user_id == user_id,
            CTFSubmission.challenge_id == challenge_id,
            CTFSubmission.correct == True,  # noqa: E712
        )
        .first()
        is not None
    )


@router.post("", response_model=ChallengeDetailOut, status_code=201)
def create_challenge(
    payload: ChallengeCreateRequest,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor_or_admin),
):
    existing = db.query(Challenge).filter(Challenge.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Slug já utilizado")

    challenge = Challenge(
        title=payload.title,
        slug=payload.slug,
        category=payload.category,
        difficulty=payload.difficulty,
        description=payload.description,
        points=payload.points,
        # A flag NUNCA é armazenada em texto puro — mesmo padrão usado
        # para flags de lab (ver app/models.py::Flag).
        flag_hash=sha256_hex(payload.flag_value.strip()),
        hints=payload.hints,
        status="published",
        created_by=instructor.id,
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)

    log_action(
        db, actor_user_id=instructor.id, action="challenge_created",
        resource_type="challenge", resource_id=challenge.id,
    )
    return ChallengeDetailOut(
        id=challenge.id, title=challenge.title, slug=challenge.slug,
        category=challenge.category, difficulty=challenge.difficulty,
        description=challenge.description, points=challenge.points,
        hint_count=len(challenge.hints), hints=challenge.hints, solved=False,
    )


@router.get("", response_model=list[ChallengeOut])
def list_challenges(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    challenges = db.query(Challenge).filter(Challenge.status == "published").all()
    return [
        ChallengeOut(
            id=c.id, title=c.title, slug=c.slug, category=c.category, difficulty=c.difficulty,
            description=c.description, points=c.points, hint_count=len(c.hints),
            solved=_has_solved(db, user.id, c.id),
        )
        for c in challenges
    ]


@router.get("/{challenge_id}", response_model=ChallengeDetailOut)
def get_challenge(
    challenge_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Desafio não encontrado")
    return ChallengeDetailOut(
        id=challenge.id, title=challenge.title, slug=challenge.slug,
        category=challenge.category, difficulty=challenge.difficulty,
        description=challenge.description, points=challenge.points,
        hint_count=len(challenge.hints), hints=challenge.hints,
        solved=_has_solved(db, user.id, challenge.id),
    )


@router.post("/{challenge_id}/submit", response_model=ChallengeSubmitResultOut)
def submit_challenge_flag(
    challenge_id: str,
    payload: ChallengeSubmitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rate_key = f"ctf:{user.id}:{challenge_id}"
    if is_rate_limited(rate_key):
        raise HTTPException(status_code=429, detail="Muitas tentativas — aguarde antes de tentar novamente")

    challenge = db.query(Challenge).filter(Challenge.id == challenge_id, Challenge.status == "published").first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Desafio não encontrado")

    already_solved = _has_solved(db, user.id, challenge.id)
    submitted_hash = sha256_hex(payload.flag_value.strip())
    correct = submitted_hash == challenge.flag_hash and not already_solved
    points = challenge.points if correct else 0

    submission = CTFSubmission(
        user_id=user.id, challenge_id=challenge.id,
        submitted_value_hash=submitted_hash, correct=correct, points_awarded=points,
    )
    db.add(submission)

    if correct:
        user.xp += points
        user.level = 1 + user.xp // 500
        db.add(user)

    db.commit()

    if correct:
        check_and_award_achievements(db, user.id)

    log_action(
        db, actor_user_id=user.id, action="ctf_flag_submitted",
        resource_type="challenge", resource_id=challenge.id,
        metadata={"correct": correct, "points_awarded": points},
    )

    return ChallengeSubmitResultOut(correct=correct, points_awarded=points)
