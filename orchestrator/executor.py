from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Mapping, Optional

from .schemas import GatherOutput, GatherResults, ToolExecution


class BudgetError(RuntimeError):
    """Raised when executing a tool would exceed its configured budget."""


class BudgetManager:
    def __init__(self, limits: Optional[Mapping[str, int]] = None) -> None:
        self.limits = dict(limits or {})
        self.usage: Dict[str, int] = {key: 0 for key in self.limits}

    def consume(self, tool: str, cost: int = 1) -> None:
        if cost <= 0:
            return
        limit = self.limits.get(tool)
        if limit is None:
            return
        used = self.usage.get(tool, 0)
        if used + cost > limit:
            raise BudgetError(f"Budget exceeded for tool '{tool}' ({used + cost}/{limit})")
        self.usage[tool] = used + cost


class Executor:
    """Runs the gathered tool requests through registered MCP handlers."""

    def __init__(
        self,
        tools: Mapping[str, Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]],
        *,
        budgets: Optional[Mapping[str, int]] = None,
        verbose: bool = False,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.tools = dict(tools)
        self.budget_manager = BudgetManager(budgets)
        self.verbose = verbose
        self.logger = logger or logging.getLogger(__name__)

    def execute(
        self,
        gather_output: GatherOutput,
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> GatherResults:
        executions = []
        context_payload = context or {}
        for call in gather_output.tool_calls:
            handler = self.tools.get(call.tool)
            if self.verbose:
                self.logger.debug(
                    "Executing tool %s with args:\n%s",
                    call.tool,
                    json.dumps(call.arguments, indent=2),
                )
            try:
                self.budget_manager.consume(call.tool, _extract_cost(call.budget))
            except BudgetError as exc:
                executions.append(
                    ToolExecution(
                        tool=call.tool,
                        arguments=call.arguments,
                        status="rejected",
                        error=str(exc),
                        justification=call.justification,
                    )
                )
                continue
            if handler is None:
                executions.append(
                    ToolExecution(
                        tool=call.tool,
                        arguments=call.arguments,
                        status="error",
                        error=f"unknown tool '{call.tool}'",
                        justification=call.justification,
                    )
                )
                if self.verbose:
                    self.logger.debug("Tool %s failed: unknown tool", call.tool)
                continue
            try:
                result = handler(call.arguments, context_payload)
                payload = result if isinstance(result, dict) else {"value": result}
                executions.append(
                    ToolExecution(
                        tool=call.tool,
                        arguments=call.arguments,
                        status="ok",
                        result=payload,
                        justification=call.justification,
                    )
                )
                if self.verbose:
                    self.logger.debug(
                        "Tool %s result:\n%s",
                        call.tool,
                        json.dumps(payload, indent=2),
                    )
            except Exception as exc:  # noqa: BLE001 - surface tool failure details
                executions.append(
                    ToolExecution(
                        tool=call.tool,
                        arguments=call.arguments,
                        status="error",
                        error=str(exc),
                        justification=call.justification,
                    )
                )
                if self.verbose:
                    self.logger.debug("Tool %s raised error: %s", call.tool, exc)
        return GatherResults(executions=executions, notes=gather_output.notes)


def _extract_cost(budget: Optional[Dict[str, Any]]) -> int:
    if not budget:
        return 1
    cost = budget.get("cost", 1)
    try:
        value = int(cost)
    except Exception:
        value = 1
    return max(1, value)


__all__ = ["Executor", "BudgetError"]
