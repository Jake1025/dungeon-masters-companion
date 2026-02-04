from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
import re

from orchestrator.llm_interaction.adapter import LLMAdapter, LLMError

# =========================
# Core Step Object
# =========================

@dataclass
class LLMStep:
    """
    Defines a single structured LLM operation.
    """
    name: str
    system_prompt: str
    tags: set[str]
    use_cot: bool = True
    max_attempts: int = 3
    validator: Optional[Callable[[Dict[str, str]], None]] = None
    parser: Optional[Callable[[Dict[str, str]], Any]] = None

    def run(self, adapter: LLMAdapter, payload_text: str) -> tuple[Any, Dict[str, Any]]:
        tags = set(self.tags)
        if self.use_cot:
            tags |= {"thoughts"}

        attempts: List[Dict[str, Any]] = []

        for attempt_num in range(1, self.max_attempts + 1):
            raw = adapter.request_text(self.name, self.system_prompt, payload_text)
            sections = parse_sections(raw, tags)

            try:
                if self.validator:
                    self.validator(sections)
                parsed = self.parser(sections) if self.parser else sections
            except Exception as exc:
                attempts.append({
                    "attempt": attempt_num,
                    "prompt": payload_text,
                    "raw": raw,
                    "sections": sections,
                    "error": str(exc),
                })

                payload_text += (
                    f"\n\n(Note: last output was invalid: {exc}. "
                    "Please follow the required format.)"
                )
                continue

            attempts.append({
                "attempt": attempt_num,
                "prompt": payload_text,
                "raw": raw,
                "sections": sections,
                "parsed": parsed,
            })

            return parsed, {"attempts": attempts}

        raise LLMError(f"Step '{self.name}' failed after {self.max_attempts} attempts.")




# =========================
# Parsing Helpers
# =========================

def parse_sections(text: str, tags: set[str]) -> Dict[str, str]:
    result: Dict[str, List[str]] = {}
    current: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        lower = stripped.lower()

        matched = None
        for tag in sorted(tags):
            prefix = f"{tag}:"
            if lower.startswith(prefix):
                matched = tag
                content = stripped[len(prefix):].strip()
                result[tag] = [content]
                current = tag
                break

        if matched is None and current and stripped:
            result[current].append(stripped)

    return {
        tag: " ".join(lines).strip()
        for tag, lines in result.items()
        if lines
    }




# =========================
# Step-Specific Parsers
# =========================

def parse_intent(sections: Dict[str, str]) -> Dict[str, Any]:
    action = sections.get("action", "").strip()
    targets = [t.strip() for t in sections.get("targets", "").split(",") if t.strip()]
    refusals = [t.strip() for t in sections.get("refusals", "").split(",") if t.strip()]
    return {"action": action, "targets": targets, "refusals": refusals}


def parse_focus(sections: Dict[str, str]) -> List[str]:
    raw = sections.get("focus", "")
    return [t.strip() for t in raw.split(",") if t.strip()]


def parse_status(sections: Dict[str, str]) -> str:
    return sections.get("status", "").strip()


def parse_narrative(sections: Dict[str, str]) -> str:
    return sections.get("narrative", "").strip()


# =========================
# Validators
# =========================

def validate_validation_step(sections: Dict[str, str]) -> None:
    verdict = sections.get("verdict", "").lower()
    advance = sections.get("advance", "").lower()

    if verdict not in {"approve", "revise"}:
        raise ValueError("Verdict must be approve or revise.")

    if not (advance.startswith("y") or advance.startswith("n")):
        raise ValueError("Advance must be yes or no.")


def validate_narration_step(sections: Dict[str, str]) -> None:
    narrative = sections.get("narrative", "")

    if not narrative:
        raise ValueError("Missing Narrative section.")

    if re.search(r"\b1\)", narrative) or re.search(r"\b2\)", narrative):
        raise ValueError("Narrative contains numbered choices.")

__all__ = [
    "LLMStep",
    "parse_intent",
    "parse_focus",
    "parse_status",
    "parse_narrative",
    "validate_validation_step",
    "validate_narration_step",
]
