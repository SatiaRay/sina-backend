import os
import io
import shutil
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)
UPLOAD_DIR = os.path.join(os.getcwd(), "uploaded_files")


@pytest.fixture(autouse=True)
def cleanup_upload_dir():
    # Ensure upload dir exists before test
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    yield
    # Remove all files after test
    shutil.rmtree(UPLOAD_DIR, ignore_errors=True)


def test_upload_single_file():
    file_content = b"hello world"
    files = {"files": ("test.txt", io.BytesIO(file_content), "text/plain")}
    response = client.post("/files/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "files" in data
    assert len(data["files"]) == 1
    uploaded = data["files"][0]
    assert uploaded["filename"] == "test.txt"
    assert uploaded["url"].startswith("/files/")
    # Check file physically exists
    assert os.path.exists(uploaded["storage_path"])
    with open(uploaded["storage_path"], "rb") as f:
        assert f.read() == file_content


def test_upload_multiple_files():
    files = [
        ("files", ("a.txt", io.BytesIO(b"A"), "text/plain")),
        ("files", ("b.txt", io.BytesIO(b"B"), "text/plain")),
    ]
    response = client.post("/files/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "files" in data
    assert len(data["files"]) == 2
    names = {f["filename"] for f in data["files"]}
    assert names == {"a.txt", "b.txt"}
    for uploaded in data["files"]:
        assert os.path.exists(uploaded["storage_path"])


def test_get_uploaded_file():
    # Upload a file first
    file_content = b"download me"
    files = {"files": ("download.txt", io.BytesIO(file_content), "text/plain")}
    upload_resp = client.post("/files/upload", files=files)
    assert upload_resp.status_code == 200
    file_url = upload_resp.json()["files"][0]["url"]
    filename = file_url.split("/")[-1]
    # Download the file
    resp = client.get(f"/files/{filename}")
    assert resp.status_code == 200
    assert resp.content == file_content
    assert resp.headers["content-type"].startswith(
        "application/octet-stream"
    ) or resp.headers["content-type"].startswith("text/plain")


def test_get_file_not_found():
    resp = client.get("/files/nonexistentfile.txt")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "File not found"
