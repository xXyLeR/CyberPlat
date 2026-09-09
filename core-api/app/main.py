from fastapi import FastAPI

from app.achievements import ensure_default_badges
from app.database import Base, SessionLocal, engine
from app.routers import (
    audit,
    auth,
    analytics,
    labs,
    lab_sessions,
    learning_paths,
    organizations,
    reports,
    submissions,
    teams,
    users,
)

# No MVP, criamos as tabelas diretamente a partir dos models (create_all).
# A partir da Fase 3, isso é substituído por migrations versionadas via
# Alembic, para permitir mudanças de schema controladas em produção.
Base.metadata.create_all(bind=engine)

# Garante que os badges padrão existam (idempotente).
_db = SessionLocal()
try:
    ensure_default_badges(_db)
finally:
    _db.close()

app = FastAPI(
    title="Vantage Range — Core API",
    version="0.1.0-mvp",
    description="API central da plataforma de treinamento em segurança ofensiva.",
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(labs.router)
app.include_router(lab_sessions.router)
app.include_router(submissions.router)
app.include_router(learning_paths.router)
app.include_router(organizations.router)
app.include_router(teams.router)
app.include_router(analytics.router)
app.include_router(reports.router)
app.include_router(audit.router)


@app.get("/health")
def health():
    return {"status": "ok"}
