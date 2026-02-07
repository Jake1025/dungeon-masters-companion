# test_draw_tool.py
# ============================================================
# 中文说明：
#   这是 DrawTool_BasicMCP/server.py 的 pytest 测试文件，风格对齐你们的 test_dice.py：
#   - 既测试 Domain 层（draw_random_item_logged 的“同 seed 可回放”与“去重抽空报错”）
#   - 也测试 MCP Tool 层（draw_item 的输出结构、request_id、以及 sync/async 两种分支）
#
# English:
#   Pytest suite for DrawTool_BasicMCP/server.py, aligned with your test_dice.py style:
#   - Tests Domain behavior (replay with seed, no-repeat exhaustion)
#   - Tests MCP tool handler (output schema, request_id, sync/async compatible)
# ============================================================

import inspect
import json
from pathlib import Path
import pytest

# 中文：导入 MCP tool server（注意：确保你的测试运行时 PYTHONPATH 能找到 DrawTool_BasicMCP/server.py）
# English: Import MCP tool server (ensure PYTHONPATH includes DrawTool_BasicMCP)
import server  # assumes this file is placed next to DrawTool_BasicMCP/server.py or import path is set


@pytest.fixture
def tmp_deck_files(tmp_path: Path):
    """
    中文：
      在临时目录里创建最小化 deck 源文件与历史文件，避免污染真实项目数据。
      返回一个 dict，包含 source_file 与 history_file 路径。
    English:
      Create minimal deck source & history files under tmp_path so tests don't touch real data.
      Returns dict of paths.
    """
    # ----- Source decks -----
    source = {
        "evidences": [
            {"id": "e1", "name": "Bloodstained Cloth", "rarity_weight": 10},
            {"id": "e2", "name": "Cracked Spyglass", "rarity_weight": 1},
            {"id": "e3", "name": "Salt-Stained Beads", "rarity_weight": 5},
        ],
        "characters": [
            {"id": "c1", "name": "Mara"},
            {"id": "c2", "name": "Brin"},
        ],
    }

    source_file = tmp_path / "decks.json"
    source_file.write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")

    # ----- History files -----
    history_file = tmp_path / "history.json"
    # 中文：历史文件可以不存在；函数会自动初始化。这里先不写入。
    # English: History file may not exist; draw function initializes it. We'll keep it absent.

    return {
        "source_file": source_file,
        "history_file": history_file,
        "tmp_path": tmp_path,
    }


def read_history(history_file: Path, list_key: str = "history"):
    """
    中文：读取历史文件（若不存在则返回空列表）
    English: Read history file (return empty list if missing)
    """
    if not history_file.exists():
        return []
    data = json.loads(history_file.read_text(encoding="utf-8"))
    return data.get(list_key, [])


# ============================================================
# Domain-level tests / 领域层测试（可选，但很推荐）
# ============================================================

def test_replay_same_seed_same_item(tmp_deck_files):
    """
    中文：
      同一个 source_file + 同一个 seed（且历史影响隔离） => 必须抽到同一个 item。
      为避免 history 影响，我们写入两个不同的 history 文件。
    English:
      Same source + same seed (with isolated histories) must yield identical item.
    """
    source_file = tmp_deck_files["source_file"]
    history_a = tmp_deck_files["tmp_path"] / "history_a.json"
    history_b = tmp_deck_files["tmp_path"] / "history_b.json"

    # 第一次抽取 / First draw
    out1 = server.draw_random_item_logged(
        source_file=str(source_file),
        history_file=str(history_a),
        deck_type="evidences",
        source_list_key="evidences",
        history_list_key="history",
        weight_key="rarity_weight",
        seed=999999,
    )

    # 第二次抽取（同 seed）/ Second draw (same seed)
    out2 = server.draw_random_item_logged(
        source_file=str(source_file),
        history_file=str(history_b),
        deck_type="evidences",
        source_list_key="evidences",
        history_list_key="history",
        weight_key="rarity_weight",
        seed=999999,
    )

    assert out1["seed"] == 999999 and out2["seed"] == 999999
    assert out1["item"] == out2["item"], "Replay failed: same seed should produce same item"


