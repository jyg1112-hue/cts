from __future__ import annotations

import pytest


@pytest.fixture()
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.main.UNLOADING_UPLOAD_DIR", tmp_path)
    return tmp_path


class TestUploadedStorageFiles:
    def test_returns_only_pattern_matched_files(self, upload_dir):
        (upload_dir / "2025_unloading.xlsx").write_bytes(b"x")
        (upload_dir / "2024_unloading.xls").write_bytes(b"y")
        (upload_dir / "readme.txt").write_text("a", encoding="utf-8")
        (upload_dir / "random.csv").write_text("b", encoding="utf-8")

        from backend.main import _uploaded_storage_files

        result = _uploaded_storage_files()
        names = [f["name"] for f in result]
        assert "2025_unloading.xlsx" in names
        assert "2024_unloading.xls" in names
        assert "readme.txt" not in names
        assert "random.csv" not in names

    def test_returns_empty_when_upload_dir_missing(self, monkeypatch):
        import tempfile
        from pathlib import Path

        missing = Path(tempfile.gettempdir()) / "missing_upload_dir_port_ops_test_xyz"
        if missing.exists():
            missing.rmdir()
        monkeypatch.setattr("backend.main.UNLOADING_UPLOAD_DIR", missing)

        from backend.main import _uploaded_storage_files

        assert _uploaded_storage_files() == []


class TestUploadedExcelFileDetails:
    def test_returns_name_size_updated_at(self, upload_dir):
        target = upload_dir / "2025_unloading.xlsx"
        target.write_bytes(b"0" * 2048)

        from backend.main import _uploaded_excel_file_details

        result = _uploaded_excel_file_details()
        assert len(result) == 1
        assert result[0]["name"] == "2025_unloading.xlsx"
        assert result[0]["size_bytes"] == 2048
        assert result[0]["updated_at"]
