"""
tests/test_rag_engine.py
-------------------------
Unit tests for rag/ollama_client.py and rag/rag_engine.py.

All tests are offline — no Ollama process required.
httpx calls are mocked via unittest.mock.
Run: pytest tests/test_rag_engine.py -v
"""

from __future__ import annotations

import json
import sys
import os
import time
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx

from rag.ollama_client import (
    OllamaConfig,
    OllamaClient,
    OllamaConnectionError,
    OllamaTimeoutError,
    OllamaModelNotFoundError,
    OllamaResponseError,
    _parse_chat_response,
    _parse_stream_line,
    _with_retry,
    get_ollama_client,
    reset_ollama_client,
)
from rag.rag_engine import (
    RAGEngine,
    RAGResponse,
    get_rag_engine,
    reset_rag_engine,
)
from rag.prompt_schema import (
    BuiltPrompt,
    PromptTemplate,
    PromptConfig,
)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset module-level singletons before every test."""
    reset_ollama_client()
    reset_rag_engine()
    yield
    reset_ollama_client()
    reset_rag_engine()


def _ollama_response_body(
    content: str = "The deadline is the 15th.",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    done_reason: str = "stop",
    eval_duration_ns: int = 2_000_000_000,
    model: str = "qwen2.5:7b",
) -> dict:
    return {
        "model":             model,
        "created_at":        "2025-01-01T00:00:00Z",
        "message":           {"role": "assistant", "content": content},
        "done":              True,
        "done_reason":       done_reason,
        "prompt_eval_count": prompt_tokens,
        "eval_count":        completion_tokens,
        "eval_duration":     eval_duration_ns,
        "total_duration":    eval_duration_ns + 500_000_000,
    }


def _stream_lines(
    chunks: list[str],
    model: str = "qwen2.5:7b",
    prompt_tokens: int = 100,
    completion_tokens: int = 30,
) -> list[str]:
    """Builds NDJSON lines matching Ollama streaming format."""
    lines = []
    for chunk in chunks:
        lines.append(json.dumps({
            "model": model, "done": False,
            "message": {"role": "assistant", "content": chunk},
        }))
    lines.append(json.dumps({
        "model": model, "done": True, "done_reason": "stop",
        "prompt_eval_count": prompt_tokens, "eval_count": completion_tokens,
        "eval_duration": 1_500_000_000,
    }))
    return lines


def _make_built_prompt(
    question: str = "What is the fee?",
    chunks_included: int = 3,
    has_conflicts: bool = False,
    template: PromptTemplate = PromptTemplate.DEFAULT,
) -> BuiltPrompt:
    """Minimal BuiltPrompt without running the full PromptBuilder stack."""
    return BuiltPrompt(
        user_question   = question,
        system_prompt   = "You are a VIT assistant.",
        context_block   = "[SOURCE 1] Fee SOP\n---\nFee is 15th each month.",
        user_message    = f"[SOURCE 1] ...\nQUESTION: {question}",
        messages        = [
            {"role": "system",  "content": "You are a VIT assistant."},
            {"role": "user",    "content": f"QUESTION: {question}"},
        ],
        chunks_included = chunks_included,
        chunks_dropped  = 0,
        context_chars   = 100,
        template_used   = template,
        has_conflicts   = has_conflicts,
        source_citations = ["Fee SOP (v2.0) — Section — chunk 1 of 10"],
    )


# ===========================================================================
# OllamaConfig
# ===========================================================================

class TestOllamaConfig:
    def test_defaults(self):
        cfg = OllamaConfig()
        assert cfg.base_url      == "http://localhost:11434"
        assert cfg.model         == "qwen2.5:7b"
        assert cfg.temperature   == 0.7
        assert cfg.max_tokens    == 1024
        assert cfg.top_p         == 0.9
        assert cfg.repeat_penalty == 1.1
        assert cfg.timeout       == 300.0
        assert cfg.max_retries   == 3
        assert cfg.retry_delay   == 1.0

    def test_custom_values(self):
        cfg = OllamaConfig(model="llama3:8b", temperature=0.1, max_tokens=512)
        assert cfg.model       == "llama3:8b"
        assert cfg.temperature == 0.1
        assert cfg.max_tokens  == 512

    def test_to_options_default(self):
        cfg  = OllamaConfig()
        opts = cfg.to_options()
        assert opts["temperature"]    == 0.7
        assert opts["num_predict"]    == 1024
        assert opts["top_p"]          == 0.9
        assert opts["repeat_penalty"] == 1.1

    def test_to_options_override_temperature(self):
        cfg  = OllamaConfig()
        opts = cfg.to_options({"temperature": 0.1})
        assert opts["temperature"] == 0.1

    def test_to_options_max_tokens_renamed(self):
        cfg  = OllamaConfig()
        opts = cfg.to_options({"max_tokens": 256})
        assert "num_predict" in opts
        assert opts["num_predict"] == 256
        assert "max_tokens" not in opts

    def test_temperature_bounds(self):
        with pytest.raises(Exception):
            OllamaConfig(temperature=3.0)
        with pytest.raises(Exception):
            OllamaConfig(temperature=-0.1)


# ===========================================================================
# _parse_chat_response (pure function)
# ===========================================================================

class TestParseChatResponse:
    def test_basic_parse(self):
        body   = _ollama_response_body("Answer here.", 80, 40)
        result = _parse_chat_response(body)
        assert result["answer"]            == "Answer here."
        assert result["prompt_tokens"]     == 80
        assert result["completion_tokens"] == 40
        assert result["finish_reason"]     == "stop"
        assert result["model_name"]        == "qwen2.5:7b"

    def test_generation_time_conversion(self):
        # 2 billion nanoseconds == 2000 ms
        body   = _ollama_response_body(eval_duration_ns=2_000_000_000)
        result = _parse_chat_response(body)
        assert abs(result["generation_time_ms"] - 2000.0) < 1

    def test_missing_eval_duration_defaults_zero(self):
        body   = _ollama_response_body()
        del body["eval_duration"]
        result = _parse_chat_response(body)
        assert result["generation_time_ms"] == 0.0

    def test_missing_message_raises(self):
        with pytest.raises(OllamaResponseError):
            _parse_chat_response({"done": True})

    def test_finish_reason_length(self):
        body   = _ollama_response_body(done_reason="length")
        result = _parse_chat_response(body)
        assert result["finish_reason"] == "length"

    def test_missing_prompt_eval_defaults_zero(self):
        body   = _ollama_response_body()
        del body["prompt_eval_count"]
        result = _parse_chat_response(body)
        assert result["prompt_tokens"] == 0


# ===========================================================================
# _parse_stream_line (pure function)
# ===========================================================================

class TestParseStreamLine:
    def test_empty_line_returns_none(self):
        chunk, done, stats = _parse_stream_line("")
        assert chunk is None
        assert done is False
        assert stats is None

    def test_content_line_returns_text(self):
        line  = json.dumps({"done": False, "message": {"role": "assistant", "content": "Hello"}})
        chunk, done, stats = _parse_stream_line(line)
        assert chunk == "Hello"
        assert done is False
        assert stats is None

    def test_empty_content_returns_none_chunk(self):
        line  = json.dumps({"done": False, "message": {"role": "assistant", "content": ""}})
        chunk, done, stats = _parse_stream_line(line)
        assert chunk is None

    def test_done_line_returns_stats(self):
        line = json.dumps({
            "done": True, "done_reason": "stop", "model": "qwen2.5:7b",
            "prompt_eval_count": 100, "eval_count": 50,
            "eval_duration": 1_000_000_000,
        })
        chunk, done, stats = _parse_stream_line(line)
        assert chunk is None
        assert done is True
        assert stats["prompt_tokens"]     == 100
        assert stats["completion_tokens"] == 50
        assert stats["finish_reason"]     == "stop"
        assert abs(stats["generation_time_ms"] - 1000.0) < 1

    def test_invalid_json_returns_none(self):
        chunk, done, stats = _parse_stream_line("not json{{{")
        assert chunk is None
        assert done is False

    def test_whitespace_line_returns_none(self):
        chunk, done, stats = _parse_stream_line("   \n  ")
        assert chunk is None


# ===========================================================================
# _with_retry
# ===========================================================================

class TestWithRetry:
    def test_succeeds_on_first_try(self):
        call_count = 0
        def fn():
            nonlocal call_count
            call_count += 1
            return "ok"
        result = _with_retry(fn, max_retries=3, base_delay=0.001)
        assert result == "ok"
        assert call_count == 1

    def test_retries_on_connection_error(self):
        call_count = 0
        def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OllamaConnectionError("down")
            return "ok"
        result = _with_retry(fn, max_retries=3, base_delay=0.001)
        assert result == "ok"
        assert call_count == 3

    def test_raises_after_max_retries(self):
        def fn():
            raise OllamaConnectionError("always down")
        with pytest.raises(OllamaConnectionError):
            _with_retry(fn, max_retries=2, base_delay=0.001)

    def test_retries_on_timeout(self):
        call_count = 0
        def fn():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OllamaTimeoutError("slow")
            return "ok"
        result = _with_retry(fn, max_retries=2, base_delay=0.001)
        assert result == "ok"

    def test_does_not_retry_model_not_found(self):
        call_count = 0
        def fn():
            nonlocal call_count
            call_count += 1
            raise OllamaModelNotFoundError("no model")
        with pytest.raises(OllamaModelNotFoundError):
            _with_retry(fn, max_retries=3, base_delay=0.001)
        assert call_count == 1  # no retry


# ===========================================================================
# OllamaClient._build_payload
# ===========================================================================

class TestBuildPayload:
    def test_includes_model(self):
        client  = OllamaClient(OllamaConfig(model="qwen2.5:7b"))
        payload = client._build_payload([{"role": "user", "content": "hi"}], stream=False, overrides={})
        assert payload["model"] == "qwen2.5:7b"

    def test_stream_flag_propagated(self):
        client  = OllamaClient()
        payload = client._build_payload([], stream=True, overrides={})
        assert payload["stream"] is True

    def test_messages_propagated(self):
        client   = OllamaClient()
        messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}]
        payload  = client._build_payload(messages, stream=False, overrides={})
        assert payload["messages"] == messages

    def test_options_present(self):
        client  = OllamaClient()
        payload = client._build_payload([], stream=False, overrides={})
        assert "options" in payload
        assert "temperature" in payload["options"]
        assert "num_predict" in payload["options"]

    def test_override_applied_to_options(self):
        client  = OllamaClient()
        payload = client._build_payload([], stream=False, overrides={"temperature": 0.2})
        assert payload["options"]["temperature"] == 0.2


# ===========================================================================
# OllamaClient._check_status
# ===========================================================================

class TestCheckStatus:
    def test_200_passes(self):
        OllamaClient._check_status(200, "http://localhost/api/chat")  # no raise

    def test_404_raises_model_not_found(self):
        with pytest.raises(OllamaModelNotFoundError):
            OllamaClient._check_status(404, "http://localhost/api/chat")

    def test_500_raises_response_error(self):
        with pytest.raises(OllamaResponseError):
            OllamaClient._check_status(500, "http://localhost/api/chat")

    def test_503_raises_response_error(self):
        with pytest.raises(OllamaResponseError):
            OllamaClient._check_status(503, "http://localhost/api/chat")


# ===========================================================================
# OllamaClient.chat (mocked httpx)
# ===========================================================================

def _mock_httpx_post(body_dict: dict):
    """Returns a mock httpx.Response for non-streaming POST."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = body_dict
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__  = MagicMock(return_value=False)
    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__  = MagicMock(return_value=False)
    mock_client.post.return_value = mock_resp
    return mock_client


