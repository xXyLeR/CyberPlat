from sqlalchemy.orm import sessionmaker

from app.models import RoleName, User
from tests.conftest import register_and_login

VALID_LAB_DEFINITION = {
    "machines": [{"name": "web01", "image": "vantage-range/web-fundamentals:latest"}],
    "network": {"isolated": True},
    "flags": [{"id": "flag_01", "points": 100, "value": "FLAG{test}"}],
}


def promote_role(db_engine, email: str, role: RoleName):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    user = session.query(User).filter(User.email == email).first()
    user.role = role
    session.add(user)
    session.commit()
    session.close()


def test_student_cannot_create_lab(client, db_engine):
    headers = register_and_login(client, email="student1@example.com")
    r = client.post(
        "/labs",
        json={
            "name": "Test Lab",
            "slug": "test-lab-1",
            "definition": VALID_LAB_DEFINITION,
        },
        headers=headers,
    )
    assert r.status_code == 403


def test_instructor_can_create_lab(client, db_engine):
    headers = register_and_login(client, email="instructor1@example.com")
    promote_role(db_engine, "instructor1@example.com", RoleName.INSTRUCTOR)

    r = client.post(
        "/labs",
        json={
            "name": "Test Lab",
            "slug": "test-lab-2",
            "definition": VALID_LAB_DEFINITION,
        },
        headers=headers,
    )
    assert r.status_code == 201
    assert r.json()["status"] == "published"


def test_student_cannot_list_all_users(client, db_engine):
    headers = register_and_login(client, email="student2@example.com")
    r = client.get("/users", headers=headers)
    assert r.status_code == 403


def test_admin_can_list_users(client, db_engine):
    headers = register_and_login(client, email="admin1@example.com")
    promote_role(db_engine, "admin1@example.com", RoleName.ORG_ADMIN)
    r = client.get("/users", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_student_cannot_read_audit_log(client, db_engine):
    headers = register_and_login(client, email="student3@example.com")
    r = client.get("/audit", headers=headers)
    assert r.status_code == 403
