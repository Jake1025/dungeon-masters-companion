#!/usr/bin/env python3
"""
Export story.py DEFAULT_NODES + constants into JSON files.

中文说明：
- 你们小组现在的 story.py 已经引入 NodeType / tags / GameState。
- 本脚本会“读取你们现有 story.py 的 DEFAULT_NODES / DEFAULT_START_KEYS / STARTING_STATE / BEAT_LIST”，
  然后输出到 orchestrator/world_state/data/ 下的一组 JSON。
- 这样 story.py 就可以删掉巨大 DEFAULT_NODES，改为从 JSON 加载（更易维护）。

EN:
- This script imports your current story.py (the latest committed version),
  then exports nodes + edges + config constants into JSON files under world_state/data/.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from zoneinfo import ZoneInfo
import sys


def load_module_from_path(module_path: Path):
    spec = importlib.util.spec_from_file_location("story_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module: {module_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--story-py", required=True, help="Path to orchestrator/world_state/story.py")
    ap.add_argument("--out-dir", required=True, help="Output directory, e.g. orchestrator/world_state/data")
    ap.add_argument("--tz", default="America/New_York", help="Timezone for created_ts")
    args = ap.parse_args()

    story_py = Path(args.story_py).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    mod = load_module_from_path(story_py)

    # ---- pull symbols
    DEFAULT_NODES = getattr(mod, "DEFAULT_NODES")
    DEFAULT_START_KEYS = getattr(mod, "DEFAULT_START_KEYS")
    STARTING_STATE = getattr(mod, "STARTING_STATE")
    BEAT_LIST = getattr(mod, "BEAT_LIST")
    NodeType = getattr(mod, "NodeType")

    created_ts = datetime.now(tz=ZoneInfo(args.tz)).isoformat()

    # ---- nodes + descriptions
    # Schema:
    #   nodes.json: id -> {name, node_type, tags, desc_en, desc_zh}
    # NOTE: If your descriptions are only EN in code, desc_zh will be "".
    nodes_out: Dict[str, Dict[str, Any]] = {}
    index_out: Dict[str, Dict[str, str]] = {}

    # simple ID allocators per type
    counters = {"location": 0, "npc": 0, "item": 0, "clue": 0}

    def alloc_id(t: str) -> str:
        if t == "location":
            counters[t] += 1
            return f"L{counters[t]:03d}"
        if t == "npc":
            counters[t] += 1
            return f"P{counters[t]:03d}"
        # item / clue both under I-prefix to match earlier convention
        counters[t] += 1
        return f"I{counters[t]:03d}"

    # ---- build mapping name->id
    name_to_id: Dict[str, str] = {}

    for n in DEFAULT_NODES:
        name = getattr(n, "key")
        nt = getattr(n, "node_type").value if getattr(n, "node_type") else "item"
        # normalize: npc in enum value might be "npc"
        node_id = alloc_id(nt)
        name_to_id[name] = node_id

    # ---- export node payloads
    for n in DEFAULT_NODES:
        name = getattr(n, "key")
        node_id = name_to_id[name]
        desc = getattr(n, "description", "")
        nt = getattr(n, "node_type").value if getattr(n, "node_type") else "item"
        tags = list(getattr(n, "tags", ()) or ())

        # If you later maintain bilingual desc in code, split here.
        nodes_out[node_id] = {
            "name": name,
            "source_key": name,
            "node_type": nt,  # location/npc/item/clue
            "tags": tags,
            "desc_en": desc,  # as-is
            "desc_zh": "",    # fill later if needed
        }
        index_out[name] = {"id": node_id, "type": nt}

    # ---- edges (name->name in code) -> (id->id in JSON)
    edges_out: Dict[str, list[str]] = {}
    for n in DEFAULT_NODES:
        from_name = getattr(n, "key")
        from_id = name_to_id[from_name]
        conns = list(getattr(n, "connections", ()) or ())
        edges_out[from_id] = [name_to_id[c] for c in conns if c in name_to_id]

    graph_out = {
        "version": 2,
        "meta": {"created_ts": created_ts, "notes": "Full graph exported from story.py DEFAULT_NODES."},
        "nodes": {nid: {"name": p["name"], "source_key": p["source_key"], "node_type": p["node_type"]} for nid, p in nodes_out.items()},
        "edges": edges_out,
    }

    # ---- config
    start_keys_out = {
        "version": 2,
        "meta": {"created_ts": created_ts, "notes": "Exported DEFAULT_START_KEYS."},
        "default_start_keys": list(DEFAULT_START_KEYS),
    }
    starting_state_out = {
        "version": 2,
        "meta": {"created_ts": created_ts, "notes": "Exported STARTING_STATE (EN only unless you add ZH)."},
        "starting_state_en": str(STARTING_STATE),
        "starting_state_zh": "",
    }
    beats_out = {
        "version": 2,
        "meta": {"created_ts": created_ts, "notes": "Exported BEAT_LIST (EN only unless you add ZH)."},
        "beats": [{"id": f"B{i:02d}", "text_en": b, "text_zh": ""} for i, b in enumerate(BEAT_LIST, start=1)],
    }

    # ---- write files
    (out_dir / "nodes_v2.json").write_text(json.dumps(nodes_out, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "graph_full_v2.json").write_text(json.dumps(graph_out, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "story_index_v2.json").write_text(json.dumps(index_out, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "default_start_keys_v2.json").write_text(json.dumps(start_keys_out, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "starting_state_v2.json").write_text(json.dumps(starting_state_out, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "beat_list_v2.json").write_text(json.dumps(beats_out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Wrote:")
    for fn in ["nodes_v2.json","graph_full_v2.json","story_index_v2.json","default_start_keys_v2.json","starting_state_v2.json","beat_list_v2.json"]:
        print(" -", out_dir / fn)


if __name__ == "__main__":
    main()
