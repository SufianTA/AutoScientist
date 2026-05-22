from __future__ import annotations

import io
from urllib.error import HTTPError, URLError

from app.services import llm_provider


class _Response:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def test_post_json_retries_transient_http_error(monkeypatch) -> None:
    calls = {"count": 0}
    sleeps: list[float] = []

    def fake_urlopen(_request, timeout: int):
        assert timeout == 90
        calls["count"] += 1
        if calls["count"] == 1:
            raise HTTPError(
                url="https://example.invalid",
                code=529,
                msg="overloaded",
                hdrs=None,
                fp=io.BytesIO(b'{"error":"overloaded"}'),
            )
        return _Response(b'{"ok": true}')

    monkeypatch.setattr(llm_provider, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm_provider.time, "sleep", sleeps.append)

    assert llm_provider._post_json("https://example.invalid", {}, {}, max_attempts=2) == {"ok": True}
    assert calls["count"] == 2
    assert sleeps == [2.0]


def test_post_json_retries_network_error(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_urlopen(_request, timeout: int):
        assert timeout == 90
        calls["count"] += 1
        if calls["count"] == 1:
            raise URLError("temporary DNS failure")
        return _Response(b'{"ok": true}')

    monkeypatch.setattr(llm_provider, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm_provider.time, "sleep", lambda _seconds: None)

    assert llm_provider._post_json("https://example.invalid", {}, {}, max_attempts=2) == {"ok": True}
    assert calls["count"] == 2
