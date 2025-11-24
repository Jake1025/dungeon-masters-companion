import json
from pathlib import Path

import streamlit as st


def load_snapshot(path: Path) -> dict:
    if not path.exists():
        st.warning(f"Snapshot file not found: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        st.error(f"Failed to read snapshot: {exc}")
        return {}


def build_dot(snapshot: dict) -> str:
    nodes = snapshot.get("nodes") or []
    edges = snapshot.get("edges") or []
    lines = ["digraph Story {", "rankdir=LR;"]
    for node in nodes:
        key = node.get("key", "")
        flags = node.get("flags") or {}
        attrs = []
        if flags.get("focus"):
            attrs.append('color="red"')
            attrs.append('style="filled"')
            attrs.append('fillcolor="mistyrose"')
        elif flags.get("active"):
            attrs.append('color="blue"')
            attrs.append('style="filled"')
            attrs.append('fillcolor="aliceblue"')
        elif flags.get("discovered"):
            attrs.append('color="gray"')
        label = key.replace('"', '\\"')
        attr_text = ", ".join(attrs)
        if attr_text:
            lines.append(f'  "{label}" [{attr_text}];')
        else:
            lines.append(f'  "{label}";')
    for edge in edges:
        src = edge.get("src", "")
        dst = edge.get("dst", "")
        src_label = src.replace('"', '\\"')
        dst_label = dst.replace('"', '\\"')
        lines.append(f'  "{src_label}" -> "{dst_label}";')
    lines.append("}")
    return "\n".join(lines)


def main() -> None:
    st.set_page_config(page_title="DMAI Graph Viewer", layout="wide")

    st.title("Session State Viewer")
    path_str = st.text_input("Snapshot path", "state_snapshot.json")
    st.button("Refresh")

    snapshot = load_snapshot(Path(path_str))
    if not snapshot:
        st.stop()

    cols = st.columns(3)
    beat = snapshot.get("beat_state") or {}
    with cols[0]:
        st.subheader("Beat")
        st.write(
            f"{beat.get('current_index',0)+1}: {beat.get('current','')} "
            f"(next: {beat.get('next','') or '—'})"
        )
        st.subheader("Focus")
        st.write(", ".join(snapshot.get("focus") or []) or "None")
    with cols[1]:
        st.subheader("Active Keys")
        st.write(", ".join(snapshot.get("active_keys") or []) or "None")
    with cols[2]:
        st.subheader("Discovered Keys")
        st.write(", ".join(snapshot.get("discovered_keys") or []) or "None")

    st.subheader("Session Summary")
    st.text(snapshot.get("session_summary") or "No summary yet.")

    st.subheader("History")
    for turn in snapshot.get("history") or []:
        st.markdown(f"**{turn.get('role','').title()}:** {turn.get('content','')}")

    st.subheader("Graph")
    dot = build_dot(snapshot)
    st.graphviz_chart(dot, use_container_width=True)


if __name__ == "__main__":
    main()