class TestOllamaClientChat:
    def test_successful_response(self):
        body   = _ollama_response_body("The answer.", 80, 40)
        client = OllamaClient(OllamaConfig(max_retries=0))

        with patch("httpx.Client", return_value=_mock_httpx_post(body)):
            result = client.chat([{"role": "user", "content": "q?"}])

        assert result["answer"]           == "The answer."
        assert result["prompt_tokens"]    == 80
        assert result["completion_tokens"]== 40
        assert "latency_ms" in result
        assert result["latency_ms"] >= 0

    def test_latency_is_float(self):
        body   = _ollama_response_body()
        client = OllamaClient(OllamaConfig(max_retries=0))

        with patch("httpx.Client", return_value=_mock_httpx_post(body)):
            result = client.chat([{"role": "user", "content": "q?"}])

        assert isinstance(result["latency_ms"], float)

    def test_per_call_temperature_override(self):
        body   = _ollama_response_body()
        client = OllamaClient(OllamaConfig(max_retries=0))
        captured_payload = {}

        def capture_post(url, json=None, **kwargs):
            captured_payload.update(json or {})
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = body
            return mock_resp

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__  = MagicMock(return_value=False)
        mock_client.post.side_effect = capture_post

        with patch("httpx.Client", return_value=mock_client):
            client.chat([{"role": "user", "content": "q?"}], temperature=0.1)

        assert captured_payload["options"]["temperature"] == 0.1

    def test_connection_error_raises(self):
        client = OllamaClient(OllamaConfig(max_retries=0))
        mock_c = MagicMock()
        mock_c.__enter__ = lambda s: s
        mock_c.__exit__  = MagicMock(return_value=False)
        mock_c.post.side_effect = httpx.ConnectError("refused")

        with patch("httpx.Client", return_value=mock_c):
            with pytest.raises(OllamaConnectionError):
                client.chat([])

    def test_timeout_raises(self):
        client = OllamaClient(OllamaConfig(max_retries=0))
        mock_c = MagicMock()
        mock_c.__enter__ = lambda s: s
        mock_c.__exit__  = MagicMock(return_value=False)
        mock_c.post.side_effect = httpx.ReadTimeout("timeout")

        with patch("httpx.Client", return_value=mock_c):
            with pytest.raises(OllamaTimeoutError):
                client.chat([])

    def test_non_json_response_raises(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("not json")
        mock_resp.text = "plain text response"
        mock_c = MagicMock()
        mock_c.__enter__ = lambda s: s
        mock_c.__exit__  = MagicMock(return_value=False)
        mock_c.post.return_value = mock_resp

        client = OllamaClient(OllamaConfig(max_retries=0))
        with patch("httpx.Client", return_value=mock_c):
            with pytest.raises(OllamaResponseError):
                client.chat([])

    def test_retry_on_connection_error(self):
        body       = _ollama_response_body("ok")
        call_count = 0

        def flaky_post(url, json=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("down")
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = body
            return mock_resp

        mock_c = MagicMock()
        mock_c.__enter__ = lambda s: s
        mock_c.__exit__  = MagicMock(return_value=False)
        mock_c.post.side_effect = flaky_post

        client = OllamaClient(OllamaConfig(max_retries=3, retry_delay=0.001))
        with patch("httpx.Client", return_value=mock_c):
            result = client.chat([])

        assert result["answer"] == "ok"
        assert call_count == 3


# ===========================================================================
# OllamaClient.chat_stream (mocked httpx)
# ===========================================================================

class TestOllamaClientStream:
    def _mock_stream_client(self, lines: list[str]):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(lines)
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__  = MagicMock(return_value=False)
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = lambda s: s
        mock_ctx.__exit__  = MagicMock(return_value=False)
        mock_ctx.status_code = 200
        mock_ctx.iter_lines.return_value = iter(lines)

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__  = MagicMock(return_value=False)
        mock_client.stream.return_value = mock_ctx
        return mock_client

    def test_yields_text_chunks(self):
        lines  = _stream_lines(["Hello", " world", "!"])
        client = OllamaClient(OllamaConfig())

        with patch("httpx.Client", return_value=self._mock_stream_client(lines)):
            chunks = list(client.chat_stream([{"role": "user", "content": "hi"}]))

        assert "Hello" in chunks
        assert " world" in chunks
        assert "!" in chunks

    def test_does_not_yield_empty_chunks(self):
        lines  = _stream_lines(["", "real content", ""])
        client = OllamaClient()

        with patch("httpx.Client", return_value=self._mock_stream_client(lines)):
            chunks = list(client.chat_stream([]))

        assert "" not in chunks
        assert "real content" in chunks

    def test_stream_connection_error(self):
        mock_c = MagicMock()
        mock_c.__enter__ = lambda s: s
        mock_c.__exit__  = MagicMock(return_value=False)
        mock_c.stream.side_effect = httpx.ConnectError("refused")

        client = OllamaClient()
        with patch("httpx.Client", return_value=mock_c):
            with pytest.raises(OllamaConnectionError):
                list(client.chat_stream([]))

    def test_stream_timeout_error(self):
        mock_c = MagicMock()
        mock_c.__enter__ = lambda s: s
        mock_c.__exit__  = MagicMock(return_value=False)
        mock_c.stream.side_effect = httpx.ReadTimeout("slow")

        client = OllamaClient()
        with patch("httpx.Client", return_value=mock_c):
            with pytest.raises(OllamaTimeoutError):
                list(client.chat_stream([]))


# ===========================================================================
# OllamaClient.health_check
# ===========================================================================

class TestHealthCheck:
    def test_returns_true_on_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_c = MagicMock()
        mock_c.__enter__ = lambda s: s
        mock_c.__exit__  = MagicMock(return_value=False)
        mock_c.get.return_value = mock_resp

        client = OllamaClient()
        with patch("httpx.Client", return_value=mock_c):
            assert client.health_check() is True

    def test_returns_false_on_exception(self):
        mock_c = MagicMock()
        mock_c.__enter__ = lambda s: s
        mock_c.__exit__  = MagicMock(return_value=False)
        mock_c.get.side_effect = httpx.ConnectError("refused")

        client = OllamaClient()
        with patch("httpx.Client", return_value=mock_c):
            assert client.health_check() is False


# ===========================================================================
# Singleton — OllamaClient
# ===========================================================================

class TestOllamaClientSingleton:
    def test_same_instance_returned(self):
        a = get_ollama_client()
        b = get_ollama_client()
        assert a is b

    def test_reset_clears_instance(self):
        a = get_ollama_client()
        reset_ollama_client()
        b = get_ollama_client()
        assert a is not b

    def test_config_applied_on_first_call(self):
        cfg    = OllamaConfig(model="llama3:8b")
        client = get_ollama_client(config=cfg)
        assert client.model == "llama3:8b"


# ===========================================================================
# RAGResponse
# ===========================================================================

class TestRAGResponse:
    def _make(self, **kwargs) -> RAGResponse:
        defaults = dict(
            answer="The fee is due on the 15th.",
            model_name="qwen2.5:7b",
            finish_reason="stop",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=350.0,
            generation_time_ms=2000.0,
            chunks_used=3,
        )
        defaults.update(kwargs)
        return RAGResponse(**defaults)

    def test_required_fields(self):
        r = self._make()
        assert r.answer      == "The fee is due on the 15th."
        assert r.model_name  == "qwen2.5:7b"
        assert r.total_tokens == 150

    def test_tokens_per_second(self):
        r = self._make(completion_tokens=50, generation_time_ms=1000.0)
        assert r.tokens_per_second == 50.0

    def test_tokens_per_second_zero_when_no_time(self):
        r = self._make(generation_time_ms=0.0)
        assert r.tokens_per_second == 0.0

    def test_summary_contains_model(self):
        r = self._make()
        assert "qwen2.5:7b" in r.summary()

    def test_summary_contains_latency(self):
        r = self._make(latency_ms=500.0)
        assert "500" in r.summary()

    def test_has_conflicts_default_false(self):
        r = self._make()
        assert r.has_conflicts is False

    def test_template_used_default(self):
        r = self._make()
        assert r.template_used == "default"


# ===========================================================================
# RAGEngine.generate (mocked OllamaClient)
# ===========================================================================

def _mock_client_chat(raw: dict) -> OllamaClient:
    client = MagicMock(spec=OllamaClient)
    client.chat.return_value = raw
    client.model = "qwen2.5:7b"
    return client


class TestRAGEngineGenerate:
    def test_returns_rag_response(self):
        raw    = _parse_chat_response(_ollama_response_body("Answer text."))
        raw["latency_ms"] = 300.0
        engine = RAGEngine(client=_mock_client_chat(raw))
        prompt = _make_built_prompt()
        result = engine.generate(prompt)
        assert isinstance(result, RAGResponse)

    def test_answer_propagated(self):
        raw    = _parse_chat_response(_ollama_response_body("The fee is 15th."))
        raw["latency_ms"] = 100.0
        engine = RAGEngine(client=_mock_client_chat(raw))
        result = engine.generate(_make_built_prompt())
        assert result.answer == "The fee is 15th."

    def test_token_counts(self):
        raw    = _parse_chat_response(_ollama_response_body(prompt_tokens=80, completion_tokens=40))
        raw["latency_ms"] = 100.0
        engine = RAGEngine(client=_mock_client_chat(raw))
        result = engine.generate(_make_built_prompt())
        assert result.prompt_tokens     == 80
        assert result.completion_tokens == 40
        assert result.total_tokens      == 120

    def test_latency_propagated(self):
        raw    = _parse_chat_response(_ollama_response_body())
        raw["latency_ms"] = 420.5
        engine = RAGEngine(client=_mock_client_chat(raw))
        result = engine.generate(_make_built_prompt())
        assert result.latency_ms == 420.5

    def test_generation_time_propagated(self):
        raw    = _parse_chat_response(_ollama_response_body(eval_duration_ns=3_000_000_000))
        raw["latency_ms"] = 100.0
        engine = RAGEngine(client=_mock_client_chat(raw))
        result = engine.generate(_make_built_prompt())
        assert abs(result.generation_time_ms - 3000.0) < 1

    def test_chunks_used_from_prompt(self):
        raw    = _parse_chat_response(_ollama_response_body())
        raw["latency_ms"] = 100.0
        engine = RAGEngine(client=_mock_client_chat(raw))
        prompt = _make_built_prompt(chunks_included=5)
        result = engine.generate(prompt)
        assert result.chunks_used == 5

    def test_has_conflicts_from_prompt(self):
        raw    = _parse_chat_response(_ollama_response_body())
        raw["latency_ms"] = 100.0
        engine = RAGEngine(client=_mock_client_chat(raw))
        prompt = _make_built_prompt(has_conflicts=True)
        result = engine.generate(prompt)
        assert result.has_conflicts is True

    def test_finish_reason_length(self):
        raw    = _parse_chat_response(_ollama_response_body(done_reason="length"))
        raw["latency_ms"] = 100.0
        engine = RAGEngine(client=_mock_client_chat(raw))
        result = engine.generate(_make_built_prompt())
        assert result.finish_reason == "length"

    def test_per_call_temperature_passed_to_client(self):
        mock_client       = MagicMock(spec=OllamaClient)
        raw               = _parse_chat_response(_ollama_response_body())
        raw["latency_ms"] = 100.0
        mock_client.chat.return_value = raw
        mock_client.model = "qwen2.5:7b"

        engine = RAGEngine(client=mock_client)
        engine.generate(_make_built_prompt(), temperature=0.1)

        _, kwargs = mock_client.chat.call_args
        assert kwargs["temperature"] == 0.1

    def test_ollama_error_propagated(self):
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.chat.side_effect = OllamaConnectionError("down")
        engine = RAGEngine(client=mock_client)

        with pytest.raises(OllamaConnectionError):
            engine.generate(_make_built_prompt())


# ===========================================================================
# RAGEngine.generate_stream (mocked OllamaClient)
# ===========================================================================

class TestRAGEngineStream:
    def test_yields_chunks(self):
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.chat_stream.return_value = iter(["Hello", " world", "!"])

        engine = RAGEngine(client=mock_client)
        chunks = list(engine.generate_stream(_make_built_prompt()))
        assert chunks == ["Hello", " world", "!"]

    def test_empty_stream(self):
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.chat_stream.return_value = iter([])

        engine  = RAGEngine(client=mock_client)
        chunks  = list(engine.generate_stream(_make_built_prompt()))
        assert chunks == []

    def test_temperature_override_passed(self):
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.chat_stream.return_value = iter(["ok"])

        engine = RAGEngine(client=mock_client)
        list(engine.generate_stream(_make_built_prompt(), temperature=0.05))

        _, kwargs = mock_client.chat_stream.call_args
        assert kwargs["temperature"] == 0.05


# ===========================================================================
# Singleton — RAGEngine
# ===========================================================================

class TestRAGEngineSingleton:
    def test_same_instance_returned(self):
        a = get_rag_engine()
        b = get_rag_engine()
        assert a is b

    def test_reset_clears_instance(self):
        a = get_rag_engine()
        reset_rag_engine()
        b = get_rag_engine()
        assert a is not b

    def test_custom_client_injected(self):
        mock_client = MagicMock(spec=OllamaClient)
        engine      = get_rag_engine(client=mock_client)
        assert engine._client is mock_client

    def test_backend_selection_ollama(self):
        with patch.dict(os.environ, {"LLM_BACKEND": "ollama"}):
            reset_rag_engine()
            engine = get_rag_engine()
            from rag.ollama_client import OllamaClient
            assert isinstance(engine._client, OllamaClient)

    def test_backend_selection_hf(self):
        with patch.dict(os.environ, {"LLM_BACKEND": "hf"}):
            reset_rag_engine()
            engine = get_rag_engine()
            from rag.hf_client import HFClient
            assert isinstance(engine._client, HFClient)
