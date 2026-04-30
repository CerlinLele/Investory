from fastapi.testclient import TestClient

from investory.main import create_app


def test_health_returns_app_config():
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "app_name": app.state.config.app_name,
        "app_env": app.state.config.app_env,
    }
