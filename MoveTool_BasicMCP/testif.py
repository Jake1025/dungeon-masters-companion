import server, json
from pathlib import Path

# 确保默认 state 有起点
Path("state").mkdir(exist_ok=True)
Path("logs").mkdir(exist_ok=True)
Path("state/world_state.json").write_text(json.dumps({"version":0,"player":{"location":"L010"}},ensure_ascii=False,indent=2),encoding="utf-8")

out = server.move(server.MoveInput(
    persist=True,
    to_id="L022",
))
print(out)