def test_no_repeat_exhaustion_raises(tmp_deck_files):
    """
    中文：
      开启 no_repeat 且池子里只有 2 个角色：
      抽两次成功，第三次应该报错（池子抽空）。
    English:
      With no_repeat=True and only 2 items:
      First 2 draws succeed; 3rd draw must raise ValueError (pool exhausted).
    """
    source_file = tmp_deck_files["source_file"]
    history_file = tmp_deck_files["history_file"]

    # Draw #1
    _ = server.draw_random_item_logged(
        source_file=str(source_file),
        history_file=str(history_file),
        deck_type="characters",
        source_list_key="characters",
        history_list_key="history",
        unique_key="id",
        no_repeat=True,
        seed=1,
    )

    # Draw #2
    _ = server.draw_random_item_logged(
        source_file=str(source_file),
        history_file=str(history_file),
        deck_type="characters",
        source_list_key="characters",
        history_list_key="history",
        unique_key="id",
        no_repeat=True,
        seed=2,
    )

    # Draw #3 should fail
    with pytest.raises(ValueError):
        _ = server.draw_random_item_logged(
            source_file=str(source_file),
            history_file=str(history_file),
            deck_type="characters",
            source_list_key="characters",
            history_list_key="history",
            unique_key="id",
            no_repeat=True,
            seed=3,
        )


# ============================================================
# MCP tool tests / MCP 工具层测试（同步/异步兼容）
# ============================================================

@pytest.mark.parametrize(
    "deck_type, list_key, kwargs",
    [
        # 中文：证据卡（带权重） + 固定 seed => 输出要包含该 seed
        # English: Evidence deck (weighted) + fixed seed => output must echo the seed
        ("evidences", "evidences", {"weight_key": "rarity_weight", "seed": 20260118}),

        # 中文：角色卡（去重） + 固定 seed
        # English: Character deck (no-repeat) + fixed seed
        ("characters", "characters", {"no_repeat": False, "seed": 7}),
    ],
)
def test_draw_item_tool_sync_or_async(tmp_deck_files, deck_type, list_key, kwargs):
    """
    中文：
      测试 MCP tool handler：draw_item
      - 兼容 FastMCP(同步) 和 Server(异步) 两种实现
      - 校验输出字段结构：ts/deck/seed/item/request_id
      - 校验写入 history 文件的行为（应追加一个 log_entry）
    English:
      Test MCP tool handler draw_item:
      - Works for both FastMCP (sync) and Server (async)
      - Validates output schema & request_id
      - Confirms history append behavior
    """
    source_file = tmp_deck_files["source_file"]
    history_file = tmp_deck_files["tmp_path"] / f"{deck_type}_history.json"

    # 构造 tool 输入 / Build tool input
    tool_input = server.DrawInput(
        source_file=str(source_file),
        history_file=str(history_file),
        deck_type=deck_type,
        source_list_key=list_key,
        history_list_key="history",
        unique_key="id",
        no_repeat=bool(kwargs.get("no_repeat", False)),
        weight_key=kwargs.get("weight_key"),
        seed=kwargs.get("seed"),
        timezone_str="America/New_York",
    )

    # 调用工具（可能是 sync 或 async）/ Invoke tool (sync or async)
    out = server.draw_item(tool_input)
    if inspect.iscoroutine(out):
        # 中文：pytest 默认无事件循环时，使用 asyncio.run 更稳
        # English: If coroutine, run it
        import asyncio
        out = asyncio.run(out)

    # -------- 输出结构断言 / Output schema asserts --------
    assert isinstance(out, server.DrawOutput)
    assert out.deck == deck_type
    assert isinstance(out.ts, str) and len(out.ts) > 0
    assert isinstance(out.seed, int)
    assert isinstance(out.item, dict)
    assert isinstance(out.request_id, str) and len(out.request_id) == 16

    # 如果输入指定 seed，输出必须等于该 seed
    # If seed provided, output must match it
    if kwargs.get("seed") is not None:
        assert out.seed == kwargs["seed"]

    # -------- 历史文件应追加一条记录 / History should append one entry --------
    hist = read_history(history_file, "history")
    assert len(hist) == 1
    entry = hist[0]
    assert entry["deck"] == deck_type
    assert entry["seed"] == out.seed
    assert entry["item"] == out.item


def test_draw_item_tool_no_repeat_exhaustion_in_tool(tmp_deck_files):
    """
    中文：
      用 MCP tool 的方式测试 no_repeat 抽空：
      characters 只有 2 个，连续调用 3 次，第三次应抛 ValueError。
    English:
      Tool-level exhaustion test for no_repeat:
      characters has only 2 items; 3rd call must raise ValueError.
    """
    source_file = tmp_deck_files["source_file"]
    history_file = tmp_deck_files["tmp_path"] / "characters_tool_history.json"

    def call(seed: int):
        inp = server.DrawInput(
            source_file=str(source_file),
            history_file=str(history_file),
            deck_type="characters",
            source_list_key="characters",
            history_list_key="history",
            unique_key="id",
            no_repeat=True,
            seed=seed,
        )
        out = server.draw_item(inp)
        if inspect.iscoroutine(out):
            import asyncio
            out = asyncio.run(out)
        return out

    # 前两次成功 / First two succeed
    _ = call(1)
    _ = call(2)

    # 第三次失败 / Third must fail
    with pytest.raises(ValueError):
        _ = call(3)
