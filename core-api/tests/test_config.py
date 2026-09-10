import pytest

from app.config import Settings


def test_short_jwt_secret_allowed_in_development():
    s = Settings(jwt_secret_key="short", environment="development")
    assert s.jwt_secret_key == "short"


def test_short_jwt_secret_rejected_in_production():
    with pytest.raises(ValueError, match="menos de 32 bytes"):
        Settings(jwt_secret_key="short", environment="production")


def test_strong_jwt_secret_allowed_in_production():
    strong_secret = "a" * 32
    s = Settings(jwt_secret_key=strong_secret, environment="production")
    assert s.jwt_secret_key == strong_secret
