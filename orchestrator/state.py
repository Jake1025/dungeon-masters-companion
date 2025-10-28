from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping


def apply_commit_ops(state: Dict[str, Any], operations: Iterable[Mapping[str, Any]]) -> None:
    """Apply commit operations emitted by the Narrate stage."""
    for op in operations:
        _apply_single_op(state, op)


def _apply_single_op(state: Dict[str, Any], op: Mapping[str, Any]) -> None:
    action = op.get("op")
    path = op.get("path")
    if not action or not path:
        return
    keys = _parse_path(path)
    if not keys:
        return
    target, final_key = _walk(state, keys)
    if target is None or final_key is None:
        return
    if action == "set":
        target[final_key] = op.get("value")
    elif action == "inc":
        current = target.get(final_key, 0) if isinstance(target, dict) else 0
        inc_value = op.get("value", 0)
        try:
            target[final_key] = current + inc_value  # type: ignore[operator]
        except Exception:
            # If addition fails, fall back to assignment.
            target[final_key] = inc_value


def _parse_path(path: str) -> Iterable[str]:
    return [segment for segment in str(path).split(".") if segment]


def _walk(state: Dict[str, Any], keys: Iterable[str]) -> tuple[Dict[str, Any], str | None]:
    cursor: Dict[str, Any] = state
    path_keys = list(keys)
    if not path_keys:
        return cursor, None
    for key in path_keys[:-1]:
        if key not in cursor or not isinstance(cursor[key], dict):
            cursor[key] = {}
        cursor = cursor[key]  # type: ignore[assignment]
    final_key = path_keys[-1]
    return cursor, final_key


__all__ = ["apply_commit_ops"]
