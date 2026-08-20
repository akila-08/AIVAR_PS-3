from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app


def test_propose_requires_gemini_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")

    response = TestClient(app).post(
        "/agent/propose", json={"scenario": "Delete 500 rows"}
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "GEMINI_API_KEY is not configured"


def test_propose_returns_validated_action(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    class FakeModels:
        def generate_content(self, **kwargs):
            assert "Delete 500 rows" in kwargs["contents"]
            return SimpleNamespace(
                text='{"tool":"db_delete","params":{"record_count":500}}'
            )

    class FakeGemini:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.models = FakeModels()

    monkeypatch.setattr("app.llm.genai.Client", FakeGemini)
    response = TestClient(app).post(
        "/agent/propose", json={"scenario": "Delete 500 rows"}
    )

    assert response.status_code == 200
    assert response.json() == {"tool": "db_delete", "params": {"record_count": 500}}