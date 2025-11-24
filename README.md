# dungeon-masters-companion
The Dungeon Masters Companion is a proposed structure for creating a MCP-powered AI DM system for TTRPGs.

## Quickstart
- Default demo (built-in tavern nodes): `python -m orchestrator.cli`
- Load a Postgres-backed campaign: `python -m orchestrator.cli --campaign-key copper-cup --pg-dsn postgresql://postgres:postgres@localhost:5432/dmai --start-key "Copper Cup"`
- Add `--verbose` to see planner/validator prompts, and `--starting-state` if you want to override the default opening.
