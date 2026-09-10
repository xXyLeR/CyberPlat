from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import AuditLog, Lab, LabInstance, LabInstanceStatus, Submission, User
from app.schemas import OrgAnalyticsOut

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=OrgAnalyticsOut)
def get_org_overview(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    org_id = admin.organization_id
    org_user_ids = [
        u.id for u in db.query(User.id).filter(User.organization_id == org_id).all()
    ]
    if not org_user_ids:
        return OrgAnalyticsOut(
            total_users=0, active_users_last_30_days=0, total_lab_sessions=0,
            labs_completed=0, labs_abandoned=0, completion_rate_percent=0,
            average_score_per_completed_session=0.0, hardest_labs=[],
        )

    total_users = len(org_user_ids)

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    active_users = (
        db.query(AuditLog.actor_user_id)
        .filter(
            AuditLog.actor_user_id.in_(org_user_ids),
            AuditLog.action.in_(["login_success", "mfa_login_success"]),
            AuditLog.created_at >= thirty_days_ago,
        )
        .distinct()
        .count()
    )

    sessions = db.query(LabInstance).filter(LabInstance.user_id.in_(org_user_ids)).all()
    total_lab_sessions = len(sessions)

    # Sessões com pelo menos 1 submissão correta = "completadas".
    correct_submissions = (
        db.query(Submission)
        .filter(Submission.user_id.in_(org_user_ids), Submission.correct == True)  # noqa: E712
        .all()
    )
    completed_instance_ids = {s.lab_instance_id for s in correct_submissions}
    labs_completed = len(completed_instance_ids)

    # Abandonada = já encerrada (destruída ou expirada) mas nunca teve
    # uma submissão correta.
    labs_abandoned = sum(
        1
        for s in sessions
        if s.status in (LabInstanceStatus.DESTROYED, LabInstanceStatus.EXPIRED)
        and s.id not in completed_instance_ids
    )

    completion_rate = round(100 * labs_completed / total_lab_sessions) if total_lab_sessions else 0

    points_per_instance: dict[str, int] = {}
    for s in correct_submissions:
        points_per_instance[s.lab_instance_id] = points_per_instance.get(s.lab_instance_id, 0) + s.points_awarded
    avg_score = (
        round(sum(points_per_instance.values()) / len(points_per_instance), 1)
        if points_per_instance
        else 0.0
    )

    # Hardest labs: menor taxa de solve entre labs com pelo menos 1 tentativa.
    lab_attempts: dict[str, int] = {}
    lab_solves: dict[str, int] = {}
    for s in sessions:
        lab_attempts[s.lab_id] = lab_attempts.get(s.lab_id, 0) + 1
        if s.id in completed_instance_ids:
            lab_solves[s.lab_id] = lab_solves.get(s.lab_id, 0) + 1

    hardest = []
    for lab_id, attempts in lab_attempts.items():
        solves = lab_solves.get(lab_id, 0)
        lab = db.query(Lab).filter(Lab.id == lab_id).first()
        hardest.append(
            {
                "lab_name": lab.name if lab else lab_id,
                "attempts": attempts,
                "solves": solves,
                "solve_rate_percent": round(100 * solves / attempts) if attempts else 0,
            }
        )
    hardest.sort(key=lambda x: x["solve_rate_percent"])

    return OrgAnalyticsOut(
        total_users=total_users,
        active_users_last_30_days=active_users,
        total_lab_sessions=total_lab_sessions,
        labs_completed=labs_completed,
        labs_abandoned=labs_abandoned,
        completion_rate_percent=completion_rate,
        average_score_per_completed_session=avg_score,
        hardest_labs=hardest[:5],
    )
