# pyproject.toml deps (pick one SDK style)
# mcp>=1.7  OR  fastmcp>=2.0
# uvicorn fastapi pydantic>=2 psycopg[binary] (if/when you add HTTP & DB)

import secrets
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

try:
    # High-level helper (nice ergonomics)
    from mcp.server.fastmcp import FastMCP  # official SDK "FastMCP" helper
    fastmcp_available = True
except Exception:
    fastmcp_available = False
    from mcp.server import Server  # official low-level server if needed

# ---------- Domain layer (Open Architecture OOP dice engine) ----------

class RollDetail(BaseModel):
    count: int
    sides: int
    modifier: int
    rolls: List[int]
    kept: Optional[List[int]] = None
    dropped: Optional[List[int]] = None
    notes: Optional[str] = None

class DicePolicy:
    """Base policy: override .roll for variants (advantage, disadvantage, exploding, etc.)."""
    id = "core.v1"
    def roll(self, count: int, sides: int, modifier: int = 0) -> Dict:
        rolls = [secrets.randbelow(sides) + 1 for _ in range(count)]
        total = sum(rolls) + modifier
        detail = RollDetail(
            count=count, sides=sides, modifier=modifier, rolls=rolls
        )
        return {"total": total, "breakdown": detail.model_dump()}

class CorePolicy(DicePolicy):
    id = "core.v1"

class AdvantagePolicy(DicePolicy):
    """5e-style advantage: intended for d20 checks/attacks. If not 1d20, falls back to core semantics."""
    id = "advantage.v1"
    def roll(self, count: int, sides: int, modifier: int = 0) -> Dict:
        # Advantage is defined for a single d20 check; keep graceful fallback.
        if count == 1 and sides == 20:
            a = secrets.randbelow(20) + 1
            b = secrets.randbelow(20) + 1
            kept_val = max(a, b)
            total = kept_val + modifier
            detail = RollDetail(
                count=2, sides=20, modifier=modifier,
                rolls=[a, b], kept=[kept_val],
                dropped=[min(a, b)], notes="advantage: kept highest"
            )
            return {"total": total, "breakdown": detail.model_dump()}
        # Fallback: behave like core (sum all dice)
        return super().roll(count, sides, modifier)

class DisadvantagePolicy(DicePolicy):
    """5e-style disadvantage: intended for d20 checks/attacks."""
    id = "disadvantage.v1"
    def roll(self, count: int, sides: int, modifier: int = 0) -> Dict:
        if count == 1 and sides == 20:
            a = secrets.randbelow(20) + 1
            b = secrets.randbelow(20) + 1
            kept_val = min(a, b)
            total = kept_val + modifier
            detail = RollDetail(
                count=2, sides=20, modifier=modifier,
                rolls=[a, b], kept=[kept_val],
                dropped=[max(a, b)], notes="disadvantage: kept lowest"
            )
            return {"total": total, "breakdown": detail.model_dump()}
        return super().roll(count, sides, modifier)

class DiceEngine:
    def __init__(self):
        # We can add policies here; (exploding, keep-highest-N, fate, house rules, etc.)
        self.policies = {
            CorePolicy.id: CorePolicy(),
            AdvantagePolicy.id: AdvantagePolicy(),
            DisadvantagePolicy.id: DisadvantagePolicy(),
            # aliases are handy if you want shorter names:
            "adv": AdvantagePolicy(),
            "dis": DisadvantagePolicy(),
        }

    def run(self, formula: str, policy: str = "core.v1"):
        """
        Very small parser: "XdY+Z" or "XdY-Z".
        Advantage/disadvantage are selected via policy ("advantage.v1"/"disadvantage.v1").
        """
        import re
        m = re.fullmatch(r"(\d+)d(\d+)([+-]\d+)?", formula, re.I)
        if not m:
            raise ValueError(f"Unsupported formula: {formula}")
        c, s = int(m[1]), int(m[2])
        mod = int(m[3]) if m[3] else 0
        policy_impl = self.policies.get(policy, self.policies["core.v1"])
        return policy_impl.roll(c, s, mod)

engine = DiceEngine()

# ---------- MCP layer (tools) ----------

class RollInput(BaseModel):
    formula: str = Field(description="Dice like '2d20+7' or '1d8+3'")
    policy: str = Field(default="core.v1", description="House rule policy id (e.g., 'core.v1', 'advantage.v1', 'disadvantage.v1')")

class RollOutput(BaseModel):
    total: int
    breakdown: Dict
    policy: str
    request_id: str

if fastmcp_available:
    mcp = FastMCP("dm-dice")
    @mcp.tool()
    def roll_dice(input: RollInput) -> RollOutput:
        result = engine.run(input.formula, input.policy)
        return RollOutput(
            total=result["total"],
            breakdown=result["breakdown"],
            policy=input.policy,
            request_id=secrets.token_hex(8),
        )
else:
    # Fallback to lower-level server (same behavior, more boilerplate)
    from mcp.types import Tool, CallToolResult
    mcp = Server("dm-dice")
    @mcp.tool("roll_dice", input_model=RollInput, output_model=RollOutput)
    async def roll_dice(input: RollInput) -> RollOutput:  # type: ignore
        result = engine.run(input.formula, input.policy)
        return RollOutput(
            total=result["total"],
            breakdown=result["breakdown"],
            policy=input.policy,
            request_id=secrets.token_hex(8),
        )

if __name__ == "__main__":
    # Run via stdio for Claude Desktop / MCP Inspector, or expose SSE/HTTP later.
    # e.g. python server.py | npx @modelcontextprotocol/inspector
    mcp.run()  # the SDK handles stdio wiring
