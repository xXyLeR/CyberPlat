from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import get_db
from app.deps import get_current_user, require_admin, require_team_manager_or_admin
from app.models import RoleName, Team, User
from app.schemas import TeamCreateRequest, TeamDetailOut, TeamMemberAddRequest, TeamOut

router = APIRouter(prefix="/teams", tags=["teams"])


def _ensure_manages_team(actor: User, team: Team) -> None:
    """
    org_admin/super_admin gerenciam qualquer team da própria org.
    team_manager só gerencia o PRÓPRIO team (team_id igual ao dele) —
    esta é a diferença real entre os dois papéis; sem esta checagem,
    'team_manager' seria só um apelido para admin.
    """
    if actor.role in (RoleName.ORG_ADMIN, RoleName.SUPER_ADMIN):
        return
    if actor.role == RoleName.TEAM_MANAGER and actor.team_id == team.id:
        return
    raise HTTPException(status_code=403, detail="Você não gerencia este team")


@router.post("", response_model=TeamOut, status_code=201)
def create_team(
    payload: TeamCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    team = Team(organization_id=admin.organization_id, name=payload.name)
    db.add(team)
    db.commit()
    db.refresh(team)

    log_action(
        db, actor_user_id=admin.id, action="team_created",
        resource_type="team", resource_id=team.id,
    )
    return team


@router.get("", response_model=list[TeamOut])
def list_teams(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Team).filter(Team.organization_id == user.organization_id).all()


@router.get("/{team_id}", response_model=TeamDetailOut)
def get_team(team_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    team = db.query(Team).filter(Team.id == team_id, Team.organization_id == user.organization_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team não encontrado")
    members = db.query(User).filter(User.team_id == team.id).all()
    return TeamDetailOut(
        id=team.id, organization_id=team.organization_id, name=team.name, members=members
    )


@router.post("/{team_id}/members", response_model=TeamDetailOut)
def add_team_member(
    team_id: str,
    payload: TeamMemberAddRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_team_manager_or_admin),
):
    team = db.query(Team).filter(Team.id == team_id, Team.organization_id == actor.organization_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team não encontrado")
    _ensure_manages_team(actor, team)

    member = db.query(User).filter(
        User.id == payload.user_id, User.organization_id == actor.organization_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Usuário não encontrado nesta organização")

    member.team_id = team.id
    db.add(member)
    db.commit()

    log_action(
        db, actor_user_id=actor.id, action="team_member_added",
        resource_type="team", resource_id=team.id, metadata={"user_id": member.id},
    )

    members = db.query(User).filter(User.team_id == team.id).all()
    return TeamDetailOut(
        id=team.id, organization_id=team.organization_id, name=team.name, members=members
    )
