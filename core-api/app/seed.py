"""
Popula dados iniciais de demonstração:
- Organização "default"
- 1 usuário admin, 1 instrutor, 1 aluno
- Lab 01 — Web Fundamentals (beginner), com 1 flag

Executar com: python -m app.seed
"""
from app.achievements import ensure_default_badges
from app.database import Base, SessionLocal, engine
from app.lab_schema import validate_lab_definition
<<<<<<< HEAD
from app.models import (
    Challenge,
    Course,
    Flag,
    Lab,
    LearningPath,
    Organization,
    QuizQuestion,
    RoleName,
    User,
)
=======
from app.models import Course, Flag, Lab, LearningPath, Organization, QuizQuestion, RoleName, User
>>>>>>> 7da46cdbcf65aa44a988cbff473c3d4a232500be
from app.security import hash_password, sha256_hex

Base.metadata.create_all(bind=engine)


LAB_01_DEFINITION = {
    "name": "Web Fundamentals",
    "difficulty": "beginner",
    "objectives": ["http", "authentication", "input_validation"],
    "machines": [
        {"name": "web01", "image": "vantage-range/web-fundamentals:latest", "ports": [8080]}
    ],
    "network": {"isolated": True},
    "flags": [
        {"id": "flag_01", "points": 100, "value": "VANTAGE{auth_bypass_via_idor_demo}"}
    ],
}


def run():
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.name == "default").first()
        if not org:
            org = Organization(name="default")
            db.add(org)
            db.commit()
            db.refresh(org)

        def ensure_user(email: str, password: str, role: RoleName) -> User:
            user = db.query(User).filter(User.email == email).first()
            if user:
                return user
            user = User(
                email=email,
                password_hash=hash_password(password),
                role=role,
                organization_id=org.id,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"  criado: {email} ({role.value})")
            return user

        admin = ensure_user("admin@vantage-range.example.com", "ChangeMe123!", RoleName.ORG_ADMIN)
        ensure_user("instructor@vantage-range.example.com", "ChangeMe123!", RoleName.INSTRUCTOR)
        ensure_user("student@vantage-range.example.com", "ChangeMe123!", RoleName.STUDENT)

        validate_lab_definition(LAB_01_DEFINITION)

        lab = db.query(Lab).filter(Lab.slug == "web-fundamentals").first()
        if not lab:
            lab = Lab(
                name=LAB_01_DEFINITION["name"],
                slug="web-fundamentals",
                description="Introdução a HTTP, autenticação e validação de entrada.",
                category="web",
                difficulty=LAB_01_DEFINITION["difficulty"],
                estimated_minutes=30,
                definition=LAB_01_DEFINITION,
                status="published",
                created_by=admin.id,
            )
            db.add(lab)
            db.commit()
            db.refresh(lab)

            for flag_def in LAB_01_DEFINITION["flags"]:
                db.add(
                    Flag(
                        lab_id=lab.id,
                        flag_key=flag_def["id"],
                        flag_hash=sha256_hex(flag_def["value"]),
                        points=flag_def["points"],
                    )
                )
            db.commit()
            print(f"  criado lab: {lab.slug}")

        ensure_default_badges(db)

        # --- Learning Path de demonstração: Pentest Fundamentals ---
        path = db.query(LearningPath).filter(LearningPath.slug == "pentest-fundamentals").first()
        if not path:
            path = LearningPath(
                title="Pentest Fundamentals",
                slug="pentest-fundamentals",
                description="Trilha introdutória cobrindo fundamentos de HTTP, autenticação e uma prática guiada de Web Pentest.",
                status="published",
                created_by=admin.id,
            )
            db.add(path)
            db.commit()
            db.refresh(path)

            course_theory = Course(
                learning_path_id=path.id,
                title="Fundamentos de HTTP",
                slug="http-fundamentals",
                description="Métodos, status codes, headers e o ciclo requisição/resposta.",
                order_index=1,
                estimated_minutes=15,
            )
            db.add(course_theory)
            db.commit()
            db.refresh(course_theory)

            db.add(
                QuizQuestion(
                    course_id=course_theory.id,
                    prompt="Qual status HTTP indica que o recurso não foi encontrado?",
                    options=["200 OK", "301 Moved Permanently", "404 Not Found", "500 Internal Server Error"],
                    correct_index=2,
                    explanation="404 Not Found indica que o servidor não encontrou o recurso solicitado.",
                )
            )
            db.add(
                QuizQuestion(
                    course_id=course_theory.id,
                    prompt="Qual método HTTP é normalmente usado para submeter dados de um formulário de login?",
                    options=["GET", "POST", "DELETE", "OPTIONS"],
                    correct_index=1,
                    explanation="POST envia dados no corpo da requisição, mais adequado para credenciais do que GET (que expõe na URL).",
                )
            )

            course_practice = Course(
                learning_path_id=path.id,
                title="Web Pentest guiado — Web Fundamentals",
                slug="guided-web-fundamentals",
                description="Aplique o que aprendeu resolvendo o Lab 01 (Web Fundamentals).",
                order_index=2,
                estimated_minutes=30,
                lab_id=lab.id,
            )
            db.add(course_practice)
            db.commit()
            print(f"  criada learning path: {path.slug} (2 cursos)")

<<<<<<< HEAD
        # --- Desafios de CTF de demonstração ---
        if not db.query(Challenge).filter(Challenge.slug == "crypto-101").first():
            db.add(
                Challenge(
                    title="Crypto 101 — Base64 não é criptografia",
                    slug="crypto-101",
                    category="cryptography",
                    difficulty="beginner",
                    description=(
                        "Interceptamos esta mensagem em um canal fictício de exfiltração: "
                        "'VkFOVEFHRXtiYXNlNjRfaXNfbm90X2VuY3J5cHRpb259'. Decodifique e submeta a flag."
                    ),
                    points=100,
                    flag_hash=sha256_hex("VANTAGE{base64_is_not_encryption}"),
                    hints=["O texto termina com '=', um sinal clássico de um encoding, não uma cifra."],
                    status="published",
                )
            )
        if not db.query(Challenge).filter(Challenge.slug == "forensics-101").first():
            db.add(
                Challenge(
                    title="Forensics 101 — Metadados esquecidos",
                    slug="forensics-101",
                    category="forensics",
                    difficulty="beginner",
                    description=(
                        "Um analista júnior fictício da ACME Corp deixou credenciais em um "
                        "comentário de commit antigo. A flag é o valor que ele esqueceu lá: "
                        "VANTAGE{never_commit_secrets}."
                    ),
                    points=100,
                    flag_hash=sha256_hex("VANTAGE{never_commit_secrets}"),
                    hints=["Este próprio exercício já contém a resposta — é sobre reconhecer o padrão, não decifrar nada."],
                    status="published",
                )
            )
        db.commit()
        print("  criados desafios de CTF: crypto-101, forensics-101")

=======
>>>>>>> 7da46cdbcf65aa44a988cbff473c3d4a232500be
        print("Seed concluído.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
