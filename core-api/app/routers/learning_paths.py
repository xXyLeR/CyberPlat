from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.achievements import (
    check_and_award_achievements,
    learning_path_progress,
    mark_course_completed_if_needed,
)
from app.audit import log_action
from app.database import get_db
from app.deps import get_current_user, require_instructor_or_admin
from app.models import Course, CourseProgress, Lab, LearningPath, QuizQuestion, User
from app.schemas import (
    CourseCreateRequest,
    CourseOut,
    LearningPathCreateRequest,
    LearningPathDetailOut,
    LearningPathOut,
    QuizQuestionOut,
    QuizResultOut,
    QuizSubmitRequest,
)

router = APIRouter(tags=["learning-paths"])

QUIZ_PASSING_SCORE = 70  # percentual mínimo para considerar o quiz aprovado


def _course_to_out(db: Session, course: Course, user_id: str) -> CourseOut:
    completed = (
        db.query(CourseProgress)
        .filter(CourseProgress.user_id == user_id, CourseProgress.course_id == course.id)
        .first()
        is not None
    )
    return CourseOut(
        id=course.id,
        title=course.title,
        slug=course.slug,
        description=course.description,
        order_index=course.order_index,
        estimated_minutes=course.estimated_minutes,
        lab_id=course.lab_id,
        has_quiz=len(course.quiz_questions) > 0,
        completed=completed,
    )


@router.post("/learning-paths", response_model=LearningPathOut, status_code=201)
def create_learning_path(
    payload: LearningPathCreateRequest,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor_or_admin),
):
    existing = db.query(LearningPath).filter(LearningPath.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Slug já utilizado")

    path = LearningPath(
        title=payload.title,
        slug=payload.slug,
        description=payload.description,
        status="published",
        created_by=instructor.id,
    )
    db.add(path)
    db.commit()
    db.refresh(path)

    log_action(
        db, actor_user_id=instructor.id, action="learning_path_created",
        resource_type="learning_path", resource_id=path.id,
    )
    return path


@router.get("/learning-paths", response_model=list[LearningPathOut])
def list_learning_paths(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(LearningPath).filter(LearningPath.status == "published").all()


@router.get("/learning-paths/{path_id}", response_model=LearningPathDetailOut)
def get_learning_path(
    path_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    path = db.query(LearningPath).filter(LearningPath.id == path_id).first()
    if not path:
        raise HTTPException(status_code=404, detail="Learning Path não encontrada")

    courses = (
        db.query(Course)
        .filter(Course.learning_path_id == path.id)
        .order_by(Course.order_index)
        .all()
    )
    progress = learning_path_progress(db, user.id, path.id)

    return LearningPathDetailOut(
        id=path.id,
        title=path.title,
        slug=path.slug,
        description=path.description,
        status=path.status,
        courses=[_course_to_out(db, c, user.id) for c in courses],
        progress_completed=progress["completed"],
        progress_total=progress["total"],
        progress_percent=progress["percent"],
    )


@router.post("/learning-paths/{path_id}/courses", response_model=CourseOut, status_code=201)
def create_course(
    path_id: str,
    payload: CourseCreateRequest,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor_or_admin),
):
    path = db.query(LearningPath).filter(LearningPath.id == path_id).first()
    if not path:
        raise HTTPException(status_code=404, detail="Learning Path não encontrada")

    if payload.lab_id:
        lab = db.query(Lab).filter(Lab.id == payload.lab_id).first()
        if not lab:
            raise HTTPException(status_code=404, detail="Lab referenciado não existe")

    if payload.lab_id and payload.quiz_questions:
        raise HTTPException(
            status_code=422,
            detail="Um curso conclui por lab OU por quiz, não pelos dois ao mesmo tempo",
        )

    course = Course(
        learning_path_id=path.id,
        title=payload.title,
        slug=payload.slug,
        description=payload.description,
        order_index=payload.order_index,
        estimated_minutes=payload.estimated_minutes,
        lab_id=payload.lab_id,
    )
    db.add(course)
    db.commit()
    db.refresh(course)

    for q in payload.quiz_questions:
        if not (0 <= q.correct_index < len(q.options)):
            raise HTTPException(status_code=422, detail="correct_index fora do range de options")
        db.add(
            QuizQuestion(
                course_id=course.id,
                prompt=q.prompt,
                options=q.options,
                correct_index=q.correct_index,
                explanation=q.explanation,
            )
        )
    db.commit()
    db.refresh(course)

    log_action(
        db, actor_user_id=instructor.id, action="course_created",
        resource_type="course", resource_id=course.id, metadata={"learning_path_id": path.id},
    )
    return _course_to_out(db, course, instructor.id)


@router.get("/courses/{course_id}/quiz", response_model=list[QuizQuestionOut])
def get_course_quiz(
    course_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Curso não encontrado")
    # Nunca retornamos correct_index aqui — QuizQuestionOut não tem esse campo.
    return course.quiz_questions


@router.post("/courses/{course_id}/quiz/submit", response_model=QuizResultOut)
def submit_quiz(
    course_id: str,
    payload: QuizSubmitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Curso não encontrado")
    if not course.quiz_questions:
        raise HTTPException(status_code=400, detail="Este curso não possui quiz")

    total = len(course.quiz_questions)
    correct_count = 0
    for question in course.quiz_questions:
        selected = payload.answers.get(question.id)
        if selected is not None and selected == question.correct_index:
            correct_count += 1

    score_percent = round(100 * correct_count / total)
    passed = score_percent >= QUIZ_PASSING_SCORE

    course_completed = False
    if passed:
        course_completed = mark_course_completed_if_needed(
            db, user.id, course.id, score=score_percent
        )
        check_and_award_achievements(db, user.id)

    log_action(
        db, actor_user_id=user.id, action="quiz_submitted",
        resource_type="course", resource_id=course.id,
        metadata={"score_percent": score_percent, "passed": passed},
    )

    return QuizResultOut(score_percent=score_percent, passed=passed, course_completed=course_completed)


@router.post("/courses/{course_id}/complete", response_model=CourseOut)
def complete_theory_course(
    course_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """
    Marca um curso puramente teórico (sem lab, sem quiz) como concluído.
    Auto-declarado de propósito — não há como validar "leitura" de forma
    confiável no MVP; cursos com critério objetivo (lab ou quiz) usam os
    endpoints correspondentes, que não são auto-declarados.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Curso não encontrado")
    if course.lab_id or course.quiz_questions:
        raise HTTPException(
            status_code=400,
            detail="Este curso conclui automaticamente ao resolver o lab ou passar no quiz",
        )

    mark_course_completed_if_needed(db, user.id, course.id)
    check_and_award_achievements(db, user.id)
    return _course_to_out(db, course, user.id)
