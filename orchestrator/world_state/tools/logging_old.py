# orchestrator/world_state/tools/logging.py
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from ..story import GameState


def default_tool_log_path() -> Path:
    """
    EN: Compute a default log file path under orchestrator/world_state/state_logs/.
    中文：默认日志路径：orchestrator/world_state/state_logs/ 下创建一个时间戳文件。
    """
    # .../orchestrator/world_state/tools/logging.py -> parent.parent = world_state
    root = Path(__file__).resolve().parent.parent
    d = root / "state_logs"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"tool_calls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"


class ToolCallLogger:
    """
    EN: Append-only JSON logger for tool executions.
        It writes a JSON array to a single file and appends entries.
        Logging failures must NOT break gameplay.
    中文：工具调用 JSON 追加日志。
        一个文件保存一个 JSON 数组，逐条追加。
        记录失败不应影响游戏流程。
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_tool_log_path()

    def append(
        self,
        *,
        tool: str,
        args: Dict[str, Any],
        result: Dict[str, Any],
        game_state: GameState,
        before_location: str,
    ) -> None:
        """
        EN: Append one tool-call entry.
        中文：追加一条工具调用记录。
        """
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "tool": tool,
            "args": args,
            "result": result,
            "player_location_before": before_location,
            "player_location_after": game_state.player_location,
        }

        try:
            data = []
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(data, list):
                    # EN: If corrupted, reset to list | 中文：若文件损坏则重置为 list
                    data = []
            data.append(entry)
            self.path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            # EN: Never crash gameplay due to logging | 中文：绝不因日志而中断游戏
            pass