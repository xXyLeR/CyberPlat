from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Team, User
from app.schemas import LeaderboardEntryOut, TeamLeaderboardEntryOut

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("", response_model=list[LeaderboardEntryOut])
def get_individual_leaderboard(
    limit: int = 20, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    # Ranking sempre escopado à organização do usuário — não faz sentido
    # (e vazaria dados entre tenants) mostrar um ranking global cruzando
    # organizações diferentes.
    top_users = (
        db.query(User)
        .filter(User.organization_id == user.organization_id)
        .order_by(User.xp.desc())
        .limit(min(limit, 100))
        .all()
    )
    return [
        LeaderboardEntryOut(rank=idx + 1, email=u.email, xp=u.xp, level=u.level)
        for idx, u in enumerate(top_users)
    ]


@router.get("/teams", response_model=list[TeamLeaderboardEntryOut])
def get_team_leaderboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    teams = db.query(Team).filter(Team.organization_id == user.organization_id).all()

    entries = []
    for team in teams:
        members = db.query(User).filter(User.team_id == team.id).all()
        if not members:
            continue
        total_xp = sum(m.xp for m in members)
        entries.append(
            TeamLeaderboardEntryOut(
                rank=0, team_name=team.name, total_xp=total_xp, member_count=len(members)
            )
        )

    entries.sort(key=lambda e: e.total_xp, reverse=True)
    for idx, entry in enumerate(entries):
        entry.rank = idx + 1

    return entries
