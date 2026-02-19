# Ollama DM Orchestration Notebooks

These notebooks are portable examples inspired by the tool-calling loop architecture in this repo.

## Files

- `01_ollama_tool_loop_skeleton.ipynb`
  - Minimal iterative loop: model -> tool calls -> tool results -> repeat.
- `02_hooks_and_exit_conditions.ipynb`
  - Adds `session_start`, `pre_tool_use`, `post_tool_use`, and `stop` hook controls.
- `03_dnd_dm_world_state_engine.ipynb`
  - Engine-style, multi-turn DM with persistent world state and trace output.

## Requirements

- Python 3.10+
- `requests`
- Local Ollama server running at `http://localhost:11434`
- A model available locally (default in notebooks is `llama3.1:8b-instruct`)

## Notes

- The notebooks use Ollama's tool format with JSON schema in `tools`.
- Tool result messages are appended with:
  - `role: "tool"`
  - `tool_name: <tool name>`
  - `content: <json result string>`
- You can copy each notebook's core loop and tool registry directly into modules in your Python project.
