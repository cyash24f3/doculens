from fastapi.testclient import TestClient
from doculens.api import create_app
from doculens.config import Settings


def test_api_end_to_end(tmp_path):
    with TestClient(create_app(settings=Settings(tmp_path, embeddings=False))) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        assert client.get("/").status_code == 200
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/openapi.json").status_code == 200
        raw = b"# API guide\n\nThe API rate limit is 120 requests per minute. Retry HTTP 429 after the specified delay."
        upload = client.post(
            "/api/documents",
            files={"file": ("guide.md", raw)},
            data={"title": "API guide", "category": "Engineering", "version": "1"},
        )
        assert upload.status_code == 201
        doc = upload.json()
        response = client.post(
            "/api/ask", json={"question": "What is the API rate limit?", "mode": "keyword"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["answer"]["statements"]
        assert client.get(f"/api/traces/{body['trace_id']}/download").status_code == 200
        chunk = body["results"][0]["id"]
        assert client.get(f"/api/chunks/{chunk}").json()["document_id"] == doc["id"]
        assert client.get(f"/api/documents/{doc['id']}/download").content == raw
        assert client.get("/api/documents/export").status_code == 200
        assert client.post("/api/ask", json={"question": "  ", "mode": "keyword"}).status_code == 422
        assert client.post("/api/ask", json={"question": "API limit", "mode": "semantic"}).status_code == 422
        replaced = client.post(
            f"/api/documents/{doc['id']}/replace",
            files={"file": ("guide.md", b"New API rate limit is 60 requests per minute.")},
            data={"version": "2"},
        )
        assert replaced.status_code == 201
        assert not client.get(f"/api/documents/{doc['id']}").json()["active"]
        assert client.delete(f"/api/documents/{doc['id']}").status_code == 200
        assert client.get(f"/api/chunks/{chunk}").status_code == 404
        assert client.get("/api/traces").json() == []
        assert client.delete("/api/documents/missing").status_code == 404


def test_origin_and_bad_upload(tmp_path):
    with TestClient(create_app(settings=Settings(tmp_path, embeddings=False))) as client:
        assert client.post("/api/demo", headers={"Origin": "https://untrusted.example"}).status_code == 403
        assert (
            client.post(
                "/api/documents", files={"file": ("bad.exe", b"hello")}, data={"title": "bad"}
            ).status_code
            == 422
        )
        assert client.get("/api/documents/unknown").status_code == 404


def test_evaluation_requires_original_corpus(tmp_path):
    with TestClient(create_app(settings=Settings(tmp_path, embeddings=False))) as client:
        assert client.post("/api/evaluations").status_code == 202
        result = client.get("/api/evaluations").json()[0]
        assert result["status"] == "failed"
        assert "original" in result["message"]


def test_metadata_csv_formula_protection(tmp_path):
    with TestClient(create_app(settings=Settings(tmp_path, embeddings=False))) as client:
        response = client.post(
            "/api/documents",
            files={"file": ("sample.txt", b"A simple source document.")},
            data={"title": '=HYPERLINK("bad")'},
        )
        assert response.status_code == 201
        assert "'=HYPERLINK" in client.get("/api/documents/export").text
