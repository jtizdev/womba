import httpx
import pytest

from src.aggregator.confluence_client import ConfluenceClient


@pytest.mark.asyncio
async def test_search_all_pages_uses_spaces_and_pages(monkeypatch):
    client = ConfluenceClient()

    async def fake_iter_spaces(self, http_client, limit=250):
        yield {"id": "1", "key": "DOC"}
        yield {"id": "2", "key": "ENG"}

    async def fake_iter_pages(self, http_client, space_id, limit=250, expand=None):
        if space_id == "1":
            yield {"id": "p1", "title": "Doc Page", "body": {"storage": {"value": "<p>Body p1</p>"}}}
        if space_id == "2":
            yield {"id": "p2", "title": "Eng Page", "body": {"storage": {"value": "<p>Body p2</p>"}}}

    monkeypatch.setattr(ConfluenceClient, "_iter_spaces_v2", fake_iter_spaces)
    monkeypatch.setattr(ConfluenceClient, "_iter_pages_v2", fake_iter_pages)

    pages = await client.search_all_pages("type=page")

    assert len(pages) == 2
    ids = {page["id"] for page in pages}
    assert ids == {"p1", "p2"}
    assert pages[0]["body"]["storage"]["value"].startswith("<p>Body")


@pytest.mark.asyncio
async def test_fetch_json_retries_rate_limits(monkeypatch):
    client = ConfluenceClient()

    async def fake_sleep(_):
        return None

    monkeypatch.setattr("src.aggregator.confluence_client.asyncio.sleep", fake_sleep)

    class DummyResponse:
        def __init__(self, status_code, json_data=None, headers=None):
            self.status_code = status_code
            self._json = json_data or {}
            self.headers = headers or {}

        def raise_for_status(self):
            if self.status_code >= 400 and self.status_code not in {429, 503}:
                raise httpx.HTTPError("HTTP error")

        def json(self):
            return self._json

    responses = [
        DummyResponse(429, headers={"Retry-After": "0"}),
        DummyResponse(200, json_data={"ok": True})
    ]

    class DummyAsyncClient:
        async def get(self, url, auth=None, params=None):
            return responses.pop(0)

    dummy_client = DummyAsyncClient()

    result = await client._fetch_json(dummy_client, "https://example.com")
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_iter_pages_handles_cursor(monkeypatch):
    client = ConfluenceClient()

    async def fake_fetch_json(self, http_client, url, params=None, max_retries=3):
        if "cursor1" in url:
            return {
                "results": [
                    {"id": "p2", "title": "Second"},
                ],
                "_links": {"next": None}
            }
        return {
            "results": [
                {"id": "p1", "title": "First"},
            ],
            "_links": {"next": "/wiki/api/v2/spaces/1/pages?cursor=cursor1"}
        }

    monkeypatch.setattr(ConfluenceClient, "_fetch_json", fake_fetch_json)

    collected = []
    async with httpx.AsyncClient() as http_client:
        async for page in client._iter_pages_v2(http_client, space_id="1", limit=100):
            collected.append(page["id"])

    assert collected == ["p1", "p2"]
