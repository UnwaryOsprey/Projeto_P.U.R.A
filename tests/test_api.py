from fastapi.testclient import TestClient

from pura.adapters.local_bus import LocalBus
from pura.api.app import create_app
from pura.config import Settings
from pura.service import PuraService


def test_state_health_and_optimizer_switch():
    s = Settings(api_token="t0k")
    svc = PuraService(s, LocalBus())
    with TestClient(create_app(svc, autostart=False)) as c:
        assert c.get("/api/health").json()["status"] == "ok"
        assert set(c.get("/api/state").json()["rooms"]) == {"sala", "quarto"}
        assert c.post("/api/optimizer", json={"name": "sa"}).status_code == 401
        assert c.post("/api/optimizer", json={"name": "sa"}, headers={"X-API-Token": "t0k"}).status_code == 200
        assert c.post("/api/optimizer", json={"name": "x"}, headers={"X-API-Token": "t0k"}).status_code == 400
        assert "P.U.R.A." in c.get("/").text
