from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---- Auth ----
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Users ----
class UserOut(BaseModel):
    id: str
    email: str
    role: str
    xp: int
    level: int
    organization_id: str

    model_config = ConfigDict(from_attributes=True)


# ---- Labs ----
class LabCreateRequest(BaseModel):
    name: str
    slug: str
    description: str = ""
    category: str = "web"
    difficulty: str = "beginner"
    estimated_minutes: int = 30
    definition: dict[str, Any]


class LabOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    category: str
    difficulty: str
    estimated_minutes: int
    status: str

    model_config = ConfigDict(from_attributes=True)


# ---- Lab Sessions ----
class LabSessionCreateRequest(BaseModel):
    lab_id: str


class LabSessionOut(BaseModel):
    id: str
    lab_id: str
    status: str
    started_at: datetime
    expires_at: Optional[datetime]
    access_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---- Submissions ----
class SubmissionCreateRequest(BaseModel):
    lab_instance_id: str
    flag_value: str


class SubmissionOut(BaseModel):
    id: str
    correct: bool
    points_awarded: int
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---- Audit ----
class AuditLogOut(BaseModel):
    id: str
    actor_user_id: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---- Learning Paths / Courses / Quiz (Fase 3) ----
class QuizQuestionCreate(BaseModel):
    prompt: str
    options: list[str] = Field(min_length=2)
    correct_index: int
    explanation: str = ""


class QuizQuestionOut(BaseModel):
    id: str
    prompt: str
    options: list[str]
    # Nota: correct_index NUNCA é exposto neste schema — o aluno não deve
    # ver a resposta certa antes de responder. Ver QuizQuestionWithAnswerOut
    # usado apenas depois da submissão.

    model_config = ConfigDict(from_attributes=True)


class CourseCreateRequest(BaseModel):
    title: str
    slug: str
    description: str = ""
    order_index: int = 0
    estimated_minutes: int = 15
    lab_id: Optional[str] = None
    quiz_questions: list[QuizQuestionCreate] = []


class CourseOut(BaseModel):
    id: str
    title: str
    slug: str
    description: str
    order_index: int
    estimated_minutes: int
    lab_id: Optional[str]
    has_quiz: bool
    completed: bool = False  # calculado por request, relativo ao usuário logado

    model_config = ConfigDict(from_attributes=True)


class LearningPathCreateRequest(BaseModel):
    title: str
    slug: str
    description: str = ""


class LearningPathOut(BaseModel):
    id: str
    title: str
    slug: str
    description: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class LearningPathDetailOut(LearningPathOut):
    courses: list[CourseOut]
    progress_completed: int
    progress_total: int
    progress_percent: int


class QuizSubmitRequest(BaseModel):
    answers: dict[str, int]  # question_id -> selected_option_index


class QuizResultOut(BaseModel):
    score_percent: int
    passed: bool
    course_completed: bool


class BadgeOut(BaseModel):
    slug: str
    name: str
    description: str

    model_config = ConfigDict(from_attributes=True)


class AchievementOut(BaseModel):
    badge: BadgeOut
    earned_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---- Organizations / Teams (Fase 5) ----
class OrganizationCreateRequest(BaseModel):
    name: str
    plan_tier: str = "default"


class OrganizationOut(BaseModel):
    id: str
    name: str
    plan_tier: str

    model_config = ConfigDict(from_attributes=True)


class TeamCreateRequest(BaseModel):
    name: str


class TeamOut(BaseModel):
    id: str
    organization_id: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class TeamMemberAddRequest(BaseModel):
    user_id: str


class TeamDetailOut(TeamOut):
    members: list[UserOut]


# ---- Analytics (Fase 5) ----
class OrgAnalyticsOut(BaseModel):
    total_users: int
    active_users_last_30_days: int
    total_lab_sessions: int
    labs_completed: int          # sessões com ao menos 1 submissão correta
    labs_abandoned: int          # sessões destruídas/expiradas sem nenhuma submissão correta
    completion_rate_percent: int
    average_score_per_completed_session: float
    hardest_labs: list[dict]     # [{lab_name, attempts, solves, solve_rate_percent}]


# ---- Reports (Fase 5) ----
class ReportGenerateRequest(BaseModel):
    title: str = "Relatório de Pentest"


class ReportOut(BaseModel):
    id: str
    title: str
    generated_at: datetime
    content: dict

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, report):
        return cls(
            id=report.id,
            title=report.title,
            generated_at=report.generated_at,
            content=report.content_json,
        )
<<<<<<< HEAD


# ---- CTF ----
class ChallengeCreateRequest(BaseModel):
    title: str
    slug: str
    category: str
    difficulty: str = "beginner"
    description: str = ""
    points: int = 100
    flag_value: str
    hints: list[str] = []


class ChallengeOut(BaseModel):
    id: str
    title: str
    slug: str
    category: str
    difficulty: str
    description: str
    points: int
    hint_count: int
    solved: bool = False


class ChallengeDetailOut(ChallengeOut):
    hints: list[str]


class ChallengeSubmitRequest(BaseModel):
    flag_value: str


class ChallengeSubmitResultOut(BaseModel):
    correct: bool
    points_awarded: int


class LeaderboardEntryOut(BaseModel):
    rank: int
    email: str
    xp: int
    level: int


class TeamLeaderboardEntryOut(BaseModel):
    rank: int
    team_name: str
    total_xp: int
    member_count: int
=======
>>>>>>> 7da46cdbcf65aa44a988cbff473c3d4a232500be
