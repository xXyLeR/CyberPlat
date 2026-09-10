from app.models import RoleName
from tests.conftest import register_and_login
from tests.test_rbac import promote_role


def create_published_challenge(client, db_engine, **overrides):
    instr_headers = register_and_login(client, email="ctfinstr@example.com")
    promote_role(db_engine, "ctfinstr@example.com", RoleName.INSTRUCTOR)

    payload = {
        "title": "SQLi 101",
        "slug": "sqli-101",
        "category": "web",
        "difficulty": "beginner",
        "points": 150,
        "flag_value": "FLAG{ctf_test_value}",
        "hints": ["Tente aspas simples no campo de busca"],
    }
    payload.update(overrides)
    resp = client.post("/challenges", json=payload, headers=instr_headers)
    return resp, instr_headers


def test_student_cannot_create_challenge(client, db_engine):
    headers = register_and_login(client, email="ctfstudent@example.com")
    r = client.post(
        "/challenges",
        json={"title": "X", "slug": "x", "category": "web", "flag_value": "FLAG{x}"},
        headers=headers,
    )
    assert r.status_code == 403


def test_instructor_can_create_challenge_and_flag_is_never_returned(client, db_engine):
    resp, _ = create_published_challenge(client, db_engine)
    assert resp.status_code == 201
    assert "flag_value" not in resp.json()
    assert "flag_hash" not in resp.json()
    assert resp.json()["hint_count"] == 1


def test_list_challenges_hides_hints_but_detail_shows_them(client, db_engine):
    resp, instr_headers = create_published_challenge(client, db_engine, slug="sqli-list-test")

    listed = client.get("/challenges", headers=instr_headers).json()
    entry = next(c for c in listed if c["slug"] == "sqli-list-test")
    assert "hints" not in entry  # ChallengeOut não expõe hints, só hint_count
    assert entry["hint_count"] == 1

    detail = client.get(f"/challenges/{resp.json()['id']}", headers=instr_headers).json()
    assert detail["hints"] == ["Tente aspas simples no campo de busca"]


def test_correct_flag_awards_points_and_wrong_does_not(client, db_engine):
    resp, _ = create_published_challenge(client, db_engine, slug="sqli-score-test")
    challenge_id = resp.json()["id"]

    student_headers = register_and_login(client, email="ctfscorer@example.com")

    r_wrong = client.post(
        f"/challenges/{challenge_id}/submit", json={"flag_value": "FLAG{wrong}"}, headers=student_headers
    )
    assert r_wrong.json()["correct"] is False
    assert r_wrong.json()["points_awarded"] == 0

    r_correct = client.post(
        f"/challenges/{challenge_id}/submit",
        json={"flag_value": "FLAG{ctf_test_value}"},
        headers=student_headers,
    )
    assert r_correct.json()["correct"] is True
    assert r_correct.json()["points_awarded"] == 150

    me = client.get("/users/me", headers=student_headers).json()
    assert me["xp"] == 150


def test_resubmitting_correct_flag_does_not_double_award(client, db_engine):
    resp, _ = create_published_challenge(client, db_engine, slug="sqli-dup-test")
    challenge_id = resp.json()["id"]
    headers = register_and_login(client, email="ctfdup@example.com")

    client.post(f"/challenges/{challenge_id}/submit", json={"flag_value": "FLAG{ctf_test_value}"}, headers=headers)
    r2 = client.post(f"/challenges/{challenge_id}/submit", json={"flag_value": "FLAG{ctf_test_value}"}, headers=headers)
    assert r2.json()["points_awarded"] == 0

    me = client.get("/users/me", headers=headers).json()
    assert me["xp"] == 150  # não dobrou


def test_ctf_submission_rate_limited(client, db_engine):
    resp, _ = create_published_challenge(client, db_engine, slug="sqli-ratelimit-test")
    challenge_id = resp.json()["id"]
    headers = register_and_login(client, email="ctfratelimit@example.com")

    statuses = [
        client.post(f"/challenges/{challenge_id}/submit", json={"flag_value": "FLAG{wrong}"}, headers=headers).status_code
        for _ in range(8)
    ]
    assert 429 in statuses


def test_ctf_flag_awards_first_blood_achievement(client, db_engine):
    resp, _ = create_published_challenge(client, db_engine, slug="sqli-firstblood-test")
    challenge_id = resp.json()["id"]
    headers = register_and_login(client, email="ctffirstblood@example.com")

    client.post(f"/challenges/{challenge_id}/submit", json={"flag_value": "FLAG{ctf_test_value}"}, headers=headers)
    achievements = client.get("/users/me/achievements", headers=headers).json()
    slugs = {a["badge"]["slug"] for a in achievements}
    assert "first_blood" in slugs


def test_individual_leaderboard_orders_by_xp_desc(client, db_engine):
    resp, _ = create_published_challenge(client, db_engine, slug="sqli-leaderboard-test", points=300)
    challenge_id = resp.json()["id"]

    high_headers = register_and_login(client, email="ctfhigh@example.com")
    client.post(f"/challenges/{challenge_id}/submit", json={"flag_value": "FLAG{ctf_test_value}"}, headers=high_headers)

    low_headers = register_and_login(client, email="ctflow@example.com")

    board = client.get("/leaderboard", headers=low_headers).json()
    emails_in_order = [e["email"] for e in board]
    assert emails_in_order.index("ctfhigh@example.com") < emails_in_order.index("ctflow@example.com")
    assert board[0]["rank"] == 1


def test_team_leaderboard_sums_member_xp(client, db_engine):
    resp, _ = create_published_challenge(client, db_engine, slug="sqli-team-leaderboard-test", points=200)
    challenge_id = resp.json()["id"]

    admin_headers = register_and_login(client, email="ctfteamadmin@example.com")
    promote_role(db_engine, "ctfteamadmin@example.com", RoleName.ORG_ADMIN)
    team_id = client.post("/teams", json={"name": "CTF Squad"}, headers=admin_headers).json()["id"]

    member_headers = register_and_login(client, email="ctfteammember@example.com")
    client.post(f"/challenges/{challenge_id}/submit", json={"flag_value": "FLAG{ctf_test_value}"}, headers=member_headers)

    users = client.get("/users", headers=admin_headers).json()
    member = next(u for u in users if u["email"] == "ctfteammember@example.com")
    client.post(f"/teams/{team_id}/members", json={"user_id": member["id"]}, headers=admin_headers)

    board = client.get("/leaderboard/teams", headers=admin_headers).json()
    squad = next(e for e in board if e["team_name"] == "CTF Squad")
    assert squad["total_xp"] == 200
    assert squad["member_count"] == 1
