import pyotp

from tests.conftest import register_and_login


def test_login_without_mfa_returns_access_token_directly(client):
    headers = register_and_login(client, email="nomfa@example.com")
    assert headers["Authorization"].startswith("Bearer ")


def test_mfa_setup_and_verify_flow(client):
    headers = register_and_login(client, email="mfauser@example.com")

    setup = client.post("/auth/mfa/setup", headers=headers).json()
    secret = setup["secret"]
    assert "otpauth://" in setup["provisioning_uri"]

    code = pyotp.TOTP(secret).now()
    verify_resp = client.post("/auth/mfa/verify", json={"code": code}, headers=headers)
    assert verify_resp.status_code == 200

    # UserOut não expõe mfa_enabled hoje, então checamos indiretamente:
    # o próximo login deve exigir segundo fator.
    login_resp = client.post(
        "/auth/login", data={"username": "mfauser@example.com", "password": "StrongPass123!"}
    )
    assert login_resp.json()["mfa_required"] is True
    assert login_resp.json()["access_token"] is None


def test_mfa_setup_with_wrong_code_does_not_enable(client):
    headers = register_and_login(client, email="wrongcode@example.com")
    client.post("/auth/mfa/setup", headers=headers)

    r = client.post("/auth/mfa/verify", json={"code": "000000"}, headers=headers)
    assert r.status_code == 400

    # Login normal (sem exigir MFA) continua funcionando, já que nunca
    # foi confirmado.
    login_resp = client.post(
        "/auth/login", data={"username": "wrongcode@example.com", "password": "StrongPass123!"}
    )
    assert login_resp.json()["mfa_required"] is False


def test_full_mfa_login_flow(client):
    headers = register_and_login(client, email="fullmfa@example.com")
    setup = client.post("/auth/mfa/setup", headers=headers).json()
    secret = setup["secret"]
    client.post("/auth/mfa/verify", json={"code": pyotp.TOTP(secret).now()}, headers=headers)

    login_resp = client.post(
        "/auth/login", data={"username": "fullmfa@example.com", "password": "StrongPass123!"}
    )
    pending_token = login_resp.json()["mfa_pending_token"]
    assert pending_token

    final = client.post(
        "/auth/mfa/login-verify",
        json={"mfa_pending_token": pending_token, "code": pyotp.TOTP(secret).now()},
    )
    assert final.status_code == 200
    assert final.json()["access_token"] is not None


def test_mfa_pending_token_cannot_be_used_as_access_token(client):
    """
    Garante que o MFA não pode ser 'pulado' usando o token intermediário
    como se fosse um access_token normal.
    """
    headers = register_and_login(client, email="bypasstest@example.com")
    setup = client.post("/auth/mfa/setup", headers=headers).json()
    secret = setup["secret"]
    client.post("/auth/mfa/verify", json={"code": pyotp.TOTP(secret).now()}, headers=headers)

    login_resp = client.post(
        "/auth/login", data={"username": "bypasstest@example.com", "password": "StrongPass123!"}
    )
    pending_token = login_resp.json()["mfa_pending_token"]

    r = client.get("/users/me", headers={"Authorization": f"Bearer {pending_token}"})
    assert r.status_code == 401


def test_mfa_login_verify_wrong_code_rejected(client):
    headers = register_and_login(client, email="wrongfinal@example.com")
    setup = client.post("/auth/mfa/setup", headers=headers).json()
    secret = setup["secret"]
    client.post("/auth/mfa/verify", json={"code": pyotp.TOTP(secret).now()}, headers=headers)

    login_resp = client.post(
        "/auth/login", data={"username": "wrongfinal@example.com", "password": "StrongPass123!"}
    )
    pending_token = login_resp.json()["mfa_pending_token"]

    r = client.post(
        "/auth/mfa/login-verify",
        json={"mfa_pending_token": pending_token, "code": "000000"},
    )
    assert r.status_code == 401


def test_mfa_disable_requires_valid_code(client):
    headers = register_and_login(client, email="disabletest@example.com")
    setup = client.post("/auth/mfa/setup", headers=headers).json()
    secret = setup["secret"]
    client.post("/auth/mfa/verify", json={"code": pyotp.TOTP(secret).now()}, headers=headers)

    r_wrong = client.post("/auth/mfa/disable", json={"code": "000000"}, headers=headers)
    assert r_wrong.status_code == 400

    r_right = client.post(
        "/auth/mfa/disable", json={"code": pyotp.TOTP(secret).now()}, headers=headers
    )
    assert r_right.status_code == 200

    login_resp = client.post(
        "/auth/login", data={"username": "disabletest@example.com", "password": "StrongPass123!"}
    )
    assert login_resp.json()["mfa_required"] is False
