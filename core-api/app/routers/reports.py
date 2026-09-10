from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import get_db
from app.deps import get_current_user
from app.models import Lab, Report, Submission, User
from app.schemas import ReportGenerateRequest, ReportOut

router = APIRouter(prefix="/reports", tags=["reports"])

SEVERITY_BY_POINTS = [
    (500, "Crítica"),
    (200, "Alta"),
    (100, "Média"),
    (0, "Baixa"),
]


def _severity_for(points: int) -> str:
    for threshold, label in SEVERITY_BY_POINTS:
        if points >= threshold:
            return label
    return "Baixa"


@router.post("/generate", response_model=ReportOut, status_code=201)
def generate_report(
    payload: ReportGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Compila um snapshot do que o usuário resolveu até agora em um
    relatório estruturado (Executive Summary, Findings, Methodology,
    Risk Rating). É um SNAPSHOT — gerar de novo depois de resolver mais
    labs produz um novo relatório, não atualiza o antigo (ver comentário
    no model Report).
    """
    correct_submissions = (
        db.query(Submission)
        .filter(Submission.user_id == user.id, Submission.correct == True)  # noqa: E712
        .order_by(Submission.submitted_at)
        .all()
    )

    findings = []
    for sub in correct_submissions:
        lab = (
            db.query(Lab)
            .join(Submission, Submission.lab_instance_id == sub.lab_instance_id)
            .filter(Submission.id == sub.id)
            .first()
        )
        # fallback: busca via lab_instance -> lab_id, caso o join acima não resolva
        if not lab:
            from app.models import LabInstance

            instance = db.query(LabInstance).filter(LabInstance.id == sub.lab_instance_id).first()
            lab = db.query(Lab).filter(Lab.id == instance.lab_id).first() if instance else None

        findings.append(
            {
                "title": lab.name if lab else "Lab desconhecido",
                "category": lab.category if lab else "n/d",
                "severity": _severity_for(sub.points_awarded),
                "points": sub.points_awarded,
                "evidence": f"Flag submetida e validada em {sub.submitted_at.isoformat()}",
                "remediation": "Ver documentação do lab correspondente para orientações de remediação.",
            }
        )

    total_points = sum(f["points"] for f in findings)

    content = {
        "executive_summary": (
            f"{user.email} concluiu {len(findings)} exercício(s) prático(s), totalizando "
            f"{total_points} pontos. Este relatório documenta as vulnerabilidades exploradas "
            f"com sucesso em ambientes isolados e fictícios da plataforma Vantage Range."
        ),
        "scope": "Ambientes de laboratório isolados e fictícios da plataforma Vantage Range. Nenhum sistema real ou de terceiros foi acessado.",
        "methodology": "Testes realizados manualmente pelo aluno seguindo as trilhas e objetivos de cada laboratório, com validação de flags server-side.",
        "findings": findings,
        "conclusion": (
            "Nenhuma vulnerabilidade real foi explorada fora do ambiente de treinamento. "
            "Este documento tem finalidade exclusivamente educacional."
        ),
    }

    report = Report(user_id=user.id, title=payload.title, content_json=content)
    db.add(report)
    db.commit()
    db.refresh(report)

    log_action(
        db, actor_user_id=user.id, action="report_generated",
        resource_type="report", resource_id=report.id, metadata={"findings_count": len(findings)},
    )

    return ReportOut.from_model(report)


@router.get("", response_model=list[ReportOut])
def list_my_reports(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    reports = db.query(Report).filter(Report.user_id == user.id).order_by(Report.generated_at.desc()).all()
    return [ReportOut.from_model(r) for r in reports]


@router.get("/{report_id}", response_model=ReportOut)
def get_report(report_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    if report.user_id != user.id and user.role.value not in ("org_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Você não tem acesso a este relatório")
    return ReportOut.from_model(report)
