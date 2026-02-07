# state_store.py
# ============================================================
# 中文：
#   世界状态快照（覆盖写）存储模块：
#   - world_state.json 表示“当前状态”
#   - 支持原子覆盖写（避免写一半崩溃导致损坏）
#   - 内置 version 自增、last_event_id 更新
#
# English:
#   State snapshot (overwrite) storage:
#   - world_state.json represents the current state
#   - atomic overwrite to prevent partial corruption
#   - built-in version bump and last_event_id update
# ============================================================

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


def read_json(path: str | Path) -> Dict[str, Any]:
    """
    中文：读取 JSON；若文件不存在返回空 dict
    English: Read JSON; return {} if file doesn't exist
    """
    p = Path(path)
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("State JSON must be an object/dict.")
    return obj


def atomic_write_json(path: str | Path, obj: Dict[str, Any]) -> None:
    """
    中文：原子覆盖写 JSON
      - 写入 .tmp 文件
      - replace 到目标路径
    English: Atomic overwrite JSON
      - write to .tmp
      - replace target
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


@dataclass(frozen=True)
class StateUpdateResult:
    """
    中文：状态更新结果
    English: State update result
    """
    before: Dict[str, Any]
    after: Dict[str, Any]
    version_before: int
    version_after: int


class StateStore:
    """
    中文：
      StateStore 管理 world_state.json（覆盖写快照）。
      推荐字段：
        - version: int
        - last_event_id: str
        - player: { location, inventory, flags, ... }
        - turn/time 等
    English:
      Manages world_state.json (overwrite snapshot).
      Recommended fields:
        - version, last_event_id, player{...}, turn/time, ...
    """

    def __init__(self, state_file: str | Path) -> None:
        self.state_file = Path(state_file)

    def load(self) -> Dict[str, Any]:
        """
        中文：加载当前状态
        English: Load current state snapshot
        """
        return read_json(self.state_file)

    def save(self, state: Dict[str, Any]) -> None:
        """
        中文：覆盖写保存（不改 version）
        English: Overwrite save (does not bump version)
        """
        atomic_write_json(self.state_file, state)

    def apply_update(
        self,
        *,
        patch_fn,
        event_id: Optional[str] = None,
        bump_version: bool = True,
    ) -> StateUpdateResult:
        """
        中文：
          原子读取-更新-写入：
          - patch_fn(before_state) -> after_state
          - 可选自动 version +1
          - 可选更新 last_event_id
        English:
          Atomic read-update-write:
          - patch_fn(before_state) -> after_state
          - optionally bump version
          - optionally set last_event_id
        """
        before = self.load()

        version_before = int(before.get("version") or 0)
        version_after = version_before + 1 if bump_version else version_before

        # 中文：调用 patch_fn 生成新状态（建议返回 dict）
        # English: patch_fn produces the new state dict
        after = patch_fn(dict(before))
        if not isinstance(after, dict):
            raise ValueError("patch_fn must return a dict state.")

        if bump_version:
            after["version"] = version_after

        if event_id:
            after["last_event_id"] = event_id

        atomic_write_json(self.state_file, after)

        return StateUpdateResult(
            before=before,
            after=after,
            version_before=version_before,
            version_after=version_after,
        )
