"""
Dependências de autenticação e autorização (RBAC).

Decisão de arquitetura: a checagem de role acontece EXCLUSIVAMENTE no
backend, a partir do claim `role` dentro do JWT assinado pelo servidor.
O frontend pode esconder botões de admin por UX, mas isso nunca é a
barreira de segurança real — a barreira real é `require_role(...)` aqui.

Risco considerado: se um JWT antigo permanecer válido após um downgrade
de permissão (ex: admin vira student), o usuário manteria privilégios
até o token expirar. Mitigação: access_token_expire_minutes é curto (15
min por padrão), limitando a janela de exposição. Para revogação
imediata (ex: usuário demitido), a Fase 5 adiciona uma denylist em Redis
verificada neste mesmo dependency.
"""
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, RoleName
from app.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas ou expiradas",
        )

    # Um token "mfa_pending" (emitido durante o segundo fator) NUNCA é
    # aceito como credencial de acesso normal — só o endpoint
    # /auth/mfa/login-verify sabe processá-lo. Sem esta checagem, alguém
    # com senha correta mas sem o segundo fator poderia usar o token
    # intermediário para acessar a API normalmente, anulando o MFA.
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido para esta operação",
        )

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido")
    return user


def require_role(*allowed_roles: RoleName) -> Callable:
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissão insuficiente para esta ação",
            )
        return user

    return checker


# Atalhos comuns
require_instructor_or_admin = require_role(
    RoleName.INSTRUCTOR, RoleName.ORG_ADMIN, RoleName.SUPER_ADMIN
)
require_admin = require_role(RoleName.ORG_ADMIN, RoleName.SUPER_ADMIN)
require_team_manager_or_admin = require_role(
    RoleName.TEAM_MANAGER, RoleName.ORG_ADMIN, RoleName.SUPER_ADMIN
)
require_super_admin = require_role(RoleName.SUPER_ADMIN)
