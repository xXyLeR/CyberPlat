"""
Modelos ORM do MVP.

Decisão: no MVP existe apenas UMA organização ("default"), mas o campo
organization_id já existe em User desde já — isso evita uma migração
dolorosa de multi-tenancy na Fase 5 (é mais barato adicionar uma coluna
vazia hoje do que fazer backfill de milhões de linhas depois).

Decisão de segurança: Flag.flag_hash armazena SHA-256 da flag, nunca a
flag em texto puro. Mesmo com um dump completo do banco, um atacante não
recupera a flag (apenas pode tentar validar guesses offline, mas as flags
são strings longas e aleatórias, não frases previsíveis).
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Integer, Boolean, Text, Enum, JSON
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RoleName(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    TEAM_MANAGER = "team_manager"
    INSTRUCTOR = "instructor"
    STUDENT = "student"


class LabInstanceStatus(str, enum.Enum):
    PROVISIONING = "provisioning"
    RUNNING = "running"
    EXPIRED = "expired"
    DESTROYED = "destroyed"
    ERROR = "error"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False, unique=True)
    plan_tier = Column(String, default="default")
    created_at = Column(DateTime, default=utcnow)

    users = relationship("User", back_populates="organization")
    teams = relationship("Team", back_populates="organization")


class Team(Base):
    __tablename__ = "teams"

    id = Column(String, primary_key=True, default=gen_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    organization = relationship("Organization", back_populates="teams")
    members = relationship("User", back_populates="team")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    team_id = Column(String, ForeignKey("teams.id"), nullable=True)
    email = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(RoleName), nullable=False, default=RoleName.STUDENT)
    mfa_enabled = Column(Boolean, default=False)
    # Segredo TOTP (base32). Gerado em /auth/mfa/setup, só passa a valer
    # depois de confirmado em /auth/mfa/verify — nunca fica "meio
    # habilitado": ou mfa_enabled é False (secret pode existir mas não
    # é usado no login) ou é True (secret confirmado e obrigatório).
    mfa_secret = Column(String, nullable=True)
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    organization = relationship("Organization", back_populates="users")
    team = relationship("Team", back_populates="members")


class Lab(Base):
    __tablename__ = "labs"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)
    description = Column(Text, default="")
    category = Column(String, default="web")
    difficulty = Column(String, default="beginner")
    estimated_minutes = Column(Integer, default=30)
    # Definição declarativa completa (imagens, network, objetivos etc.)
    # armazenada como JSON — validada contra schema antes de ser aceita
    # (ver app/lab_schema.py).
    definition = Column(JSON, nullable=False)
    status = Column(String, default="draft")  # draft | published
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    flags = relationship("Flag", back_populates="lab")


class Flag(Base):
    __tablename__ = "flags"

    id = Column(String, primary_key=True, default=gen_uuid)
    lab_id = Column(String, ForeignKey("labs.id"), nullable=False)
    flag_key = Column(String, nullable=False)  # ex: "flag_01"
    flag_hash = Column(String, nullable=False)  # sha256(flag_value)
    points = Column(Integer, default=100)

    lab = relationship("Lab", back_populates="flags")


class LabInstance(Base):
    __tablename__ = "lab_instances"

    id = Column(String, primary_key=True, default=gen_uuid)
    lab_id = Column(String, ForeignKey("labs.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(LabInstanceStatus), default=LabInstanceStatus.PROVISIONING)
    network_namespace = Column(String, nullable=True)  # nome da docker network isolada
    container_id = Column(String, nullable=True)
    access_token = Column(String, nullable=True)  # token de sessão única p/ Session Gateway
    started_at = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime, nullable=True)
    destroyed_at = Column(DateTime, nullable=True)


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    lab_instance_id = Column(String, ForeignKey("lab_instances.id"), nullable=False)
    flag_id = Column(String, ForeignKey("flags.id"), nullable=True)
    submitted_value_hash = Column(String, nullable=False)
    correct = Column(Boolean, default=False)
    points_awarded = Column(Integer, default=0)
    submitted_at = Column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    actor_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------------------
# Fase 3 — Learning Platform
# ---------------------------------------------------------------------------
#
# Decisão de modelagem: NÃO armazenamos um campo "percent_complete" na
# LearningPath. Progresso agregado é sempre CALCULADO a partir de
# CourseProgress (contagem de cursos concluídos / total de cursos). Um
# campo persistido de percentual é uma cópia que pode divergir da
# realidade (ex: se um curso é removido da trilha depois de calculado);
# calcular sob demanda custa pouco e nunca fica desatualizado.

class LearningPath(Base):
    __tablename__ = "learning_paths"

    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)
    description = Column(Text, default="")
    status = Column(String, default="draft")  # draft | published
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    courses = relationship(
        "Course", back_populates="learning_path", order_by="Course.order_index"
    )


class Course(Base):
    __tablename__ = "courses"

    id = Column(String, primary_key=True, default=gen_uuid)
    learning_path_id = Column(String, ForeignKey("learning_paths.id"), nullable=False)
    title = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    description = Column(Text, default="")
    order_index = Column(Integer, default=0)
    estimated_minutes = Column(Integer, default=15)
    # Um curso conclui de UMA das três formas, mutuamente exclusivas:
    #  (a) lab_id setado         -> concluído ao resolver a flag do lab
    #  (b) possui QuizQuestions  -> concluído ao passar no quiz
    #  (c) nenhum dos dois       -> teoria pura, concluído via "mark as read"
    lab_id = Column(String, ForeignKey("labs.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    learning_path = relationship("LearningPath", back_populates="courses")
    quiz_questions = relationship("QuizQuestion", back_populates="course")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(String, primary_key=True, default=gen_uuid)
    course_id = Column(String, ForeignKey("courses.id"), nullable=False)
    prompt = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)       # lista de strings
    correct_index = Column(Integer, nullable=False)
    explanation = Column(Text, default="")

    course = relationship("Course", back_populates="quiz_questions")


class CourseProgress(Base):
    __tablename__ = "course_progress"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    course_id = Column(String, ForeignKey("courses.id"), nullable=False)
    score = Column(Integer, nullable=True)  # percentual, só para cursos com quiz
    completed_at = Column(DateTime, default=utcnow)


class Badge(Base):
    __tablename__ = "badges"

    id = Column(String, primary_key=True, default=gen_uuid)
    slug = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    badge_id = Column(String, ForeignKey("badges.id"), nullable=False)
    earned_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------------------
# Fase 5 — Enterprise (Reports)
# ---------------------------------------------------------------------------
#
# Decisão: o relatório é gerado a partir de dados que JÁ existem
# (Submission, Lab) no momento da geração — `content_json` é um
# snapshot imutável do que foi encontrado até aquele momento. Isso
# reflete a realidade de um pentest de verdade: um relatório entregue
# não deve mudar retroativamente se o aluno resolver mais labs depois.
# Para um relatório atualizado, gera-se um novo.

class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    content_json = Column(JSON, nullable=False)
    generated_at = Column(DateTime, default=utcnow)
