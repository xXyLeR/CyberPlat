"""
Worker de expiração automática de lab instances.

Por que isso é necessário: hoje (Fase 2) um LabInstance só é destruído se
o usuário chamar POST /lab-sessions/{id}/terminate. Se o usuário
simplesmente fechar a aba, o container ficaria rodando indefinidamente
até alguém notar — isso é o cenário exato de abuso descrito na
arquitetura (recursos presos = superfície para cryptomining/DoS). Este
worker fecha essa lacuna: roda em loop (ou como Kubernetes CronJob),
busca instâncias com `expires_at` no passado e ainda `status=running`, e
força a destruição.

Decisão: a função `expire_overdue_instances` é pura o suficiente para
ser testada com um orchestrator fake (ver tests/test_worker.py) — ela
recebe `db` e `orchestrator` como parâmetros, nunca instancia nada
globalmente, o que também facilita rodá-la tanto em loop (`if __main__`)
quanto como um Kubernetes CronJob de execução única.
"""
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.audit import log_action
from app.config import get_settings
from app.database import SessionLocal
from app.models import LabInstance, LabInstanceStatus
from app.orchestrator import get_orchestrator

settings = get_settings()


def expire_overdue_instances(db: Session, orchestrator) -> int:
    now = datetime.now(timezone.utc)

    overdue = (
        db.query(LabInstance)
        .filter(
            LabInstance.status == LabInstanceStatus.RUNNING,
            LabInstance.expires_at.isnot(None),
            LabInstance.expires_at < now,
        )
        .all()
    )

    count = 0
    for instance in overdue:
        if instance.container_id:
            try:
                orchestrator.destroy(instance.container_id, instance.network_namespace)
            except RuntimeError:
                # Ambiente sem daemon/cluster disponível (dev) — segue o
                # fluxo mesmo assim, para não deixar o registro no banco
                # eternamente "running" quando a infraestrutura real já
                # não existe (ex: cluster reiniciado).
                pass

        instance.status = LabInstanceStatus.EXPIRED
        instance.destroyed_at = now
        db.add(instance)

        log_action(
            db,
            actor_user_id=None,
            action="lab_instance_expired",
            resource_type="lab_instance",
            resource_id=instance.id,
            metadata={"reason": "ttl_exceeded"},
        )
        count += 1

    db.commit()
    return count


def run_forever() -> None:
    orchestrator = get_orchestrator()
    while True:
        db = SessionLocal()
        try:
            expired_count = expire_overdue_instances(db, orchestrator)
            if expired_count:
                print(f"[expiration-worker] {expired_count} lab instance(s) expirada(s)")
        finally:
            db.close()
        time.sleep(settings.expiration_worker_poll_seconds)


if __name__ == "__main__":
    run_forever()
