from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from backend.main import app
    return TestClient(app, raise_server_exceptions=False)


class TestYardSimApi:
    def test_get_returns_null_when_no_data(self, client):
        with patch("backend.main._db_get_yard_sim", return_value=None):
            res = client.get("/api/yard-sim?mode=overall")
        assert res.status_code == 200
        assert res.json() is None

    def test_get_returns_data_when_exists(self, client):
        mock_data = {"selfYard": {"capa": 248400}, "rentYard": {"capa": 172800}}
        with patch("backend.main._db_get_yard_sim", return_value=mock_data):
            res = client.get("/api/yard-sim?mode=import")
        assert res.status_code == 200
        assert res.json()["selfYard"]["capa"] == 248400

    def test_get_invalid_mode_returns_400(self, client):
        res = client.get("/api/yard-sim?mode=invalid")
        assert res.status_code == 400

    def test_put_saves_data(self, client):
        payload = {"selfYard": {"capa": 248400}, "rentYard": {"capa": 172800}}
        with patch("backend.main._db_save_yard_sim") as mock_save:
            res = client.put("/api/yard-sim?mode=overall", json=payload)
        assert res.status_code == 200
        mock_save.assert_called_once_with("overall", payload)

    def test_put_invalid_mode_returns_400(self, client):
        res = client.put("/api/yard-sim?mode=bad", json={})
        assert res.status_code == 400
