from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_storage_file(name: str, size: int = 1024, updated_at: str = "2026-01-01T00:00:00") -> dict:
    return {"name": name, "metadata": {"size": size}, "updated_at": updated_at}


class TestUploadedStorageFiles:
    def test_returns_only_pattern_matched_files(self):
        mock_files = [
            _make_storage_file("2025_하역률.xlsx"),
            _make_storage_file("2024_하역률.xls"),
            _make_storage_file("readme.txt"),
            _make_storage_file("random.csv"),
        ]
        mock_bucket = MagicMock()
        mock_bucket.list.return_value = mock_files

        with patch("backend.main._storage_client", return_value=mock_bucket):
            from backend.main import _uploaded_storage_files
            result = _uploaded_storage_files()

        names = [f["name"] for f in result]
        assert "2025_하역률.xlsx" in names
        assert "2024_하역률.xls" in names
        assert "readme.txt" not in names
        assert "random.csv" not in names

    def test_returns_empty_on_exception(self):
        mock_bucket = MagicMock()
        mock_bucket.list.side_effect = Exception("network error")

        with patch("backend.main._storage_client", return_value=mock_bucket):
            from backend.main import _uploaded_storage_files
            result = _uploaded_storage_files()

        assert result == []


class TestUploadedExcelFileDetails:
    def test_returns_name_size_updated_at(self):
        mock_files = [
            _make_storage_file("2025_하역률.xlsx", size=2048, updated_at="2026-03-01T12:00:00"),
        ]
        mock_bucket = MagicMock()
        mock_bucket.list.return_value = mock_files

        with patch("backend.main._storage_client", return_value=mock_bucket):
            from backend.main import _uploaded_excel_file_details
            result = _uploaded_excel_file_details()

        assert len(result) == 1
        assert result[0]["name"] == "2025_하역률.xlsx"
        assert result[0]["size_bytes"] == 2048
        assert result[0]["updated_at"] == "2026-03-01T12:00:00"
