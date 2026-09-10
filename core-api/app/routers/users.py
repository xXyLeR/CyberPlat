from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import Achievement, Badge, User
from app.schemas import AchievementOut, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)):
    return user


@router.get("/me/achievements", response_model=list[AchievementOut])
def get_my_achievements(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    rows = (
        db.query(Achievement, Badge)
        .join(Badge, Achievement.badge_id == Badge.id)
        .filter(Achievement.user_id == user.id)
        .order_by(Achievement.earned_at.desc())
        .all()
    )
    return [
        AchievementOut(badge=badge, earned_at=achievement.earned_at)
        for achievement, badge in rows
    ]


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # Apenas admins podem listar todos os usuários da organização.
    return db.query(User).filter(User.organization_id == admin.organization_id).all()
