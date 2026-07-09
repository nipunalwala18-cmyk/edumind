"""
rag/gemini_client.py
--------------------
Lightweight HTTP client for the Google Gemini API (Google AI Studio).
Provides a drop-in replacement for OllamaClient and HFClient.

API endpoints targeted:
- POST https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent?key=<api_key>
- POST https://generativelanguage.googleapis.com/v1beta/models/<model>:streamGenerateContent?alt=sse&key=<api_key>
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

class GeminiError(RuntimeError):
    """Base for all Gemini client errors."""

class GeminiConnectionError(GeminiError):
    """Could not reach the Gemini API."""

class GeminiTimeoutError(GeminiError):
    """Request exceeded the configured timeout."""

class GeminiResponseError(GeminiError):
    """Unexpected or malformed response from the Gemini API."""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class GeminiConfig(BaseModel):
    """All parameters controlling the Gemini API connection."""

    api_key:      str   = Field(default=os.environ.get("GEMINI_API_KEY", ""))
    model:        str   = Field(default=os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"))
    api_base:     str   = Field(default="https://generativelanguage.googleapis.com/v1beta")

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

class GeminiClient:
    """
    Thin wrapper around Gemini's v1beta generateContent and streamGenerateContent API.
    Implements the same interface as OllamaClient.
    """

    def __init__(self, config: Optional[GeminiConfig] = None) -> None:
        self._cfg = config or GeminiConfig()
        if not self._cfg.api_key:
            logger.warning("[GEMINI] No GEMINI_API_KEY set. Requests will fail.")

    @property
    def model(self) -> str:
        return self._cfg.model

    @property
    def config(self) -> GeminiConfig:
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
        repeat_penalty: Optional[float] = None,  # Not supported by Gemini, ignored
    ) -> dict:
        """
        Non-streaming chat. Returns parsed dict with answer, token counts, and latency.
        """
        payload = self._build_payload(messages, temperature, max_tokens, top_p)
        url = f"{self._cfg.api_base}/models/{self._cfg.model}:generateContent?key={self._cfg.api_key}"

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
        payload = self._build_payload(messages, temperature, max_tokens, top_p)
        url = f"{self._cfg.api_base}/models/{self._cfg.model}:streamGenerateContent?alt=sse&key={self._cfg.api_key}"
        timeout = httpx.Timeout(connect=10.0, read=self._cfg.timeout, write=10.0, pool=5.0)

        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        raise GeminiResponseError(
                            f"Gemini API returned status code {response.status_code}: {response.read().decode('utf-8')}"
                        )
                    for line in response.iter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[len("data: "):]
                        try:
                            obj = json.loads(data_str)
                            candidates = obj.get("candidates", [])
                            if not candidates:
                                continue
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                yield parts[0]["text"]
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except httpx.ConnectError as exc:
            raise GeminiConnectionError(f"Cannot connect to Gemini API endpoint.") from exc
        except httpx.TimeoutException as exc:
            raise GeminiTimeoutError(f"Gemini streaming timed out after {self._cfg.timeout}s.") from exc

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
        temperature: Optional[float],
        max_tokens: Optional[int],
        top_p: Optional[float],
    ) -> dict:
        """Converts standard chat messages to Gemini's API format."""
        system_instruction = None
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_instruction = {
                    "parts": [{"text": content}]
                }
            else:
                gemini_role = "user" if role == "user" else "model"
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": content}]
                })

        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature if temperature is not None else self._cfg.temperature,
                "maxOutputTokens": max_tokens if max_tokens is not None else self._cfg.max_tokens,
                "topP": top_p if top_p is not None else self._cfg.top_p,
            }
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        return payload

    def _post_json(self, url: str, payload: dict) -> dict:
        """Helper to post JSON data with retries."""
        timeout = httpx.Timeout(connect=10.0, read=self._cfg.timeout, write=10.0, pool=5.0)
        last_exc: Optional[Exception] = None

        for attempt in range(self._cfg.max_retries + 1):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(url, json=payload)
                    if response.status_code != 200:
                        raise GeminiResponseError(
                            f"Gemini API returned status code {response.status_code}: {response.text}"
                        )
                    return response.json()
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt == self._cfg.max_retries:
                    break
                time.sleep(self._cfg.retry_delay * (2 ** attempt))

        if isinstance(last_exc, httpx.ConnectError):
            raise GeminiConnectionError("Cannot connect to Gemini API endpoint.") from last_exc
        else:
            raise GeminiTimeoutError("Gemini API request timed out.") from last_exc

    def _parse_chat_response(self, body: dict) -> dict:
        """Parses the non-streaming Gemini API response."""
        try:
            candidates = body.get("candidates", [])
            if not candidates:
                raise GeminiResponseError("Gemini API response has no candidates.")
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            answer = parts[0].get("text", "") if parts else ""
            
            finish_reason = candidates[0].get("finishReason", "STOP").lower()
            
            usage = body.get("usageMetadata", {})
            p_tokens = usage.get("promptTokenCount", 0)
            c_tokens = usage.get("candidatesTokenCount", 0)
            
        except (KeyError, IndexError, TypeError) as exc:
            raise GeminiResponseError(f"Malformed Gemini API response: {exc}. Body: {body}") from exc

        return {
            "answer": answer,
            "prompt_tokens": p_tokens,
            "completion_tokens": c_tokens,
            "finish_reason": finish_reason,
            "generation_time_ms": 0.0,  # Gemini doesn't report exact generation latency in metadata
            "model_name": self._cfg.model,
        }


# ---------------------------------------------------------------------------
# Singleton Getter
# ---------------------------------------------------------------------------

_gemini_client_instance: Optional[GeminiClient] = None

def get_gemini_client(config: Optional[GeminiConfig] = None) -> GeminiClient:
    global _gemini_client_instance
    if _gemini_client_instance is None:
        _gemini_client_instance = GeminiClient(config)
    return _gemini_client_instance
