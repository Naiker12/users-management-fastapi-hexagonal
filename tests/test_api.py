from uuid import uuid4

from fastapi.testclient import TestClient

from users_management import main
from users_management.domain import User, UserRole, UserStatus


class FakeService:
    def __init__(self):
        self.user = User(name="Ana", email="ana@example.com", password_hash="secret",
                         role=UserRole.MEMBER, status=UserStatus.PENDING)

    def create(self, data):
        return self.user

    def list(self):
        return [self.user]

    def get(self, user_id):
        return self.user

    def update(self, user_id, data):
        return self.user

    def delete(self, user_id):
        return None

    def login(self, email, password):
        return "signed-token", 900


def client():
    service = FakeService()
    main.app.dependency_overrides[main.get_service] = lambda: service
    main.security_service.decode = lambda token: {"sub": str(service.user.id)}
    return TestClient(main.app)


def test_login_and_create_contract():
    http = client()
    login = http.post("/api/auth/login", json={"email": "admin@example.com", "password": "secret"})
    assert login.status_code == 200
    assert login.json()["tokenType"] == "Bearer"
    created = http.post("/api/users", json={"name": "Ana", "email": "ana@example.com",
                                             "password": "Clave1234!", "role": "MEMBER"})
    assert created.status_code == 201
    assert created.json()["status"] == "PENDING"
    assert "password" not in created.json()
    main.app.dependency_overrides.clear()


def test_protected_routes_require_bearer_and_hide_password():
    http = client()
    response = http.get("/api/users")
    assert response.status_code == 401
    assert response.json() == {"status": 401, "message": "Autenticacion requerida o token invalido."}
    response = http.get("/api/users", headers={"Authorization": "Bearer valid"})
    assert response.status_code == 200
    assert "password" not in response.json()[0]
    main.app.dependency_overrides.clear()


def test_crud_routes_and_openapi():
    http = client()
    headers = {"Authorization": "Bearer valid"}
    uid = str(uuid4())
    assert http.get(f"/api/users/{uid}", headers=headers).status_code == 200
    assert http.put(f"/api/users/{uid}", headers=headers, json={"name": "Ana"}).status_code == 200
    assert http.delete(f"/api/users/{uid}", headers=headers).status_code == 204
    assert http.get("/swagger-ui/index.html").status_code == 200
    assert http.get("/v3/api-docs").status_code == 200
    main.app.dependency_overrides.clear()
