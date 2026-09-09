from app.models import RoleName
from tests.conftest import register_and_login
from tests.test_rbac import promote_role, VALID_LAB_DEFINITION


def test_student_cannot_access_analytics(client, db_engine):
    headers = register_and_login(client, email="analyticsstudent@example.com")
    r = client.get("/analytics/overview", headers=headers)
    assert r.status_code == 403


def test_analytics_overview_reflects_lab_activity(client, db_engine):
    instr_headers = register_and_login(client, email="analyticsinstr@example.com")
    promote_role(db_engine, "analyticsinstr@example.com", RoleName.INSTRUCTOR)
    lab_id = client.post(
        "/labs",
        json={"name": "Analytics Lab", "slug": "analytics-lab", "definition": VALID_LAB_DEFINITION},
        headers=instr_headers,
    ).json()["id"]

    student_headers = register_and_login(client, email="analyticsflow@example.com")
    session = client.post("/lab-sessions", json={"lab_id": lab_id}, headers=student_headers).json()
    client.post(
        "/submissions",
        json={"lab_instance_id": session["id"], "flag_value": "FLAG{test}"},
        headers=student_headers,
    )

    admin_headers = register_and_login(client, email="analyticsadmin@example.com")
    promote_role(db_engine, "analyticsadmin@example.com", RoleName.ORG_ADMIN)

    r = client.get("/analytics/overview", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total_lab_sessions"] >= 1
    assert data["labs_completed"] >= 1
    assert data["completion_rate_percent"] > 0
    assert any(finding["lab_name"] == "Analytics Lab" for finding in data["hardest_labs"])


def test_report_generation_reflects_solved_labs(client, db_engine):
    instr_headers = register_and_login(client, email="reportinstr@example.com")
    promote_role(db_engine, "reportinstr@example.com", RoleName.INSTRUCTOR)
    lab_id = client.post(
        "/labs",
        json={"name": "Report Lab", "slug": "report-lab", "definition": VALID_LAB_DEFINITION},
        headers=instr_headers,
    ).json()["id"]

    student_headers = register_and_login(client, email="reportflow@example.com")
    session = client.post("/lab-sessions", json={"lab_id": lab_id}, headers=student_headers).json()
    client.post(
        "/submissions",
        json={"lab_instance_id": session["id"], "flag_value": "FLAG{test}"},
        headers=student_headers,
    )

    r = client.post("/reports/generate", json={"title": "Meu Relatório"}, headers=student_headers)
    assert r.status_code == 201
    content = r.json()["content"]
    assert len(content["findings"]) == 1
    assert content["findings"][0]["title"] == "Report Lab"
    assert "Nenhum sistema real" in content["scope"] or "Nenhum" in content["scope"]


def test_report_generation_with_no_solves_has_empty_findings(client, db_engine):
    headers = register_and_login(client, email="emptyreport@example.com")
    r = client.post("/reports/generate", json={}, headers=headers)
    assert r.status_code == 201
    assert r.json()["content"]["findings"] == []


def test_user_cannot_read_someone_elses_report(client, db_engine):
    headers_a = register_and_login(client, email="reportownera@example.com")
    headers_b = register_and_login(client, email="reportownerb@example.com")

    report_id = client.post("/reports/generate", json={}, headers=headers_a).json()["id"]

    r = client.get(f"/reports/{report_id}", headers=headers_b)
    assert r.status_code == 403


def test_list_my_reports_only_shows_own(client, db_engine):
    headers_a = register_and_login(client, email="reportlist_a@example.com")
    headers_b = register_and_login(client, email="reportlist_b@example.com")

    client.post("/reports/generate", json={}, headers=headers_a)
    client.post("/reports/generate", json={}, headers=headers_b)

    reports_a = client.get("/reports", headers=headers_a).json()
    assert len(reports_a) == 1
