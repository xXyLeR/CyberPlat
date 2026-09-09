from app.models import RoleName
from tests.conftest import register_and_login
from tests.test_rbac import promote_role, VALID_LAB_DEFINITION


def create_published_lab(client, db_engine, slug="lab-scoring-test"):
    headers = register_and_login(client, email="instr@example.com")
    promote_role(db_engine, "instr@example.com", RoleName.INSTRUCTOR)
    r = client.post(
        "/labs",
        json={"name": "Scoring Lab", "slug": slug, "definition": VALID_LAB_DEFINITION},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_full_student_flow_start_lab_submit_flag_score(client, db_engine):
    lab_id = create_published_lab(client, db_engine)
    student_headers = register_and_login(client, email="flowstudent@example.com")

    # Inicia sessão de laboratório
    r = client.post("/lab-sessions", json={"lab_id": lab_id}, headers=student_headers)
    assert r.status_code == 201
    session = r.json()
    assert session["status"] == "running"
    instance_id = session["id"]

    # Submissão errada não pontua
    r_wrong = client.post(
        "/submissions",
        json={"lab_instance_id": instance_id, "flag_value": "FLAG{wrong_guess}"},
        headers=student_headers,
    )
    assert r_wrong.status_code == 201
    assert r_wrong.json()["correct"] is False
    assert r_wrong.json()["points_awarded"] == 0

    # Submissão correta pontua
    r_correct = client.post(
        "/submissions",
        json={"lab_instance_id": instance_id, "flag_value": "FLAG{test}"},
        headers=student_headers,
    )
    assert r_correct.status_code == 201
    assert r_correct.json()["correct"] is True
    assert r_correct.json()["points_awarded"] == 100

    # XP do usuário foi atualizado
    me = client.get("/users/me", headers=student_headers).json()
    assert me["xp"] == 100

    # Resubmeter a mesma flag correta não pontua de novo (evita duplicação)
    r_dup = client.post(
        "/submissions",
        json={"lab_instance_id": instance_id, "flag_value": "FLAG{test}"},
        headers=student_headers,
    )
    assert r_dup.json()["points_awarded"] == 0


def test_cannot_submit_flag_for_someone_elses_session(client, db_engine):
    lab_id = create_published_lab(client, db_engine, slug="lab-isolation-owner-test")
    student_a = register_and_login(client, email="usera@example.com")
    student_b = register_and_login(client, email="userb@example.com")

    r = client.post("/lab-sessions", json={"lab_id": lab_id}, headers=student_a)
    instance_id = r.json()["id"]

    r2 = client.post(
        "/submissions",
        json={"lab_instance_id": instance_id, "flag_value": "FLAG{test}"},
        headers=student_b,
    )
    assert r2.status_code == 404


def test_rate_limiting_on_flag_submission(client, db_engine):
    lab_id = create_published_lab(client, db_engine, slug="lab-ratelimit-test")
    headers = register_and_login(client, email="ratelimit@example.com")
    r = client.post("/lab-sessions", json={"lab_id": lab_id}, headers=headers)
    instance_id = r.json()["id"]

    statuses = []
    for _ in range(8):
        resp = client.post(
            "/submissions",
            json={"lab_instance_id": instance_id, "flag_value": "FLAG{wrong}"},
            headers=headers,
        )
        statuses.append(resp.status_code)

    assert 429 in statuses, "esperava que o rate limit bloqueasse após várias tentativas"


def test_max_concurrent_lab_instances_per_user(client, db_engine):
    lab_id = create_published_lab(client, db_engine, slug="lab-concurrency-test")
    headers = register_and_login(client, email="concurrency@example.com")

    r1 = client.post("/lab-sessions", json={"lab_id": lab_id}, headers=headers)
    r2 = client.post("/lab-sessions", json={"lab_id": lab_id}, headers=headers)
    r3 = client.post("/lab-sessions", json={"lab_id": lab_id}, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r3.status_code == 429  # limite de 2 labs simultâneos


def test_lab_definition_with_disallowed_image_is_rejected(client, db_engine):
    headers = register_and_login(client, email="badimage@example.com")
    promote_role(db_engine, "badimage@example.com", RoleName.INSTRUCTOR)

    bad_definition = {
        "machines": [{"name": "web01", "image": "docker.io/randomuser/whatever:latest"}],
        "network": {"isolated": True},
        "flags": [{"id": "flag_01", "points": 100, "value": "FLAG{x}"}],
    }
    r = client.post(
        "/labs",
        json={"name": "Bad Lab", "slug": "bad-lab", "definition": bad_definition},
        headers=headers,
    )
    assert r.status_code == 422


def test_lab_definition_cannot_disable_isolation(client, db_engine):
    headers = register_and_login(client, email="noniso@example.com")
    promote_role(db_engine, "noniso@example.com", RoleName.INSTRUCTOR)

    bad_definition = {
        "machines": [{"name": "web01", "image": "vantage-range/x:latest"}],
        "network": {"isolated": False},
        "flags": [{"id": "flag_01", "points": 100, "value": "FLAG{x}"}],
    }
    r = client.post(
        "/labs",
        json={"name": "Non Isolated Lab", "slug": "non-isolated-lab", "definition": bad_definition},
        headers=headers,
    )
    assert r.status_code == 422
