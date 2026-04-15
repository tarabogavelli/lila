from unittest.mock import patch, MagicMock

import pytest
import httpx

from server import app


@pytest.fixture
def client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


class TestGetToken:
    async def test_returns_jwt(self, client, monkeypatch):
        monkeypatch.setenv("LIVEKIT_API_KEY", "test_key")
        monkeypatch.setenv("LIVEKIT_API_SECRET", "test_secret")
        monkeypatch.setenv("LIVEKIT_URL", "wss://test.livekit.cloud")

        async with client:
            response = await client.get("/token")

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert isinstance(data["token"], str)
        assert len(data["token"]) > 0
        assert data["url"] == "wss://test.livekit.cloud"
        assert "room" in data
        assert data["room"].startswith("lila-")

    async def test_custom_params(self, client, monkeypatch):
        monkeypatch.setenv("LIVEKIT_API_KEY", "test_key")
        monkeypatch.setenv("LIVEKIT_API_SECRET", "test_secret")
        monkeypatch.setenv("LIVEKIT_URL", "wss://test.livekit.cloud")

        async with client:
            response = await client.get("/token?room=custom&participant=alice")

        assert response.status_code == 200
        data = response.json()
        assert "token" in data


class TestGetShelves:
    async def test_no_room_returns_empty(self, client):
        async with client:
            response = await client.get("/shelves")

        assert response.status_code == 200
        assert response.json() == {}

    async def test_empty_room(self, client):
        mock_store = MagicMock()
        mock_store.get_all_shelves.return_value = {}
        with patch("server.get_store", return_value=mock_store):
            async with client:
                response = await client.get("/shelves?room=test-room")

        assert response.status_code == 200
        assert response.json() == {}

    async def test_with_data(self, client):
        shelves_data = {
            "Need a Cry": [
                {"title": "Normal People", "author": "Sally Rooney", "isbn": "123"}
            ]
        }
        mock_store = MagicMock()
        mock_store.get_all_shelves.return_value = shelves_data
        with patch("server.get_store", return_value=mock_store):
            async with client:
                response = await client.get("/shelves?room=test-room")

        assert response.status_code == 200
        data = response.json()
        assert "Need a Cry" in data
        assert data["Need a Cry"][0]["title"] == "Normal People"


class TestCors:
    async def test_cors_headers_present(self, client):
        async with client:
            response = await client.options(
                "/token",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                },
            )

        assert "access-control-allow-origin" in response.headers
