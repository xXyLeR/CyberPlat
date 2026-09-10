"""
Funções de segurança: hashing de senha (bcrypt) e emissão/validação de JWT.

Decisão: usamos bcrypt (via passlib) em vez de SHA/MD5 para senhas —
bcrypt é lento por design (fator de custo ajustável), o que torna
brute-force offline caro mesmo com dump de banco. Para hashes de FLAG
(não senha), usamos SHA-256 simples em models.py, porque ali o objetivo
é apenas evitar leitura direta em texto claro, não resistir a brute-force
de dicionário (a flag é um UUID aleatório, não uma senha escolhida por
humano — SHA-256 já é suficiente e mais barato).
"""
import hashlib
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pyotp
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_access_token(subject: str, role: str, org_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject,
        "role": role,
        "org_id": org_id,
        "exp": expire,
        "type": "access",
    }
    return pyjwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_mfa_pending_token(subject: str) -> str:
    """
    Token de vida MUITO curta (2 min), emitido depois de validar
    email+senha quando o usuário tem MFA habilitado. Este token NUNCA é
    aceito pelo dependency `get_current_user` (ver deps.py, que checa
    `type == "access"`) — ele só serve para provar, na segunda chamada
    (/auth/mfa/login-verify), que a senha já foi validada, sem re-enviar
    a senha em texto puro de novo.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=2)
    payload = {"sub": subject, "exp": expire, "type": "mfa_pending"}
    return pyjwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return pyjwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except pyjwt.PyJWTError as exc:
        raise ValueError("invalid_token") from exc


def generate_mfa_secret() -> str:
    return pyotp.random_base32()


def get_totp_provisioning_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name="Vantage Range")


def verify_totp_code(secret: str, code: str) -> bool:
    return pyotp.totp.TOTP(secret).verify(code, valid_window=1)
