from app.models import RoleName
from tests.conftest import register_and_login
from tests.test_rbac import promote_role, VALID_LAB_DEFINITION


def create_path_with_lab_course(client, db_engine):
    instr_headers = register_and_login(client, email="lpinstr@example.com")
    promote_role(db_engine, "lpinstr@example.com", RoleName.INSTRUCTOR)

    lab_resp = client.post(
        "/labs",
        json={"name": "LP Lab", "slug": "lp-lab", "definition": VALID_LAB_DEFINITION},
        headers=instr_headers,
    )
    lab_id = lab_resp.json()["id"]

    path_resp = client.post(
        "/learning-paths",
        json={"title": "Test Path", "slug": "test-path"},
        headers=instr_headers,
    )
    path_id = path_resp.json()["id"]

    course_resp = client.post(
        f"/learning-paths/{path_id}/courses",
        json={
            "title": "Practical Lab Course",
            "slug": "practical-lab-course",
            "order_index": 1,
            "lab_id": lab_id,
        },
        headers=instr_headers,
    )
    return path_id, course_resp.json()["id"], lab_id, instr_headers


def test_student_cannot_create_learning_path(client, db_engine):
    headers = register_and_login(client, email="lpstudent@example.com")
    r = client.post(
        "/learning-paths", json={"title": "X", "slug": "x-path"}, headers=headers
    )
    assert r.status_code == 403


def test_course_with_both_lab_and_quiz_rejected(client, db_engine):
    instr_headers = register_and_login(client, email="badcourse@example.com")
    promote_role(db_engine, "badcourse@example.com", RoleName.INSTRUCTOR)

    lab_resp = client.post(
        "/labs",
        json={"name": "X Lab", "slug": "x-lab-badcourse", "definition": VALID_LAB_DEFINITION},
        headers=instr_headers,
    )
    lab_id = lab_resp.json()["id"]

    path_resp = client.post(
        "/learning-paths", json={"title": "P", "slug": "p-badcourse"}, headers=instr_headers
    )
    path_id = path_resp.json()["id"]

    r = client.post(
        f"/learning-paths/{path_id}/courses",
        json={
            "title": "Bad Course",
            "slug": "bad-course",
            "lab_id": lab_id,
            "quiz_questions": [
                {"prompt": "?", "options": ["a", "b"], "correct_index": 0}
            ],
        },
        headers=instr_headers,
    )
    assert r.status_code == 422


def test_lab_flag_completion_propagates_to_course_progress(client, db_engine):
    path_id, course_id, lab_id, _instr_headers = create_path_with_lab_course(client, db_engine)

    student_headers = register_and_login(client, email="lpflow@example.com")

    detail = client.get(f"/learning-paths/{path_id}", headers=student_headers).json()
    assert detail["progress_percent"] == 0
    assert detail["courses"][0]["completed"] is False

    session = client.post(
        "/lab-sessions", json={"lab_id": lab_id}, headers=student_headers
    ).json()

    client.post(
        "/submissions",
        json={"lab_instance_id": session["id"], "flag_value": "FLAG{test}"},
        headers=student_headers,
    )

    detail_after = client.get(f"/learning-paths/{path_id}", headers=student_headers).json()
    assert detail_after["progress_percent"] == 100
    assert detail_after["courses"][0]["completed"] is True


def test_first_blood_achievement_awarded_on_first_correct_flag(client, db_engine):
    path_id, course_id, lab_id, _ = create_path_with_lab_course(client, db_engine)
    student_headers = register_and_login(client, email="firstblood@example.com")

    achievements_before = client.get("/users/me/achievements", headers=student_headers).json()
    assert achievements_before == []

    session = client.post(
        "/lab-sessions", json={"lab_id": lab_id}, headers=student_headers
    ).json()
    client.post(
        "/submissions",
        json={"lab_instance_id": session["id"], "flag_value": "FLAG{test}"},
        headers=student_headers,
    )

    achievements_after = client.get("/users/me/achievements", headers=student_headers).json()
    slugs = {a["badge"]["slug"] for a in achievements_after}
    assert "first_blood" in slugs


