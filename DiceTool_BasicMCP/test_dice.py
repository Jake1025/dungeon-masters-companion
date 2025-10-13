import asyncio
import inspect
import importlib
import json
import secrets
import types
import pytest
import server



@pytest.fixture
def set_randbelow(monkeypatch): # Let's you set deterministic rand for consistent tests.
 
    # Patch secrets.randbelow with a sequence of predetermined integers.
    # Values must already be in [0, sides-1] for the call's sides.

    def _set(values):
        it = iter(values)
        def fake_randbelow(sides: int) -> int:
            try:
                v = next(it)
            except StopIteration:
                raise AssertionError("Not enough mocked random values for this test.")
            if not (0 <= v < sides):
                raise AssertionError(f"Mock value {v} out of range for sides={sides}")
            return v
        monkeypatch.setattr(secrets, "randbelow", fake_randbelow)
    return _set


# Unit tests for the Dice_Roller. 

def test_core_policy_sum_and_modifier(set_randbelow):
    # 2d6+3 with rolls 4 and 5  -> we feed 3 and 4 because randbelow(6) + 1
    set_randbelow([3, 4])  # -> rolls are 4, 5
    result = server.engine.run("2d6+3", "core.v1")
    assert result["total"] == 4 + 5 + 3
    br = result["breakdown"]
    assert br["rolls"] == [4, 5]
    assert br["modifier"] == 3
    assert br.get("kept") is None and br.get("dropped") is None

def test_invalid_formula_raises():
    with pytest.raises(ValueError):
        server.engine.run("d20+5")  # missing count

def test_advantage_policy_keeps_highest(set_randbelow):
    # For advantage on 1d20+7, produce 2 and 19  -> feed 1 and 18
    set_randbelow([1, 18])
    result = server.engine.run("1d20+7", "advantage.v1")
    assert result["total"] == 19 + 7
    br = result["breakdown"]
    assert sorted(br["rolls"]) == [2, 19]
    assert br["kept"] == [19]
    assert br["dropped"] == [2]
    assert "advantage" in br["notes"]

def test_disadvantage_policy_keeps_lowest(set_randbelow):
    # For disadvantage on 1d20+2, produce 17 and 4  -> feed 16 and 3
    set_randbelow([16, 3])
    result = server.engine.run("1d20+2", "disadvantage.v1")
    assert result["total"] == 4 + 2
    br = result["breakdown"]
    assert sorted(br["rolls"]) == [4, 17]
    assert br["kept"] == [4]
    assert br["dropped"] == [17]
    assert "disadvantage" in br["notes"]

def test_advantage_policy_fallback_on_non_d20(set_randbelow):
    # Advantage policy but 2d6+3 -> should behave like core (sum all dice)
    set_randbelow([0, 5])  # -> rolls 1 and 6
    result = server.engine.run("2d6+3", "advantage.v1")
    assert result["total"] == 1 + 6 + 3
    br = result["breakdown"]
    assert br["rolls"] == [1, 6]
    assert br.get("kept") is None and br.get("dropped") is None

def test_policy_aliases_adv_and_dis(set_randbelow):
    set_randbelow([10, 12])  # -> 11 and 13
    r1 = server.engine.run("1d20+0", "adv")
    assert r1["breakdown"]["kept"] == [13]
    set_randbelow([10, 12])  # reset for next call
    r2 = server.engine.run("1d20+0", "dis")
    assert r2["breakdown"]["kept"] == [11]


# MCP tool handler test
@pytest.mark.parametrize("policy, seq, expected_total", [
    ("core.v1", [9], 10),              # 1d20+0 -> roll 10
    ("advantage.v1", [1, 18], 26),     # keep 19 + 7
    ("disadvantage.v1", [16, 3], 6),   # keep 4 + 2
])
def test_roll_dice_tool_sync_or_async(set_randbelow, policy, seq, expected_total):
    
    # Calls the exported roll_dice tool. 
    # Works for both FastMCP (sync) and Server (async) branches.
    
    # Map expected inputs per test
    if policy == "core.v1":
        roll_input = server.RollInput(formula="1d20+0", policy=policy)
    elif policy == "advantage.v1":
        roll_input = server.RollInput(formula="1d20+7", policy=policy)
    else:
        roll_input = server.RollInput(formula="1d20+2", policy=policy)

    set_randbelow(seq)

    # Invoke tool (could be sync function or async coroutine)
    out = server.roll_dice(roll_input)
    if inspect.iscoroutine(out):
        out = asyncio.get_event_loop().run_until_complete(out)

    assert isinstance(out, server.RollOutput)
    assert out.total == expected_total
    assert out.policy == policy
    assert isinstance(out.breakdown, dict)
    assert isinstance(out.request_id, str) and len(out.request_id) == 16  
