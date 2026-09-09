"""
Lógica de achievements.

Decisão: toda regra de "quando um badge é concedido" vive AQUI, não
espalhada pelos routers de submissions/courses. Isso evita duplicar a
mesma checagem em dois lugares e divergir com o tempo — qualquer novo
gatilho de badge (ex: um novo endpoint que também deveria conceder
"first_blood") só precisa chamar `check_and_award_achievements`.
"""
from sqlalchemy.orm import Session

from app.models import (
    Achievement,
    Badge,
    Course,
    CourseProgress,
    LearningPath,
    Submission,
)

BADGE_FIRST_BLOOD = "first_blood"
BADGE_PATH_FINISHER = "path_finisher"

DEFAULT_BADGES = [
    (BADGE_FIRST_BLOOD, "First Blood", "Encontrou e submeteu sua primeira flag correta."),
    (BADGE_PATH_FINISHER, "Path Finisher", "Concluiu todos os cursos de uma Learning Path."),
]


def ensure_default_badges(db: Session) -> None:
    for slug, name, description in DEFAULT_BADGES:
        exists = db.query(Badge).filter(Badge.slug == slug).first()
        if not exists:
            db.add(Badge(slug=slug, name=name, description=description))
    db.commit()


def _award_if_missing(db: Session, user_id: str, badge_slug: str) -> Achievement | None:
    badge = db.query(Badge).filter(Badge.slug == badge_slug).first()
    if not badge:
        return None
    already = (
        db.query(Achievement)
        .filter(Achievement.user_id == user_id, Achievement.badge_id == badge.id)
        .first()
    )
    if already:
        return None
    achievement = Achievement(user_id=user_id, badge_id=badge.id)
    db.add(achievement)
    db.commit()
    db.refresh(achievement)
    return achievement


def check_and_award_achievements(db: Session, user_id: str) -> list[Achievement]:
    """Reavalia todos os critérios de badge para um usuário. Idempotente."""
    newly_awarded: list[Achievement] = []

    # --- First Blood: pelo menos 1 submissão correta na vida do usuário ---
    has_correct_submission = (
        db.query(Submission)
        .filter(Submission.user_id == user_id, Submission.correct == True)  # noqa: E712
        .first()
    )
    if has_correct_submission:
        result = _award_if_missing(db, user_id, BADGE_FIRST_BLOOD)
        if result:
            newly_awarded.append(result)

    # --- Path Finisher: existe alguma Learning Path com 100% dos cursos
    #     concluídos por este usuário ---
    paths = db.query(LearningPath).filter(LearningPath.status == "published").all()
    for path in paths:
        courses = db.query(Course).filter(Course.learning_path_id == path.id).all()
        if not courses:
            continue
        completed_course_ids = {
            cp.course_id
            for cp in db.query(CourseProgress).filter(CourseProgress.user_id == user_id).all()
        }
        if all(course.id in completed_course_ids for course in courses):
            result = _award_if_missing(db, user_id, BADGE_PATH_FINISHER)
            if result:
                newly_awarded.append(result)
            break  # 1 path já concluída basta para o badge

    return newly_awarded


def learning_path_progress(db: Session, user_id: str, path_id: str) -> dict:
    """Retorna {completed, total, percent} para uma learning path + usuário."""
    courses = db.query(Course).filter(Course.learning_path_id == path_id).all()
    total = len(courses)
    if total == 0:
        return {"completed": 0, "total": 0, "percent": 0}

    course_ids = [c.id for c in courses]
    completed = (
        db.query(CourseProgress)
        .filter(CourseProgress.user_id == user_id, CourseProgress.course_id.in_(course_ids))
        .count()
    )
    return {"completed": completed, "total": total, "percent": round(100 * completed / total)}


def mark_course_completed_if_needed(
    db: Session, user_id: str, course_id: str, score: int | None = None
) -> bool:
    """Retorna True se acabou de marcar como concluído (idempotente)."""
    existing = (
        db.query(CourseProgress)
        .filter(CourseProgress.user_id == user_id, CourseProgress.course_id == course_id)
        .first()
    )
    if existing:
        return False
    db.add(CourseProgress(user_id=user_id, course_id=course_id, score=score))
    db.commit()
    return True
