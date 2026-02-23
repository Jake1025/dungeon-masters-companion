# orchestrator/world_state/tools/registry.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from ..story import GameState, StoryGraph


# -----------------------------------------------------------------------------
# Tool Function Signature
# -----------------------------------------------------------------------------
# EN: Each tool is a function that receives:
#     - args: dict parsed from LLM tool call arguments
#     - game_state: mutable game state (player location, discovered keys, etc.)
#     - story_graph: read-only story graph (nodes, connections, node types)
#     and returns a dict result.
#
# 中文：每个工具函数接收：
#     - args：LLM 工具调用传入的参数 dict
#     - game_state：可变游戏状态（玩家位置、已发现节点等）
#     - story_graph：只读故事图（节点、连接、类型）
#     并返回一个 dict 作为结果。
ToolFn = Callable[[Dict[str, Any], GameState, StoryGraph], Dict[str, Any]]


@dataclass(frozen=True)
class ToolSpec:
    """
    EN: Tool metadata object (schema + execution function).
    中文：工具的元数据（schema + 执行函数）。
    """

    name: str
    description: str
    parameters: Dict[str, Any]
    fn: ToolFn
    readonly: bool = False  # EN: readonly tools can be exposed as VALIDATE_TOOLS | 中文：只读工具可归入 VALIDATE_TOOLS


class ToolRegistry:
    """
    EN: A registry that stores all tools and can generate OpenAI/Ollama function schemas.
    中文：工具注册表，存储所有工具，并可生成函数调用 schema（供 LLM tool calling）。
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
        EN: Return tool schemas in the "function" tool format.
            If readonly_only=True, include only tools with spec.readonly=True.
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
        return out

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        game_state: GameState,
        story_graph: StoryGraph,
    ) -> dict[str, Any]:
        """
        EN: Execute a tool by name.
        中文：按名称执行工具。
        """
        spec = self._tools.get(tool_name)
        if not spec:
            return {"success": False, "reason": f"Unknown tool: {tool_name}"}
        return spec.fn(arguments, game_state, story_graph)


# EN: Global singleton registry (simple and practical for a small project).
# 中文：全局单例注册表（对小项目足够简单好用）。
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
        用法同上。
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