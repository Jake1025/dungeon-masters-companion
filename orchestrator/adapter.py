from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Mapping, Optional

import ollama


logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when the language model fails to provide valid JSON."""


class LLMAdapter:
    """Small wrapper around Ollama to enforce strict JSON contracts per stage."""

    def __init__(
        self,
        model: str,
        *,
        default_temperature: float = 0.0,
        stage_temperatures: Optional[Mapping[str, float]] = None,
        options: Optional[Mapping[str, Any]] = None,
        max_attempts: int = 3,
        verbose: bool = False,
    ) -> None:
        self.model = model
        self.default_temperature = default_temperature
        self.stage_temperatures = dict(stage_temperatures or {})
        self.options = dict(options or {})
        self.max_attempts = max(1, max_attempts)
        self.verbose = verbose

    def request_json(
        self,
        stage: str,
        system_prompt: str,
        payload: Dict[str, Any],
        *,
        validator: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Call Ollama with deterministic settings and ensure JSON output."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, separators=(",", ":"))},
        ]
        options = dict(self.options)
        temperature = self.stage_temperatures.get(stage, self.default_temperature)
        options.setdefault("temperature", temperature)

        if self.verbose:
            logger.debug("Stage %s payload:\n%s", stage, json.dumps(payload, indent=2))

        attempts: List[str] = []
        for idx in range(self.max_attempts):
            response = ollama.chat(
                model=self.model,
                messages=messages,
                format="json",
                options=options,
            )
            content = self._extract_content(response)
            attempts.append(content)
            if self.verbose:
                logger.debug("Stage %s attempt %s raw response: %s", stage, idx + 1, content)
            try:
                data = self._parse_json(content)
                if validator:
                    validator(data)
                if self.verbose:
                    logger.debug("Stage %s parsed response:\n%s", stage, json.dumps(data, indent=2))
                return data
            except Exception as exc:
                logger.debug("LLM attempt %s failed for stage %s: %s", idx + 1, stage, exc)
                if idx == self.max_attempts - 1:
                    break
                messages.append(
                    {
                        "role": "system",
                        "content": "Output must be valid JSON. Re-emit the payload using the agreed schema.",
                    }
                )

        raise LLMError(f"Stage '{stage}' failed to return valid JSON after {self.max_attempts} attempts. Last output: {attempts[-1] if attempts else '<none>'}")

    @staticmethod
    def _extract_content(response: Any) -> str:
        message = getattr(response, "message", None)
        if message is None and isinstance(response, dict):
            message = response.get("message")
        if hasattr(message, "model_dump"):
            payload = message.model_dump(exclude_none=True)
        elif isinstance(message, dict):
            payload = message
        else:
            payload = {}
        content = payload.get("content", "")
        if isinstance(content, list):
            content = "".join(str(chunk) for chunk in content)
        return str(content).strip()

    def _parse_json(self, raw: str) -> Dict[str, Any]:
        cleaned = self._strip_code_fence(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            alt = self._parse_minidict(cleaned)
            if alt is not None:
                return alt
            raise

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        if text.startswith("```"):
            lines = text.splitlines()
            # drop first and last fence lines
            core = [line for line in lines if not line.startswith("```")]
            return "\n".join(core).strip()
        return text

    @staticmethod
    def _parse_minidict(text: str) -> Optional[Dict[str, Any]]:
        """
        Support a tiny "key: value" DSL as a last resort; used when the model
        forgets to emit strict JSON despite the format hint.
        """
        if "{" in text or "[" in text:
            return None
        candidate: Dict[str, Any] = {}
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                return None
            key, value = line.split(":", 1)
            key = key.strip().strip('"')
            value = value.strip()
            parsed: Any = value
            if value.lower() in {"true", "false"}:
                parsed = value.lower() == "true"
            else:
                try:
                    parsed = json.loads(value)
                except json.JSONDecodeError:
                    if value.isdigit():
                        parsed = int(value)
                    else:
                        try:
                            parsed = float(value)
                        except ValueError:
                            parsed = value.strip('"')
            candidate[key] = parsed
        return candidate or None


__all__ = ["LLMAdapter", "LLMError"]
