from app.models import RoleName
from tests.conftest import register_and_login
from tests.test_rbac import promote_role


def test_org_admin_cannot_create_organization(client, db_engine):
    headers = register_and_login(client, email="orgadmin1@example.com")
    promote_role(db_engine, "orgadmin1@example.com", RoleName.ORG_ADMIN)

    r = client.post("/organizations", json={"name": "New Corp"}, headers=headers)
    assert r.status_code == 403


def test_super_admin_can_create_organization(client, db_engine):
    headers = register_and_login(client, email="superadmin1@example.com")
    promote_role(db_engine, "superadmin1@example.com", RoleName.SUPER_ADMIN)

    r = client.post("/organizations", json={"name": "New Corp 2"}, headers=headers)
    assert r.status_code == 201
    assert r.json()["name"] == "New Corp 2"


def test_org_admin_can_create_team(client, db_engine):
    headers = register_and_login(client, email="teamadmin@example.com")
    promote_role(db_engine, "teamadmin@example.com", RoleName.ORG_ADMIN)

    r = client.post("/teams", json={"name": "Red Team Alpha"}, headers=headers)
    assert r.status_code == 201
    assert r.json()["name"] == "Red Team Alpha"


def test_student_cannot_create_team(client, db_engine):
    headers = register_and_login(client, email="teamstudent@example.com")
    r = client.post("/teams", json={"name": "X"}, headers=headers)
    assert r.status_code == 403


def test_add_member_to_team(client, db_engine):
    admin_headers = register_and_login(client, email="teamadmin2@example.com")
    promote_role(db_engine, "teamadmin2@example.com", RoleName.ORG_ADMIN)
    team_id = client.post("/teams", json={"name": "Blue Team"}, headers=admin_headers).json()["id"]

    register_and_login(client, email="futuremember@example.com")

    # Precisa do user_id — busca via /users (admin only).
    users = client.get("/users", headers=admin_headers).json()
    member = next(u for u in users if u["email"] == "futuremember@example.com")

    r = client.post(
        f"/teams/{team_id}/members", json={"user_id": member["id"]}, headers=admin_headers
    )
    assert r.status_code == 200
    assert any(m["email"] == "futuremember@example.com" for m in r.json()["members"])


def test_team_manager_cannot_manage_other_teams(client, db_engine):
    admin_headers = register_and_login(client, email="teamadmin3@example.com")
    promote_role(db_engine, "teamadmin3@example.com", RoleName.ORG_ADMIN)

    team_a = client.post("/teams", json={"name": "Team A"}, headers=admin_headers).json()
    team_b = client.post("/teams", json={"name": "Team B"}, headers=admin_headers).json()

    manager_headers = register_and_login(client, email="manager1@example.com")
    promote_role(db_engine, "manager1@example.com", RoleName.TEAM_MANAGER)

    users = client.get("/users", headers=admin_headers).json()
    manager_user = next(u for u in users if u["email"] == "manager1@example.com")
    client.post(f"/teams/{team_a['id']}/members", json={"user_id": manager_user["id"]}, headers=admin_headers)

    register_and_login(client, email="targetuser@example.com")
    users = client.get("/users", headers=admin_headers).json()
    target = next(u for u in users if u["email"] == "targetuser@example.com")

    # Manager tenta adicionar alguém ao Team B, que não é o dele -> 403
    r = client.post(
        f"/teams/{team_b['id']}/members", json={"user_id": target["id"]}, headers=manager_headers
    )
    assert r.status_code == 403

    # Mas consegue adicionar ao próprio Team A
    r_ok = client.post(
        f"/teams/{team_a['id']}/members", json={"user_id": target["id"]}, headers=manager_headers
    )
    assert r_ok.status_code == 200
