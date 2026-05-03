from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from backend.main import app
    return TestClient(app, raise_server_exceptions=False)


class TestScheduleApi:
    def test_get_schedule_returns_list(self, client):
        mock_rows = [
            ({"id": "1", "type": "ship", "name": "테스트선", "start": "2026-04-01T08:00", "end": "2026-04-02T08:00"},),
        ]
        with patch("backend.main._db_fetch_items", return_value=mock_rows):
            res = client.get("/api/schedule")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert data[0]["id"] == "1"

    def test_get_schedule_returns_empty_list_on_db_error(self, client):
        with patch("backend.main._db_fetch_items", side_effect=Exception("db error")):
            res = client.get("/api/schedule")
        assert res.status_code == 200
        assert res.json() == []

    def test_put_schedule_saves_items(self, client):
        items = [{"id": "1", "type": "ship", "name": "테스트선", "start": "2026-04-01T08:00", "end": "2026-04-02T08:00"}]
        with patch("backend.main._db_save_items") as mock_save:
            res = client.put("/api/schedule", json=items)
        assert res.status_code == 200
        mock_save.assert_called_once()


class TestBanchuApi:
    def test_get_banchu_returns_list(self, client):
        mock_rows = [
            ({"id": "2", "cat": "CW1", "name": "슬라그", "start": "2026-04-01T08:00", "end": "2026-04-01T16:00"},),
        ]
        with patch("backend.main._db_fetch_items", return_value=mock_rows):
            res = client.get("/api/banchu")
        assert res.status_code == 200
        data = res.json()
        assert data[0]["id"] == "2"

    def test_put_banchu_saves_items(self, client):
        items = [{"id": "2", "cat": "CW1", "name": "슬라그", "start": "2026-04-01T08:00", "end": "2026-04-01T16:00"}]
        with patch("backend.main._db_save_items") as mock_save:
            res = client.put("/api/banchu", json=items)
        assert res.status_code == 200
        mock_save.assert_called_once()
