"""
rag/hf_client.py
-----------------
HuggingFace Inference API client — drop-in replacement for OllamaClient.

Uses HuggingFace's OpenAI-compatible serverless inference endpoint:
    POST https://api-inference.huggingface.co/models/<model>/v1/chat/completions

Supports:
  - Qwen/Qwen2.5-32B-Instruct  (ZeroGPU / serverless free tier)
  - Any HF model with an inference endpoint

Set environment variables in .env:
    LLM_BACKEND=hf
    HF_TOKEN=hf_...
    HF_MODEL=Qwen/Qwen2.5-32B-Instruct
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Iterator, Optional

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions  (mirrors OllamaClient's exception names so callers don't care
# which backend raised the error)
# ---------------------------------------------------------------------------

class HFConnectionError(RuntimeError):
    pass

class HFTimeoutError(RuntimeError):
    pass

class HFResponseError(RuntimeError):
    pass

class HFModelNotFoundError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class HFConfig(BaseModel):
    """All parameters controlling the HuggingFace Inference API connection."""

    api_base:   str   = Field(
        default="https://api-inference.huggingface.co/models",
        description="HuggingFace Inference API base URL."
    )
    model:      str   = Field(
        default=os.environ.get("HF_MODEL", "Qwen/Qwen2.5-32B-Instruct"),
        description="HuggingFace model ID."
    )
    token:      str   = Field(
        default=os.environ.get("HF_TOKEN", ""),
        description="HuggingFace API token (hf_...)."
    )

    # Generation
    temperature:    float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens:     int   = Field(default=1024, ge=1, le=32768)
    top_p:          float = Field(default=0.9, ge=0.0, le=1.0)

    # HTTP
    timeout:        float = Field(default=300.0, gt=0)
    max_retries:    int   = Field(default=3, ge=0, le=10)
    retry_delay:    float = Field(default=2.0, gt=0)

    @property
    def chat_url(self) -> str:
        return f"{self.api_base}/{self.model}/v1/chat/completions"

    @property
    def auth_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class HFClient:
    """
    HuggingFace Inference API client.
    Implements the same .chat() / .chat_stream() interface as OllamaClient.
    """

    def __init__(self, config: Optional[HFConfig] = None) -> None:
        self._cfg = config or HFConfig()
        logger.info(
            "[HF] Initialized client  model=%s  url=%s",
            self._cfg.model, self._cfg.chat_url,
        )
        if not self._cfg.token:
            logger.warning(
                "[HF] No HF_TOKEN set — requests may be rate-limited or rejected."
            )

    @property
    def model(self) -> str:
        return self._cfg.model

    # ------------------------------------------------------------------
    # Non-streaming
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: list[dict],
        *,
        temperature:    Optional[float] = None,
        max_tokens:     Optional[int]   = None,
        top_p:          Optional[float] = None,
        repeat_penalty: Optional[float] = None,  # not used by HF API, ignored
    ) -> dict:
        payload = self._build_payload(messages, stream=False,
                                      temperature=temperature,
                                      max_tokens=max_tokens,
                                      top_p=top_p)
        t_start = time.perf_counter()
        body    = self._post_with_retry(payload)
        latency = (time.perf_counter() - t_start) * 1000

        return self._parse_response(body, latency)

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    def chat_stream(
        self,
        messages: list[dict],
        *,
        temperature:    Optional[float] = None,
        max_tokens:     Optional[int]   = None,
        top_p:          Optional[float] = None,
        repeat_penalty: Optional[float] = None,
    ) -> Iterator[str]:
        payload = self._build_payload(messages, stream=True,
                                      temperature=temperature,
                                      max_tokens=max_tokens,
                                      top_p=top_p)
        timeout = httpx.Timeout(connect=15.0, read=self._cfg.timeout,
                                write=15.0, pool=5.0)

        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream(
                    "POST", self._cfg.chat_url,
                    json=payload,
                    headers=self._cfg.auth_headers,
                ) as response:
                    self._check_status(response.status_code)
                    for line in response.iter_lines():
                        line = line.strip()
                        if not line or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            line = line[len("data: "):]
                        try:
                            obj   = json.loads(line)
                            delta = obj["choices"][0].get("delta", {})
                            text  = delta.get("content", "")
                            if text:
                                yield text
                        except (json.JSONDecodeError, KeyError):
                            continue

        except httpx.ConnectError as exc:
            raise HFConnectionError(
                f"Cannot connect to HuggingFace API at {self._cfg.chat_url}."
            ) from exc
        except httpx.TimeoutException as exc:
            raise HFTimeoutError(
                f"HuggingFace API stream timed out after {self._cfg.timeout}s."
            ) from exc

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """Returns True if the HF token is set and API is reachable."""
        try:
            with httpx.Client(timeout=httpx.Timeout(10.0)) as client:
                r = client.get(
                    "https://huggingface.co",
                    headers=self._cfg.auth_headers,
                )
                return r.status_code < 500
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_payload(
        self,
        messages: list[dict],
        *,
        stream: bool,
        temperature: Optional[float],
        max_tokens: Optional[int],
        top_p: Optional[float],
    ) -> dict:
        return {
            "model":       self._cfg.model,
            "messages":    messages,
            "stream":      stream,
            "temperature": temperature if temperature is not None else self._cfg.temperature,
            "max_tokens":  max_tokens  if max_tokens  is not None else self._cfg.max_tokens,
            "top_p":       top_p       if top_p       is not None else self._cfg.top_p,
        }

    def _post_with_retry(self, payload: dict) -> dict:
        timeout = httpx.Timeout(connect=15.0, read=self._cfg.timeout,
                                write=15.0, pool=5.0)
        last_exc: Optional[Exception] = None

        for attempt in range(self._cfg.max_retries + 1):
            try:
                try:
                    with httpx.Client(timeout=timeout) as client:
                        response = client.post(
                            self._cfg.chat_url,
                            json=payload,
                            headers=self._cfg.auth_headers,
                        )
                except httpx.ConnectError as exc:
                    raise HFConnectionError(
                        f"Cannot connect to HuggingFace API at {self._cfg.chat_url}."
                    ) from exc
                except httpx.TimeoutException as exc:
                    raise HFTimeoutError(
                        f"HuggingFace API timed out after {self._cfg.timeout}s."
                    ) from exc

                self._check_status(response.status_code)
                return response.json()

            except (HFConnectionError, HFTimeoutError) as exc:
                last_exc = exc
                if attempt < self._cfg.max_retries:
                    wait = self._cfg.retry_delay * (2 ** attempt)
                    logger.warning("[HF] Attempt %d/%d failed with %s — retrying in %.1fs",
                                   attempt + 1, self._cfg.max_retries, type(exc).__name__, wait)
                    time.sleep(wait)
                else:
                    break

        raise last_exc  # type: ignore

    def _parse_response(self, body: dict, latency_ms: float) -> dict:
        try:
            choice  = body["choices"][0]
            content = choice["message"]["content"]
            usage   = body.get("usage", {})
            return {
                "answer":             content.strip(),
                "prompt_tokens":      usage.get("prompt_tokens", 0),
                "completion_tokens":  usage.get("completion_tokens", 0),
                "finish_reason":      choice.get("finish_reason", "stop"),
                "generation_time_ms": 0.0,   # HF API doesn't expose this
                "model_name":         body.get("model", self._cfg.model),
                "latency_ms":         round(latency_ms, 2),
            }
        except (KeyError, IndexError) as exc:
            raise HFResponseError(
                f"Unexpected HF API response structure: {exc}. body={body!r}"
            ) from exc

    def _check_status(self, status_code: int) -> None:
        if status_code == 200:
            return
        if status_code == 401:
            raise HFResponseError(
                "HuggingFace API returned 401 Unauthorized. "
                "Check your HF_TOKEN in .env."
            )
        if status_code == 404:
            raise HFModelNotFoundError(
                f"Model '{self._cfg.model}' not found on HuggingFace (HTTP 404). "
                "Check HF_MODEL in .env."
            )
        if status_code == 429:
            raise HFTimeoutError(
                "HuggingFace API rate limit hit (HTTP 429). "
                "Wait a moment or check your ZeroGPU quota."
            )
        if status_code == 503:
            raise HFTimeoutError(
                "HuggingFace model is loading (HTTP 503). Try again in 20 seconds."
            )
        raise HFResponseError(
            f"HuggingFace API returned HTTP {status_code}."
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_hf_client_instance: Optional[HFClient] = None


def get_hf_client(config: Optional[HFConfig] = None) -> HFClient:
    """Returns the process-level HFClient singleton."""
    global _hf_client_instance
    if _hf_client_instance is None:
        _hf_client_instance = HFClient(config)
    return _hf_client_instance


def reset_hf_client() -> None:
    """Clears the singleton — primarily for testing."""
    global _hf_client_instance
    _hf_client_instance = None
