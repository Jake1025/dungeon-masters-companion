# orchestrator/world_state/tools/registry.py
from __future__ import annotations

"""
EN:
  Tool registry:
    - Provides a global singleton REGISTRY
    - Provides @tool decorator to register functions
    - Generates tool schema lists for LLM function calling
    - Executes tools by name

中文：
  工具注册表：
    - 提供全局单例 REGISTRY
    - 提供 @tool 装饰器注册工具函数
    - 生成 LLM function calling 所需的 schema 列表
    - 按名称执行工具
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

# -----------------------------------------------------------------------------
# EN: IMPORTANT: Avoid importing ..story at runtime to prevent circular imports.
# 中文：重要：运行时避免导入 ..story，防止循环导入导致 REGISTRY 初始化失败。
# -----------------------------------------------------------------------------
if TYPE_CHECKING:
    from ..story import GameState, StoryGraph


# -----------------------------------------------------------------------------
# Tool Function Signature / 工具函数签名
# -----------------------------------------------------------------------------
# EN:
#   Each tool function receives:
#     - args: tool call arguments (dict OR other types if you want compatibility)
#     - game_state: mutable game state
#     - story_graph: read-only story graph
#   and returns a dict result.
#
# 中文：
#   每个工具函数接收：
#     - args：工具调用参数（可为 dict 或其他类型，用于兼容旧调用）
#     - game_state：可变游戏状态
#     - story_graph：只读故事图
#   并返回 dict 结果。
ToolFn = Callable[[Any, "GameState", "StoryGraph"], Dict[str, Any]]


@dataclass(frozen=True)
class ToolSpec:
    """
    EN: Tool metadata (schema + execution function).
    中文：工具元信息（schema + 执行函数）。
    """

    name: str
    description: str
    parameters: Dict[str, Any]
    fn: ToolFn
    readonly: bool = False  # EN: for VALIDATE_TOOLS | 中文：是否只读（用于 VALIDATE_TOOLS）


class ToolRegistry:
    """
    EN: Stores all tools and generates tool schemas.
    中文：存储所有工具并生成 tool schemas。
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        """
        EN: Register a tool spec. Tool names must be unique.
        中文：注册工具定义。工具名必须唯一。
        """
        if spec.name in self._tools:
            raise ValueError(f"Duplicate tool name: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> Optional[ToolSpec]:
        """
        EN: Get tool spec by name.
        中文：按名称获取工具定义。
        """
        return self._tools.get(name)

    def schema_list(self, *, readonly_only: bool = False) -> list[dict[str, Any]]:
        """
        EN: Return tool schemas in "function tool" format.
            If readonly_only=True, include only readonly tools.
        中文：以 function tool 格式返回 schema。
            readonly_only=True 时，仅返回只读工具。
        """
        out: list[dict[str, Any]] = []
        for spec in self._tools.values():
            if readonly_only and not spec.readonly:
                continue
            out.append(
                {
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": spec.parameters,
                    },
                }
            )

        # EN: Deterministic ordering makes debugging/diffs easier.
        # 中文：固定排序便于 debug/diff。
        out.sort(key=lambda x: x["function"]["name"])
        return out

    def execute(
        self,
        tool_name: str,
        arguments: Any,
        game_state: "GameState",
        story_graph: "StoryGraph",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        EN:
          Execute a tool by name.
          - arguments: accept Any to support legacy calls (e.g. str for movement).
          - **kwargs: reserved for future use (event_id, log paths, etc.).
        中文：
          按名称执行工具。
          - arguments：允许 Any，用于兼容旧调用（如 move_to_location 直接传 str）。
          - **kwargs：预留扩展（event_id、log 路径等）。
        """
        spec = self._tools.get(tool_name)
        if not spec:
            return {"success": False, "reason": f"Unknown tool: {tool_name}"}
        return spec.fn(arguments, game_state, story_graph, **kwargs)  # type: ignore[misc]


# -----------------------------------------------------------------------------
# EN: Global singleton registry (must exist for tools/__init__.py import).
# 中文：全局单例注册表（必须存在，供 tools/__init__.py 导入）。
# -----------------------------------------------------------------------------
REGISTRY = ToolRegistry()


def tool(
    *,
    name: str,
    description: str,
    parameters: Dict[str, Any],
    readonly: bool = False,
):
    """
    EN: Decorator to register a function as a tool.
        Usage:
            @tool(name="...", description="...", parameters={...}, readonly=True/False)
            def my_tool(args, game_state, story_graph) -> dict: ...
    中文：将函数注册为工具的装饰器。
    """

    def deco(fn: ToolFn) -> ToolFn:
        REGISTRY.register(
            ToolSpec(
                name=name,
                description=description,
                parameters=parameters,
                fn=fn,
                readonly=readonly,
            )
        )
        return fn

    return deco


__all__ = ["ToolRegistry", "ToolSpec", "REGISTRY", "tool"]