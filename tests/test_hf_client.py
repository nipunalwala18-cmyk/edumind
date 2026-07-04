"""
tests/test_hf_client.py
------------------------
Unit tests for rag/hf_client.py.

All tests are offline — no HuggingFace API connection required.
httpx calls are mocked via unittest.mock.
Run: pytest tests/test_hf_client.py -v
"""

from __future__ import annotations

import json
import sys
import os
import time
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx

from rag.hf_client import (
    HFConfig,
    HFClient,
    HFConnectionError,
    HFTimeoutError,
    HFResponseError,
    HFModelNotFoundError,
    get_hf_client,
    reset_hf_client,
)


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset module-level singletons before every test."""
    reset_hf_client()
    yield
    reset_hf_client()


def _hf_response_body(
    content: str = "The deadline is the 15th.",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    model: str = "Qwen/Qwen2.5-32B-Instruct",
) -> dict:
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1672531199,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _stream_lines(chunks: list[str]) -> list[str]:
    """Builds SSE lines matching OpenAI/HF streaming format."""
    lines = []
    for chunk in chunks:
        lines.append(
            "data: "
            + json.dumps(
                {
                    "choices": [
                        {
                            "delta": {"content": chunk},
                            "finish_reason": None,
                            "index": 0,
                        }
                    ]
                }
            )
        )
    lines.append("data: [DONE]")
    return lines


# ===========================================================================
# HFConfig
# ===========================================================================

class TestHFConfig:
    def test_defaults(self):
        cfg = HFConfig(token="test-token")
        assert cfg.api_base == "https://api-inference.huggingface.co/models"
        assert cfg.model == "Qwen/Qwen2.5-32B-Instruct"
        assert cfg.token == "test-token"
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 1024
        assert cfg.top_p == 0.9
        assert cfg.timeout == 300.0
        assert cfg.max_retries == 3
        assert cfg.retry_delay == 2.0

    def test_chat_url(self):
        cfg = HFConfig(model="meta-llama/Llama-3-8b")
        assert cfg.chat_url == "https://api-inference.huggingface.co/models/meta-llama/Llama-3-8b/v1/chat/completions"

    def test_auth_headers(self):
        cfg = HFConfig(token="hf_abc123")
        headers = cfg.auth_headers
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer hf_abc123"

    def test_auth_headers_no_token(self):
        cfg = HFConfig(token="")
        headers = cfg.auth_headers
        assert headers["Content-Type"] == "application/json"
        assert "Authorization" not in headers


# ===========================================================================
# HFClient._build_payload
# ===========================================================================

class TestHFClientPayload:
    def test_build_payload(self):
        client = HFClient(HFConfig(model="foo", token="bar"))
        payload = client._build_payload(
            [{"role": "user", "content": "hi"}],
            stream=True,
            temperature=0.5,
            max_tokens=100,
            top_p=0.8,
        )
        assert payload["model"] == "foo"
        assert payload["messages"] == [{"role": "user", "content": "hi"}]
        assert payload["stream"] is True
        assert payload["temperature"] == 0.5
        assert payload["max_tokens"] == 100
        assert payload["top_p"] == 0.8


# ===========================================================================
# HFClient._check_status
# ===========================================================================

class TestHFClientCheckStatus:
    def test_200_ok(self):
        client = HFClient()
        client._check_status(200)  # should not raise

    def test_401_unauthorized(self):
        client = HFClient()
        with pytest.raises(HFResponseError) as excinfo:
            client._check_status(401)
        assert "401 Unauthorized" in str(excinfo.value)

    def test_404_model_not_found(self):
        client = HFClient()
        with pytest.raises(HFModelNotFoundError) as excinfo:
            client._check_status(404)
        assert "not found" in str(excinfo.value)

    def test_429_rate_limit(self):
        client = HFClient()
        with pytest.raises(HFTimeoutError) as excinfo:
            client._check_status(429)
        assert "rate limit" in str(excinfo.value)

    def test_503_loading(self):
        client = HFClient()
        with pytest.raises(HFTimeoutError) as excinfo:
            client._check_status(503)
        assert "loading" in str(excinfo.value)

    def test_other_error(self):
        client = HFClient()
        with pytest.raises(HFResponseError) as excinfo:
            client._check_status(500)
        assert "HTTP 500" in str(excinfo.value)


# ===========================================================================
# HFClient.chat (mocked httpx)
# ===========================================================================

def _mock_httpx_post(body_dict: dict, status_code: int = 200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = body_dict
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_resp
    return mock_client


class TestHFClientChat:
    def test_successful_chat(self):
        body = _hf_response_body("HF Answer", 20, 15)
        client = HFClient(HFConfig(max_retries=0))

        with patch("httpx.Client", return_value=_mock_httpx_post(body)):
            result = client.chat([{"role": "user", "content": "hello"}])

        assert result["answer"] == "HF Answer"
        assert result["prompt_tokens"] == 20
        assert result["completion_tokens"] == 15
        assert result["model_name"] == "Qwen/Qwen2.5-32B-Instruct"
        assert "latency_ms" in result

    def test_connection_error(self):
        client = HFClient(HFConfig(max_retries=0))
        mock_c = MagicMock()
        mock_c.__enter__ = lambda s: s
        mock_c.__exit__ = MagicMock(return_value=False)
        mock_c.post.side_effect = httpx.ConnectError("refused")

        with patch("httpx.Client", return_value=mock_c):
            with pytest.raises(HFConnectionError):
                client.chat([])

    def test_timeout_error(self):
        client = HFClient(HFConfig(max_retries=0))
        mock_c = MagicMock()
        mock_c.__enter__ = lambda s: s
        mock_c.__exit__ = MagicMock(return_value=False)
        mock_c.post.side_effect = httpx.ReadTimeout("slow")

        with patch("httpx.Client", return_value=mock_c):
            with pytest.raises(HFTimeoutError):
                client.chat([])


# ===========================================================================
# HFClient.chat_stream (mocked httpx)
# ===========================================================================

class TestHFClientStream:
    def _mock_stream_client(self, lines: list[str]):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = lambda s: s
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.status_code = 200
        mock_ctx.iter_lines.return_value = iter(lines)

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.stream.return_value = mock_ctx
        return mock_client

    def test_yields_text_chunks(self):
        lines = _stream_lines(["Hello", " from", " HuggingFace"])
        client = HFClient()

        with patch("httpx.Client", return_value=self._mock_stream_client(lines)):
            chunks = list(client.chat_stream([{"role": "user", "content": "hi"}]))

        assert chunks == ["Hello", " from", " HuggingFace"]


# ===========================================================================
# Singleton — HFClient
# ===========================================================================

class TestHFClientSingleton:
    def test_same_instance_returned(self):
        a = get_hf_client()
        b = get_hf_client()
        assert a is b

    def test_reset_clears_instance(self):
        a = get_hf_client()
        reset_hf_client()
        b = get_hf_client()
        assert a is not b
