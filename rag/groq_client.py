"""
rag/groq_client.py
------------------
Lightweight HTTP client for the Groq Cloud API.
Provides a drop-in replacement for OllamaClient, HFClient, and GeminiClient.

API endpoint targeted:
- POST https://api.groq.com/openai/v1/chat/completions
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
# Exceptions
# ---------------------------------------------------------------------------

class GroqError(RuntimeError):
    """Base for all Groq client errors."""

class GroqConnectionError(GroqError):
    """Could not reach the Groq API."""

class GroqTimeoutError(GroqError):
    """Request exceeded the configured timeout."""

class GroqResponseError(GroqError):
    """Unexpected or malformed response from the Groq API."""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class GroqConfig(BaseModel):
    """All parameters controlling the Groq API connection."""

    api_key:      str   = Field(default=os.environ.get("GROQ_API_KEY", ""))
    model:        str   = Field(default=os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"))
    api_base:     str   = Field(default="https://api.groq.com/openai/v1")

    # Generation
    temperature:  float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens:   int   = Field(default=1024, ge=1, le=8192)
    top_p:        float = Field(default=0.9, ge=0.0, le=1.0)

    # HTTP / retry
    timeout:      float = Field(default=60.0, gt=0)
    max_retries:  int   = Field(default=3, ge=0, le=10)
    retry_delay:  float = Field(default=1.0, gt=0)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class GroqClient:
    """
    Thin wrapper around Groq's chat completion endpoint.
    Implements the same interface as OllamaClient.
    """

    def __init__(self, config: Optional[GroqConfig] = None) -> None:
        self._cfg = config or GroqConfig()
        if not self._cfg.api_key:
            logger.warning("[GROQ] No GROQ_API_KEY set. Requests will fail.")

    @property
    def model(self) -> str:
        return self._cfg.model

    @property
    def config(self) -> GroqConfig:
        return self._cfg

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: list[dict],
        *,
        temperature:    Optional[float] = None,
        max_tokens:     Optional[int]   = None,
        top_p:          Optional[float] = None,
        repeat_penalty: Optional[float] = None,  # Not supported by Groq, ignored
    ) -> dict:
        """
        Non-streaming chat. Returns parsed dict with answer, token counts, and latency.
        """
        payload = self._build_payload(messages, False, temperature, max_tokens, top_p)
        url = f"{self._cfg.api_base}/chat/completions"

        t_start = time.perf_counter()
        body = self._post_json(url, payload)
        latency = (time.perf_counter() - t_start) * 1000

        result = self._parse_chat_response(body)
        result["latency_ms"] = round(latency, 2)
        return result

    def chat_stream(
        self,
        messages: list[dict],
        *,
        temperature:    Optional[float] = None,
        max_tokens:     Optional[int]   = None,
        top_p:          Optional[float] = None,
        repeat_penalty: Optional[float] = None,
    ) -> Iterator[str]:
        """
        Streaming chat. Yields text chunk strings as they arrive.
        """
        payload = self._build_payload(messages, True, temperature, max_tokens, top_p)
        url = f"{self._cfg.api_base}/chat/completions"
        timeout = httpx.Timeout(connect=10.0, read=self._cfg.timeout, write=10.0, pool=5.0)
        headers = {
            "Authorization": f"Bearer {self._cfg.api_key}",
            "Content-Type": "application/json"
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        raise GroqResponseError(
                            f"Groq API returned status code {response.status_code}: {response.read().decode('utf-8')}"
                        )
                    for line in response.iter_lines():
                        line = line.strip()
                        if not line or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            line = line[len("data: "):]
                        try:
                            obj = json.loads(line)
                            choices = obj.get("choices", [])
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {})
                            text = delta.get("content", "")
                            if text:
                                yield text
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except httpx.ConnectError as exc:
            raise GroqConnectionError(f"Cannot connect to Groq API endpoint.") from exc
        except httpx.TimeoutException as exc:
            raise GroqTimeoutError(f"Groq streaming timed out after {self._cfg.timeout}s.") from exc

    def health_check(self) -> bool:
        """Returns True if the API is configured and responds to a simple check."""
        if not self._cfg.api_key:
            return False
        try:
            messages = [{"role": "user", "content": "ping"}]
            self.chat(messages, max_tokens=5)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_payload(
        self,
        messages: list[dict],
        stream: bool,
        temperature: Optional[float],
        max_tokens: Optional[int],
        top_p: Optional[float],
    ) -> dict:
        """Converts standard chat messages to OpenAI/Groq API format."""
        payload: dict = {
            "model": self._cfg.model,
            "messages": messages,
            "stream": stream,
            "temperature": temperature if temperature is not None else self._cfg.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self._cfg.max_tokens,
            "top_p": top_p if top_p is not None else self._cfg.top_p,
        }
        return payload

    def _post_json(self, url: str, payload: dict) -> dict:
        """Helper to post JSON data with retries."""
        timeout = httpx.Timeout(connect=10.0, read=self._cfg.timeout, write=10.0, pool=5.0)
        headers = {
            "Authorization": f"Bearer {self._cfg.api_key}",
            "Content-Type": "application/json"
        }
        last_exc: Optional[Exception] = None

        for attempt in range(self._cfg.max_retries + 1):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(url, json=payload, headers=headers)
                    if response.status_code != 200:
                        raise GroqResponseError(
                            f"Groq API returned status code {response.status_code}: {response.text}"
                        )
                    return response.json()
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt == self._cfg.max_retries:
                    break
                time.sleep(self._cfg.retry_delay * (2 ** attempt))

        if isinstance(last_exc, httpx.ConnectError):
            raise GroqConnectionError("Cannot connect to Groq API endpoint.") from last_exc
        else:
            raise GroqTimeoutError("Groq API request timed out.") from last_exc

    def _parse_chat_response(self, body: dict) -> dict:
        """Parses the non-streaming Groq API response."""
        try:
            choices = body.get("choices", [])
            if not choices:
                raise GroqResponseError("Groq API response has no choices.")
            
            message = choices[0].get("message", {})
            answer = message.get("content", "")
            
            finish_reason = choices[0].get("finish_reason", "stop")
            
            usage = body.get("usage", {})
            p_tokens = usage.get("prompt_tokens", 0)
            c_tokens = usage.get("completion_tokens", 0)
            
        except (KeyError, IndexError, TypeError) as exc:
            raise GroqResponseError(f"Malformed Groq API response: {exc}. Body: {body}") from exc

        return {
            "answer": answer,
            "prompt_tokens": p_tokens,
            "completion_tokens": c_tokens,
            "finish_reason": finish_reason,
            "generation_time_ms": 0.0,
            "model_name": self._cfg.model,
        }


# ---------------------------------------------------------------------------
# Singleton Getter
# ---------------------------------------------------------------------------

_groq_client_instance: Optional[GroqClient] = None

def get_groq_client(config: Optional[GroqConfig] = None) -> GroqClient:
    global _groq_client_instance
    if _groq_client_instance is None:
        _groq_client_instance = GroqClient(config)
    return _groq_client_instance
