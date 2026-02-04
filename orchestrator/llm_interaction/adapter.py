from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Mapping, Optional

import ollama
from ollama import ResponseError

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when the LLM fails after retries."""


class LLMAdapter:
    """
    Thin gateway around the LLM API.
    Handles sending, retries, parsing, and normalization.
    """

    def __init__(
        self,
        model: str,
        *,
        default_options: Optional[Mapping[str, Any]] = None,
        stage_options: Optional[Mapping[str, Mapping[str, Any]]] = None,
        max_attempts: int = 3,
        verbose: bool = False,
    ) -> None:

        self.model = model
        self.default_options = dict(default_options or {})
        self.stage_options = dict(stage_options or {})
        self.max_attempts = max(1, max_attempts)
        self.verbose = verbose

    # -------------------------------------------------

    def request_text(self, stage: str, system_prompt: str, payload_text: str) -> str:
        messages = self._build_messages(system_prompt, payload_text)
        options = self._stage_options(stage)

        if self.verbose:
            logger.info("[%s] request started", stage.upper())

        for attempt in range(1, self.max_attempts + 1):
            try:
                response = ollama.chat(
                    model=self.model,
                    messages=messages,
                    options=options,
                )
                content = self._extract_content(response)

            except ResponseError as exc:
                content = self._extract_raw_from_error(exc) or ""

            content = content.strip()

            if content:
                if self.verbose:
                    logger.info("[%s] success (%s chars)", stage.upper(), len(content))
                return content

            messages.append(
                {
                    "role": "system",
                    "content": "Please provide a detailed natural-language response.",
                }
            )

        raise LLMError(f"Stage '{stage}' failed after {self.max_attempts} attempts.")

    # -------------------------------------------------

    def request_json(
        self,
        stage: str,
        system_prompt: str,
        payload: Dict[str, Any],
        *,
        validator: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:

        messages = self._build_messages(
            system_prompt,
            json.dumps(payload, separators=(",", ":")),
        )
        options = self._stage_options(stage)

        if self.verbose:
            logger.info("[%s] JSON request started", stage.upper())

        for attempt in range(1, self.max_attempts + 1):
            response = ollama.chat(
                model=self.model,
                messages=messages,
                format="json",
                options=options,
            )

            raw = self._extract_content(response)

            try:
                data = self._parse_json(raw)

                if validator:
                    validator(data)

                if self.verbose:
                    logger.info("[%s] JSON parsed", stage.upper())

                return data

            except Exception as exc:
                logger.warning("[%s] parse failed: %s", stage.upper(), exc)

                messages.append(
                    {
                        "role": "system",
                        "content": "Output must be valid JSON.",
                    }
                )

        raise LLMError(f"Stage '{stage}' failed to return valid JSON.")

    # -------------------------------------------------

    def _build_messages(self, system_prompt: str, user_payload: str):
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ]

    def _stage_options(self, stage: str) -> Dict[str, Any]:
        options = dict(self.default_options)

        if stage in self.stage_options:
            options.update(self.stage_options[stage])

        return options

    # -------------------------------------------------

    @staticmethod
    def _extract_content(response: Any) -> str:
        message = getattr(response, "message", None)

        if message is None and isinstance(response, dict):
            message = response.get("message")

        if not message:
            return ""

        if hasattr(message, "model_dump"):
            payload = message.model_dump(exclude_none=True)
        elif isinstance(message, dict):
            payload = message
        else:
            return ""

        content = payload.get("content", "")

        if isinstance(content, list):
            content = "".join(map(str, content))

        return str(content)

    @staticmethod
    def _extract_raw_from_error(exc: Exception) -> Optional[str]:
        msg = str(exc)
        marker = "raw='"
        start = msg.find(marker)
        if start == -1:
            return None
        start += len(marker)
        end = msg.find("'", start)
        return None if end == -1 else msg[start:end]

    # -------------------------------------------------

    def _parse_json(self, raw: str) -> Dict[str, Any]:
        cleaned = self._strip_code_fence(raw)
        return json.loads(cleaned)

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        if text.startswith("```"):
            return "\n".join(
                line for line in text.splitlines() if not line.startswith("```")
            ).strip()
        return text


__all__ = ["LLMAdapter", "LLMError"]
