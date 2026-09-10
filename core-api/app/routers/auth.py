from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import get_db
from app.deps import get_current_user
from app.models import Organization, RoleName, User
from app.schemas import RegisterRequest, TokenResponse
from app.security import (
    create_access_token,
    create_mfa_pending_token,
    decode_token,
    generate_mfa_secret,
    get_totp_provisioning_uri,
    hash_password,
    verify_password,
    verify_totp_code,
)

router = APIRouter(prefix="/auth", tags=["auth"])

DEFAULT_ORG_NAME = "default"


class LoginResponse(BaseModel):
    # Ou vem access_token (login concluído) ou vem mfa_pending_token
    # (falta o segundo fator) — nunca os dois ao mesmo tempo.
    access_token: str | None = None
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_pending_token: str | None = None


class MfaSetupResponse(BaseModel):
    provisioning_uri: str
    secret: str


class MfaVerifyRequest(BaseModel):
    code: str


class MfaLoginVerifyRequest(BaseModel):
    mfa_pending_token: str
    code: str


def get_or_create_default_org(db: Session) -> Organization:
    org = db.query(Organization).filter(Organization.name == DEFAULT_ORG_NAME).first()
    if org is None:
        org = Organization(name=DEFAULT_ORG_NAME)
        db.add(org)
        db.commit()
        db.refresh(org)
    return org


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    org = get_or_create_default_org(db)
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=RoleName.STUDENT,  # novos cadastros públicos nunca começam como admin
        organization_id=org.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log_action(db, actor_user_id=user.id, action="user_registered", resource_type="user", resource_id=user.id)

    token = create_access_token(subject=user.id, role=user.role.value, org_id=user.organization_id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=LoginResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    # Mensagem genérica de propósito: não revelar se o email existe ou não
    # (evita user enumeration).
    invalid_credentials = HTTPException(status_code=401, detail="Email ou senha inválidos")

    if user is None or not verify_password(form_data.password, user.password_hash):
        log_action(db, actor_user_id=None, action="login_failed", metadata={"email": form_data.username})
        raise invalid_credentials

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuário desativado")

    if user.mfa_enabled:
        log_action(db, actor_user_id=user.id, action="login_password_ok_mfa_pending", resource_type="user", resource_id=user.id)
        return LoginResponse(mfa_required=True, mfa_pending_token=create_mfa_pending_token(user.id))

    log_action(db, actor_user_id=user.id, action="login_success", resource_type="user", resource_id=user.id)
    token = create_access_token(subject=user.id, role=user.role.value, org_id=user.organization_id)
    return LoginResponse(access_token=token)


@router.post("/mfa/login-verify", response_model=LoginResponse)
def mfa_login_verify(payload: MfaLoginVerifyRequest, db: Session = Depends(get_db)):
    try:
        token_payload = decode_token(payload.mfa_pending_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Token de MFA inválido ou expirado")

    if token_payload.get("type") != "mfa_pending":
        raise HTTPException(status_code=401, detail="Token de MFA inválido")

    user = db.query(User).filter(User.id == token_payload.get("sub")).first()
    if not user or not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(status_code=401, detail="MFA não configurado para este usuário")

    if not verify_totp_code(user.mfa_secret, payload.code):
        log_action(db, actor_user_id=user.id, action="mfa_login_failed", resource_type="user", resource_id=user.id)
        raise HTTPException(status_code=401, detail="Código de MFA inválido")

    log_action(db, actor_user_id=user.id, action="mfa_login_success", resource_type="user", resource_id=user.id)
    token = create_access_token(subject=user.id, role=user.role.value, org_id=user.organization_id)
    return LoginResponse(access_token=token)


@router.post("/mfa/setup", response_model=MfaSetupResponse)
def mfa_setup(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Gera um novo segredo TOTP e retorna a URI de provisionamento (para
    QR code). O segredo é salvo, mas `mfa_enabled` permanece False até
    /auth/mfa/verify confirmar que o usuário conseguiu gerar um código
    válido — evita que o usuário fique "trancado para fora" da própria
    conta por ter salvo o secret errado no app autenticador.
    """
    secret = generate_mfa_secret()
    user.mfa_secret = secret
    user.mfa_enabled = False
    db.add(user)
    db.commit()

    return MfaSetupResponse(
        provisioning_uri=get_totp_provisioning_uri(secret, user.email), secret=secret
    )


@router.post("/mfa/verify", response_model=TokenResponse)
def mfa_verify(
    payload: MfaVerifyRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    if not user.mfa_secret:
        raise HTTPException(status_code=400, detail="Chame /auth/mfa/setup primeiro")

    if not verify_totp_code(user.mfa_secret, payload.code):
        raise HTTPException(status_code=400, detail="Código inválido")

    user.mfa_enabled = True
    db.add(user)
    db.commit()

    log_action(db, actor_user_id=user.id, action="mfa_enabled", resource_type="user", resource_id=user.id)

    token = create_access_token(subject=user.id, role=user.role.value, org_id=user.organization_id)
    return TokenResponse(access_token=token)


@router.post("/mfa/disable", response_model=TokenResponse)
def mfa_disable(
    payload: MfaVerifyRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    # Exige um código válido para desabilitar — sem isso, um atacante com
    # um token de acesso roubado (mas sem o segundo fator) poderia
    # simplesmente desligar o MFA da conta.
    if not user.mfa_enabled or not user.mfa_secret or not verify_totp_code(user.mfa_secret, payload.code):
        raise HTTPException(status_code=400, detail="Código inválido")

    user.mfa_enabled = False
    user.mfa_secret = None
    db.add(user)
    db.commit()

    log_action(db, actor_user_id=user.id, action="mfa_disabled", resource_type="user", resource_id=user.id)
    token = create_access_token(subject=user.id, role=user.role.value, org_id=user.organization_id)
    return TokenResponse(access_token=token)
