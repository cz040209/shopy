from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import get_db
from app.main import app
from app.models import AuthSession, Cart, User, Wallet
from app.security import verify_password


def auth_client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_register_creates_user_related_records_and_session(db_session):
    client = auth_client(db_session)
    try:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Jeffrey Tan",
                "email": "JEFFREY@example.com ",
                "password": "Orbit2026!",
            },
        )

        assert response.status_code == 201
        assert response.json()["user"]["email"] == "jeffrey@example.com"
        assert response.json()["user"]["full_name"] == "Jeffrey Tan"
        assert "shopy_session" in response.cookies

        user = db_session.scalar(select(User).where(User.email == "jeffrey@example.com"))
        assert user is not None
        assert user.password_hash != "Orbit2026!"
        assert verify_password("Orbit2026!", user.password_hash)
        assert db_session.scalar(select(func.count()).select_from(Wallet)) == 1
        assert db_session.scalar(select(func.count()).select_from(Cart)) == 1
        assert db_session.scalar(select(func.count()).select_from(AuthSession)) == 1

        me_response = client.get("/api/v1/auth/me")
        assert me_response.status_code == 200
        assert me_response.json()["id"] == str(user.id)
    finally:
        app.dependency_overrides.clear()


def test_duplicate_registration_is_rejected(db_session):
    client = auth_client(db_session)
    payload = {
        "full_name": "Jeffrey Tan",
        "email": "member@example.com",
        "password": "Orbit2026!",
    }
    try:
        assert client.post("/api/v1/auth/register", json=payload).status_code == 201
        response = client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 409
        assert db_session.scalar(select(func.count()).select_from(User)) == 1
    finally:
        app.dependency_overrides.clear()


def test_login_me_and_logout_lifecycle(db_session):
    client = auth_client(db_session)
    payload = {
        "full_name": "Jeffrey Tan",
        "email": "member@example.com",
        "password": "Orbit2026!",
    }
    try:
        assert client.post("/api/v1/auth/register", json=payload).status_code == 201
        assert client.post("/api/v1/auth/logout").status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 401
        assert db_session.scalar(select(func.count()).select_from(AuthSession)) == 0

        invalid = client.post(
            "/api/v1/auth/login",
            json={"email": payload["email"], "password": "wrong-password"},
        )
        assert invalid.status_code == 401

        login = client.post(
            "/api/v1/auth/login",
            json={"email": payload["email"], "password": payload["password"]},
        )
        assert login.status_code == 200
        assert login.json()["user"]["email"] == payload["email"]
        assert client.get("/api/v1/auth/me").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_registration_validates_password_strength(db_session):
    client = auth_client(db_session)
    try:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Jeffrey Tan",
                "email": "member@example.com",
                "password": "onlyletters",
            },
        )

        assert response.status_code == 422
        assert db_session.scalar(select(func.count()).select_from(User)) == 0
    finally:
        app.dependency_overrides.clear()
