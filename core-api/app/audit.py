"""
Helper de auditoria.

Decisão: nenhum endpoint da API expõe UPDATE ou DELETE sobre audit_logs.
Em produção, isso é reforçado também a nível de banco (permissão GRANT
apenas INSERT/SELECT para o usuário de aplicação nessa tabela), para que
mesmo um bug de aplicação não permita adulterar o histórico.
"""
from sqlalchemy.orm import Session

from app.models import AuditLog


def log_action(
    db: Session,
    actor_user_id: str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=metadata or {},
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
