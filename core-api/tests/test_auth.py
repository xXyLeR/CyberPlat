def test_register_and_login_success(client):
    r = client.post("/auth/register", json={"email": "a@example.com", "password": "StrongPass123!"})
    assert r.status_code == 201
    assert "access_token" in r.json()

    r2 = client.post("/auth/login", data={"username": "a@example.com", "password": "StrongPass123!"})
    assert r2.status_code == 200
    assert "access_token" in r2.json()


def test_login_wrong_password_returns_generic_error(client):
    client.post("/auth/register", json={"email": "b@example.com", "password": "StrongPass123!"})
    r = client.post("/auth/login", data={"username": "b@example.com", "password": "WrongPassword!"})
    assert r.status_code == 401
    # Mensagem genérica — não revela se o problema foi email ou senha.
    assert r.json()["detail"] == "Email ou senha inválidos"


def test_login_nonexistent_user_same_generic_error(client):
    r = client.post("/auth/login", data={"username": "nobody@example.com", "password": "whatever"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Email ou senha inválidos"


def test_duplicate_registration_rejected(client):
    client.post("/auth/register", json={"email": "dup@example.com", "password": "StrongPass123!"})
    r = client.post("/auth/register", json={"email": "dup@example.com", "password": "AnotherPass123!"})
    assert r.status_code == 400


def test_protected_endpoint_requires_token(client):
    r = client.get("/users/me")
    assert r.status_code == 401


def test_new_registrations_are_always_student_role(client):
    from tests.conftest import register_and_login

    headers = register_and_login(client, email="newuser@example.com")
    me = client.get("/users/me", headers=headers).json()
    assert me["role"] == "student"
