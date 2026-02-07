# DrawTool_BasicMCP/server.py
# ============================================================
# 中文说明：
#   将你开发的 draw_random_item_logged 抽卡函数封装成 MCP Tool。
#   结构对齐 DiceTool：Domain 函数保持纯逻辑，MCP 层负责输入/输出与工具暴露。
#
# English:
#   Wrap your draw_random_item_logged function as an MCP tool.
#   Mirrors DiceTool architecture: Domain function stays pure, MCP layer exposes the tool.
# ============================================================

import secrets
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

try:
    # 中文：官方 FastMCP（高层封装，写起来更简洁）
    # English: Official FastMCP helper (high-level, ergonomic)
    from mcp.server.fastmcp import FastMCP
    fastmcp_available = True
except Exception:
    # 中文：如果 FastMCP 不可用，退回到低层 Server API（逻辑一样，只是写法更啰嗦）
    # English: Fallback to low-level Server API if FastMCP is unavailable
    fastmcp_available = False
    from mcp.server import Server

# ============================================================
# Domain Layer / 领域层（你自己写的抽卡逻辑）
# ============================================================
# 中文：保持 draw.py 里的函数不变，这里只负责调用它。
# English: Keep your draw.py function unchanged; this layer just invokes it.
from draw import draw_random_item_logged


# ============================================================
# MCP Layer / 工具层（定义工具输入输出模型）
# ============================================================

class DrawInput(BaseModel):
    # 中文：源 JSON 文件路径（卡池）
    # English: Path to source JSON pool file
    source_file: str = Field(description="Path to source JSON pool file")

    # 中文：历史记录 JSON 文件路径（用于写入抽取日志）
    # English: Path to history JSON log file (persist draw logs)
    history_file: str = Field(description="Path to history JSON log file")

    # 中文：卡组类型名字（skills/characters/evidences 等）
    # English: Deck name/type (skills/characters/evidences/etc.)
    deck_type: str = Field(description="Deck name (skills/characters/evidences/...)")

    # 中文：源 JSON 中列表字段的 key（如 'skills' / 'characters' / 'evidences'）
    # English: Key of the list in source JSON (e.g., 'skills', 'characters')
    source_list_key: str = Field(description="Key of list in source JSON (e.g., 'skills')")

    # 中文：历史 JSON 中列表字段的 key（默认 history）
    # English: Key of list in history JSON (default: 'history')
    history_list_key: str = Field(
        default="history",
        description="Key of list in history JSON (default: 'history')"
    )

    # 中文：去重时用于唯一标识的字段（如 'id' 或 'name'）
    # English: Unique field for no-repeat filtering (e.g., 'id' or 'name')
    unique_key: Optional[str] = Field(
        default=None,
        description="Unique field for no-repeat (e.g., 'id' or 'name')"
    )

    # 中文：是否启用去重抽取（需要 unique_key）
    # English: Whether to prevent repeats (requires unique_key)
    no_repeat: bool = Field(
        default=False,
        description="Prevent drawing previously drawn items (requires unique_key)"
    )

    # 中文：权重字段名（如 'rarity_weight'），用于加权抽取；不传则均匀随机
    # English: Weight field name for weighted draw; if None, use uniform random
    weight_key: Optional[str] = Field(
        default=None,
        description="Weight field (e.g., 'rarity_weight'); if None, uniform random"
    )

    # 中文：可回放 seed；如果不传，server 会生成 seed 并写入日志
    # English: Replay seed; if None, server generates one and logs it
    seed: Optional[int] = Field(
        default=None,
        description="Replay seed; if None, server generates one"
    )

    # 中文：写入日志的时区（默认纽约）
    # English: Timezone for timestamp (default: New York)
    timezone_str: str = Field(
        default="America/New_York",
        description="Timezone for timestamp (default: America/New_York)"
    )


class DrawOutput(BaseModel):
    # 中文：抽卡时间戳（ISO8601，含时区）
    # English: Timestamp of draw (ISO8601 with TZ)
    ts: str

    # 中文：卡组类型
    # English: Deck type/name
    deck: str

    # 中文：用于回放的 seed（决定结果的关键）
    # English: Replay seed (the key for deterministic replay)
    seed: int

    # 中文：抽到的条目（原始 dict）
    # English: The drawn item (original dict)
    item: Dict[str, Any]

    # 中文：请求 ID（便于日志关联/调试）
    # English: Request ID (useful for tracing/debugging)
    request_id: str


# ============================================================
# Tool Registration / 工具注册
# ============================================================

if fastmcp_available:
    # 中文：FastMCP 写法（同步函数）
    # English: FastMCP style (sync handler)
    mcp = FastMCP("dm-draw")

    @mcp.tool()
    def draw_item(input: DrawInput) -> DrawOutput:
        """
        中文：抽取一个条目并写入历史记录文件。
        English: Draw one item and append a log entry to the history file.
        """
        log_entry = draw_random_item_logged(
            source_file=input.source_file,
            history_file=input.history_file,
            deck_type=input.deck_type,
            source_list_key=input.source_list_key,
            history_list_key=input.history_list_key,
            unique_key=input.unique_key,
            no_repeat=input.no_repeat,
            weight_key=input.weight_key,
            seed=input.seed,
            timezone_str=input.timezone_str,
        )

        return DrawOutput(
            ts=log_entry["ts"],
            deck=log_entry["deck"],
            seed=log_entry["seed"],
            item=log_entry["item"],
            request_id=secrets.token_hex(8),
        )

else:
    # 中文：低层 Server 写法（异步函数）
    # English: Low-level Server style (async handler)
    mcp = Server("dm-draw")

    @mcp.tool("draw_item", input_model=DrawInput, output_model=DrawOutput)
    async def draw_item(input: DrawInput) -> DrawOutput:  # type: ignore
        """
        中文：抽取一个条目并写入历史记录文件（低层 Server 版本）。
        English: Draw one item and append a log entry (low-level Server version).
        """
        log_entry = draw_random_item_logged(
            source_file=input.source_file,
            history_file=input.history_file,
            deck_type=input.deck_type,
            source_list_key=input.source_list_key,
            history_list_key=input.history_list_key,
            unique_key=input.unique_key,
            no_repeat=input.no_repeat,
            weight_key=input.weight_key,
            seed=input.seed,
            timezone_str=input.timezone_str,
        )

        return DrawOutput(
            ts=log_entry["ts"],
            deck=log_entry["deck"],
            seed=log_entry["seed"],
            item=log_entry["item"],
            request_id=secrets.token_hex(8),
        )


# ============================================================
# Entrypoint / 启动入口
# ============================================================

if __name__ == "__main__":
    # 中文：默认使用 stdio 运行（适配 Claude Desktop / MCP Inspector）
    # English: Run over stdio by default (Claude Desktop / MCP Inspector)
    # e.g. python server.py | npx @modelcontextprotocol/inspector
    mcp.run()
