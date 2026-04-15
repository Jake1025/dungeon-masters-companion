from __future__ import annotations

import copy
import json
import logging
import os
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Union

try:
    import ollama
    from ollama import ResponseError
except ImportError:  # pragma: no cover - optional dependency per provider
    ollama = None

    class ResponseError(Exception):
        pass

logger = logging.getLogger(__name__)
DMC_ROLL_REQUIRED_SENTINEL = "__DMC_ROLL_REQUIRED__"


class LLMError(RuntimeError):
    """Raised when the LLM fails after retries."""


class LLMAdapter:
    """
    Thin gateway around the LLM API.
    Handles transport-level retries and normalization.
    """

    def __init__(
        self,
        model: str,
        *,
        provider: str = "ollama",
        default_options: Optional[Mapping[str, Any]] = None,
        stage_options: Optional[Mapping[str, Mapping[str, Any]]] = None,
        max_attempts: int = 3,
        verbose: bool = False,
        force_retry_stage: Optional[str] = None,  # used ONLY by LLMStep
    ) -> None:

        self.provider = str(provider or "ollama").strip().lower()
        self.model = model
        self.default_options = dict(default_options or {})
        self.stage_options = dict(stage_options or {})
        self.max_attempts = max(1, max_attempts)
        self.verbose = verbose
        self.force_retry_stage = force_retry_stage
        self._openai_client: Any = None
        self._anthropic_client: Any = None

    def _require_openai_client(self):
        if self._openai_client is not None:
            return self._openai_client
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMError("OpenAI provider requires the `openai` package.") from exc
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise LLMError("OPENAI_API_KEY is required when provider=openai.")
        self._openai_client = OpenAI(api_key=api_key)
        return self._openai_client

    def _require_anthropic_client(self):
        if self._anthropic_client is not None:
            return self._anthropic_client
        try:
            import anthropic
        except ImportError as exc:
            raise LLMError("Anthropic provider requires the `anthropic` package.") from exc
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is required when provider=anthropic.")
        self._anthropic_client = anthropic.Anthropic(api_key=api_key)
        return self._anthropic_client

    # -------------------------------------------------

    def request_text(self, stage: str, system_prompt: str, payload_text: str) -> tuple[str, list[dict]]:
        messages = self._build_messages(system_prompt, payload_text)
        options = self._stage_options(stage)

        if self.verbose:
            logger.info("[%s] request started", stage.upper())

        attempt_history = []

        for attempt in range(1, self.max_attempts + 1):
            if self.verbose:
                print(f"[LLM] Transport attempt {attempt} for stage '{stage}'")

            try:
                response = self._chat_with_retry(
                    messages=messages,
                    options=options,
                    stage=stage,
                )
                content = self._extract_content(response)

            except ResponseError as exc:
                content = self._extract_raw_from_error(exc) or ""

            content = content.strip()
            
            attempt_history.append({
                "attempt": attempt,
                "content": content,
                "success": bool(content)
            })

            if content:
                if self.verbose:
                    logger.info(
                        "[%s] success (%s chars)",
                        stage.upper(),
                        len(content),
                    )
                return content, attempt_history

            # empty → retry
            if self.verbose:
                print(f"[LLM-RETRY] Attempt {attempt} returned empty, retrying...")
            
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
            if self.provider == "ollama":
                if ollama is None:
                    raise LLMError("Ollama provider requires the `ollama` package.")
                response = ollama.chat(
                    model=self.model,
                    messages=messages,
                    format="json",
                    options=options,
                )
            else:
                response = self._chat_with_retry(
                    messages=messages,
                    options=options,
                    stage=stage,
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
        if hasattr(response, "choices"):  # OpenAI chat completion
            choices = getattr(response, "choices", None) or []
            if choices:
                message = getattr(choices[0], "message", None)
                if message is not None:
                    content = getattr(message, "content", "")
                    if isinstance(content, list):
                        return "".join(str(part) for part in content)
                    return str(content or "")

        if hasattr(response, "content"):  # Anthropic messages response
            blocks = getattr(response, "content", None) or []
            texts: list[str] = []
            for block in blocks:
                block_type = getattr(block, "type", None)
                if block_type == "text":
                    texts.append(str(getattr(block, "text", "") or ""))
            if texts:
                return "\n".join(part for part in texts if part).strip()

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
    def _extract_thinking(response: Any) -> str:
        """
        Extract model reasoning/thinking text when the backend provides it.
        Different Ollama models expose this under slightly different keys.
        """
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

        for key in ("thinking", "reasoning", "reasoning_content"):
            value = payload.get(key)
            if value is None:
                continue
            if isinstance(value, list):
                value = "".join(map(str, value))
            text = str(value).strip()
            if text:
                return text
        return ""

    @staticmethod
    def _extract_tool_calls(response: Any) -> list[dict[str, Any]]:
        """
        Normalize Ollama tool calls into a plain list of dicts:
        [{'function': {'name': str, 'arguments': {...}}}, ...]
        """
        # OpenAI chat.completions response
        if hasattr(response, "choices"):
            choices = getattr(response, "choices", None) or []
            if choices:
                message = getattr(choices[0], "message", None)
                if message is not None:
                    tool_calls = getattr(message, "tool_calls", None) or []
                    normalized: list[dict[str, Any]] = []
                    for tc in tool_calls:
                        if hasattr(tc, "model_dump"):
                            normalized.append(tc.model_dump(exclude_none=True))
                        elif isinstance(tc, dict):
                            normalized.append(tc)
                    return normalized

        # Anthropic messages response
        if hasattr(response, "content"):
            blocks = getattr(response, "content", None) or []
            normalized: list[dict[str, Any]] = []
            for idx, block in enumerate(blocks):
                if getattr(block, "type", None) != "tool_use":
                    continue
                name = str(getattr(block, "name", "") or "")
                arguments = getattr(block, "input", {}) or {}
                tool_id = str(getattr(block, "id", "") or f"call_{idx}")
                normalized.append(
                    {
                        "id": tool_id,
                        "function": {
                            "name": name,
                            "arguments": arguments,
                        },
                    }
                )
            return normalized

        message = getattr(response, "message", None)
        if message is None and isinstance(response, dict):
            message = response.get("message")
        if not message:
            return []

        # pydantic model case
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            normalized: list[dict[str, Any]] = []
            for tc in tool_calls:
                if hasattr(tc, "model_dump"):
                    normalized.append(tc.model_dump(exclude_none=True))
                elif isinstance(tc, dict):
                    normalized.append(tc)
            return normalized

        # dict case
        if isinstance(message, dict):
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list):
                return [tc for tc in tool_calls if isinstance(tc, dict)]

        return []

    @staticmethod
    def _normalize_tool_calls(response: Any) -> list[dict[str, Any]]:
        """
        Convert model tool calls into a stable shape:
        [{'id': str, 'name': str, 'arguments': dict, 'raw': dict}, ...]
        """
        normalized: list[dict[str, Any]] = []

        for idx, call in enumerate(LLMAdapter._extract_tool_calls(response)):
            if not isinstance(call, dict):
                continue

            function_payload = call.get("function")
            if isinstance(function_payload, dict):
                name = function_payload.get("name") or call.get("name") or ""
                arguments = function_payload.get("arguments", {})
            else:
                name = call.get("name", "")
                arguments = call.get("arguments", {})

            parsed_arguments: dict[str, Any] = {}

            if isinstance(arguments, str):
                try:
                    loaded = json.loads(arguments)
                    if isinstance(loaded, dict):
                        parsed_arguments = loaded
                except json.JSONDecodeError:
                    parsed_arguments = {}
            elif isinstance(arguments, Mapping):
                parsed_arguments = dict(arguments)

            normalized.append(
                {
                    "id": call.get("id") or f"call_{idx}",
                    "name": str(name),
                    "arguments": parsed_arguments,
                    "raw": call,
                }
            )

        return normalized

    def _chat_with_retry(
        self,
        messages: list[dict[str, Any]],
        options: Dict[str, Any],
        stage: str,
        *,
        tools: Optional[Sequence[Union[Mapping[str, Any], Any, Callable]]] = None,
    ) -> Any:
        for attempt in range(1, self.max_attempts + 1):
            if self.verbose:
                print(f"[LLM] Transport attempt {attempt} for stage '{stage}'")
            try:
                if self.provider == "ollama":
                    if ollama is None:
                        raise LLMError("Ollama provider requires the `ollama` package.")
                    return ollama.chat(
                        model=self.model,
                        messages=messages,
                        tools=tools,
                        options=options,
                    )
                if self.provider == "openai":
                    return self._openai_chat(messages=messages, options=options, tools=tools)
                if self.provider == "anthropic":
                    return self._anthropic_chat(messages=messages, options=options, tools=tools)
                raise LLMError(f"Unsupported provider '{self.provider}'.")
            except ResponseError as exc:
                raw = self._extract_raw_from_error(exc)
                if raw:
                    return {"message": {"content": raw}}
            except Exception:
                if attempt >= self.max_attempts:
                    raise
        raise LLMError(f"Stage '{stage}' failed after {self.max_attempts} attempts.")

    def _openai_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        options: Dict[str, Any],
        tools: Optional[Sequence[Union[Mapping[str, Any], Any, Callable]]] = None,
    ) -> Any:
        client = self._require_openai_client()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            **options,
        }
        if tools:
            kwargs["tools"] = list(tools)
        return client.chat.completions.create(**kwargs)

    @staticmethod
    def _to_anthropic_messages(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        system_parts: list[str] = []
        converted: list[dict[str, Any]] = []

        for msg in messages:
            role = str(msg.get("role", "")).strip().lower()
            if role == "system":
                system_parts.append(str(msg.get("content", "") or ""))
                continue
            if role == "tool":
                content = str(msg.get("content", "") or "")
                tool_name = str(msg.get("tool_name", "") or "")
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": str(msg.get("tool_call_id") or f"{tool_name}_result"),
                                "content": content,
                            }
                        ],
                    }
                )
                continue
            converted.append(
                {
                    "role": "assistant" if role == "assistant" else "user",
                    "content": str(msg.get("content", "") or ""),
                }
            )
        return "\n\n".join(part for part in system_parts if part).strip(), converted

    def _anthropic_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        options: Dict[str, Any],
        tools: Optional[Sequence[Union[Mapping[str, Any], Any, Callable]]] = None,
    ) -> Any:
        client = self._require_anthropic_client()
        system_text, anthropic_messages = self._to_anthropic_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": int(options.get("max_tokens", 1024)),
        }
        if system_text:
            kwargs["system"] = system_text
        if "temperature" in options:
            kwargs["temperature"] = options["temperature"]
        if tools:
            anthropic_tools: list[dict[str, Any]] = []
            for tool in tools:
                if not isinstance(tool, Mapping):
                    continue
                function_payload = tool.get("function")
                if not isinstance(function_payload, Mapping):
                    continue
                anthropic_tools.append(
                    {
                        "name": str(function_payload.get("name", "")),
                        "description": str(function_payload.get("description", "")),
                        "input_schema": dict(function_payload.get("parameters", {})),
                    }
                )
            if anthropic_tools:
                kwargs["tools"] = anthropic_tools
        return client.messages.create(**kwargs)

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
                line for line in text.splitlines()
                if not line.startswith("```")
            ).strip()
        return text

    # --------------------------------------------------

    def request_with_tools(
        self, 
        stage: str, 
        system_prompt: str, 
        messages: list[dict],
        tools: list[dict]
    ) -> dict:
        """
        Makes a request that supports tool calling.
        Returns the full response dict from ollama.
        """
        options = self._stage_options(stage)
        
        if self.verbose:
            logger.info("[%s] tool-enabled request started", stage.upper())
        
        response = self._chat_with_retry(
            messages=[
                {"role": "system", "content": system_prompt},
                *messages,
            ],
            options=options,
            stage=stage,
            tools=tools,
        )
        
        return response

    # --------------------------------------------------

    def run_tool_loop(
        self,
        *,
        stage: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: Sequence[Mapping[str, Any]],
        tool_executor: Optional[Callable[[str, Mapping[str, Any]], Any]] = None,
        max_iterations: int = 10,
        pre_tool_use: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
        post_tool_use: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], Optional[str]]] = None,
        assistant_response_hook: Optional[Callable[[str, Sequence[Dict[str, Any]], int], Optional[str]]] = None,
        stop_hook: Optional[Callable[[str, bool], Optional[str]]] = None,
    ) -> Dict[str, Any]:
        """
        Generic iterative model->tool->result loop.
        Mirrors Copilot-style orchestration with optional hook controls.
        """
        max_iterations = max(1, max_iterations)
        convo_messages: list[dict[str, Any]] = list(messages)
        rounds: list[dict[str, Any]] = []
        tool_trace: list[dict[str, Any]] = []
        stop_hook_active = False

        for iteration in range(1, max_iterations + 1):
            if self.verbose:
                print(f"[LOOP] {stage} iteration {iteration}")
            response = self.request_with_tools(
                stage=stage,
                system_prompt=system_prompt,
                messages=convo_messages,
                tools=list(tools),
            )

            assistant_text = self._extract_content(response).strip()
            assistant_thinking = self._extract_thinking(response).strip()
            tool_calls = self._normalize_tool_calls(response)

            round_info: dict[str, Any] = {
                "iteration": iteration,
                "assistant_text": assistant_text,
                "assistant_thinking": assistant_thinking,
                "tool_calls": [
                    {
                        "id": call["id"],
                        "name": call["name"],
                        "arguments": copy.deepcopy(call["arguments"]),
                    }
                    for call in tool_calls
                ],
                "tool_results": [],
                "stop_hook_active": stop_hook_active,
                "hook_notes": [],
            }
            rounds.append(round_info)

            if assistant_response_hook:
                response_block_reason = assistant_response_hook(
                    assistant_text,
                    round_info["tool_calls"],
                    iteration,
                )
                if response_block_reason:
                    round_info["response_block_reason"] = response_block_reason
                    convo_messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Your last response was invalid for this phase: "
                                f"{response_block_reason} Re-respond and follow the required structure."
                            ),
                        }
                    )
                    continue

            if not tool_calls:
                stop_reason = stop_hook(assistant_text, stop_hook_active) if stop_hook else None
                if stop_reason:
                    stop_hook_active = True
                    round_info["stop_block_reason"] = stop_reason
                    convo_messages.append(
                        {
                            "role": "user",
                            "content": (
                                "You were about to finish, but a stop hook blocked completion: "
                                f"{stop_reason}"
                            ),
                        }
                    )
                    continue

                convo_messages.append({"role": "assistant", "content": assistant_text})
                return {
                    "status": "completed",
                    "final_answer": assistant_text,
                    "rounds": rounds,
                    "messages": convo_messages,
                    "tool_calls": tool_trace,
                }

            convo_messages.append(
                {
                    "role": "assistant",
                    "content": assistant_text,
                    "tool_calls": [call["raw"] for call in tool_calls],
                }
            )

            for call in tool_calls:
                tool_name = call["name"]
                arguments = call["arguments"]

                if pre_tool_use:
                    pre_result = pre_tool_use(tool_name, arguments) or {"allow": True}
                else:
                    pre_result = {"allow": True}

                if not pre_result.get("allow", True):
                    tool_payload: dict[str, Any] = {
                        "ok": False,
                        "error": pre_result.get("reason", "Blocked by pre_tool_use hook."),
                    }
                elif tool_executor is None:
                    tool_payload = {
                        "ok": False,
                        "error": f"No tool executor configured for '{tool_name}'.",
                    }
                else:
                    try:
                        tool_result = tool_executor(tool_name, arguments)
                        if isinstance(tool_result, dict):
                            tool_payload = copy.deepcopy(tool_result)
                        else:
                            tool_payload = {"ok": True, "result": copy.deepcopy(tool_result)}
                    except Exception as exc:
                        # Manual roll mode in the Streamlit UI signals "wait for player roll"
                        # by raising a sentinel runtime error from the tool executor.
                        # This must escape the tool loop so the UI can render the dice component.
                        if DMC_ROLL_REQUIRED_SENTINEL in str(exc):
                            raise
                        tool_payload = {"ok": False, "error": str(exc)}

                tool_entry = {
                    "iteration": iteration,
                    "id": call.get("id"),
                    "name": tool_name,
                    "arguments": copy.deepcopy(arguments),
                    "result": copy.deepcopy(tool_payload),
                }
                round_info["tool_results"].append(tool_entry)
                tool_trace.append(copy.deepcopy(tool_entry))

                convo_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id"),
                        "tool_name": tool_name,
                        "content": json.dumps(tool_payload, separators=(",", ":"), ensure_ascii=True),
                    }
                )

                if post_tool_use:
                    post_note = post_tool_use(tool_name, arguments, tool_payload)
                    if post_note:
                        round_info.setdefault("hook_notes", []).append(str(post_note))
                        convo_messages.append({"role": "user", "content": f"Hook note: {post_note}"})

        return {
            "status": "max_iterations",
            "final_answer": "Stopped due to max iterations before final response.",
            "rounds": rounds,
            "messages": convo_messages,
            "tool_calls": tool_trace,
        }


__all__ = ["LLMAdapter", "LLMError"]