def test_quiz_flow_pass_and_fail(client, db_engine):
    instr_headers = register_and_login(client, email="quizinstr@example.com")
    promote_role(db_engine, "quizinstr@example.com", RoleName.INSTRUCTOR)

    path_resp = client.post(
        "/learning-paths", json={"title": "Quiz Path", "slug": "quiz-path"}, headers=instr_headers
    )
    path_id = path_resp.json()["id"]

    course_resp = client.post(
        f"/learning-paths/{path_id}/courses",
        json={
            "title": "Quiz Course",
            "slug": "quiz-course",
            "quiz_questions": [
                {"prompt": "2+2?", "options": ["3", "4"], "correct_index": 1},
                {"prompt": "Capital de SP?", "options": ["Rio", "São Paulo"], "correct_index": 1},
            ],
        },
        headers=instr_headers,
    )
    course_id = course_resp.json()["id"]

    student_headers = register_and_login(client, email="quizstudent@example.com")
    questions = client.get(f"/courses/{course_id}/quiz", headers=student_headers).json()

    # Nunca deve vazar o índice correto para o aluno.
    for q in questions:
        assert "correct_index" not in q

    q_ids = [q["id"] for q in questions]

    # Errando tudo: não passa, não completa o curso.
    r_fail = client.post(
        f"/courses/{course_id}/quiz/submit",
        json={"answers": {q_ids[0]: 0, q_ids[1]: 0}},
        headers=student_headers,
    )
    assert r_fail.json()["passed"] is False
    assert r_fail.json()["course_completed"] is False

    # Acertando tudo: passa e completa.
    r_pass = client.post(
        f"/courses/{course_id}/quiz/submit",
        json={"answers": {q_ids[0]: 1, q_ids[1]: 1}},
        headers=student_headers,
    )
    assert r_pass.json()["passed"] is True
    assert r_pass.json()["score_percent"] == 100
    assert r_pass.json()["course_completed"] is True


def test_theory_only_course_manual_completion(client, db_engine):
    instr_headers = register_and_login(client, email="theoryinstr@example.com")
    promote_role(db_engine, "theoryinstr@example.com", RoleName.INSTRUCTOR)

    path_resp = client.post(
        "/learning-paths", json={"title": "Theory Path", "slug": "theory-path"}, headers=instr_headers
    )
    path_id = path_resp.json()["id"]
    course_resp = client.post(
        f"/learning-paths/{path_id}/courses",
        json={"title": "Pure Theory", "slug": "pure-theory"},
        headers=instr_headers,
    )
    course_id = course_resp.json()["id"]

    student_headers = register_and_login(client, email="theorystudent@example.com")
    r = client.post(f"/courses/{course_id}/complete", headers=student_headers)
    assert r.status_code == 200
    assert r.json()["completed"] is True

    # Idempotente: chamar de novo não quebra nem duplica.
    r2 = client.post(f"/courses/{course_id}/complete", headers=student_headers)
    assert r2.status_code == 200


def test_path_finisher_badge_awarded_when_all_courses_complete(client, db_engine):
    instr_headers = register_and_login(client, email="finisherinstr@example.com")
    promote_role(db_engine, "finisherinstr@example.com", RoleName.INSTRUCTOR)

    path_resp = client.post(
        "/learning-paths", json={"title": "Finisher Path", "slug": "finisher-path"},
        headers=instr_headers,
    )
    path_id = path_resp.json()["id"]
    course_resp = client.post(
        f"/learning-paths/{path_id}/courses",
        json={"title": "Only Course", "slug": "only-course"},
        headers=instr_headers,
    )
    course_id = course_resp.json()["id"]

    student_headers = register_and_login(client, email="finisherstudent@example.com")
    client.post(f"/courses/{course_id}/complete", headers=student_headers)

    achievements = client.get("/users/me/achievements", headers=student_headers).json()
    slugs = {a["badge"]["slug"] for a in achievements}
    assert "path_finisher" in slugs
