import pytest
from app import create_app
from app.extensions import db
import seed


@pytest.fixture()
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "RATELIMIT_ENABLED": False,
                      "EXPOSE_RESET_TOKEN": True})
    with app.app_context():
        seed.run(reset=True)
        yield app
        db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def login(client):
    def _login(email):
        r = client.post("/api/auth/login", json={"email": f"{email}@estateflow.demo", "password": "Demo@1234"})
        assert r.status_code == 200, r.get_json()
        return {"Authorization": "Bearer " + r.get_json()["data"]["token"]}
    return _login
