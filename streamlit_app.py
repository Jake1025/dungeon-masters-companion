from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from orchestrator.pipeline import Orchestrator
from orchestrator.story import STARTING_STATE


def _parse_keys(raw: str) -> List[str]:
    return [key.strip() for key in raw.split(",") if key.strip()]


def _config_signature(model: str, keys: List[str], starting_state: str) -> str:
    return f"{model}|{','.join(keys)}|{starting_state}"


def _initialize_session(model: str, keys: List[str], starting_state: str) -> None:
    orchestrator = Orchestrator(
        model=model,
        initial_keys=keys or None,
        starting_state=starting_state,
    )
    messages: List[Dict[str, str]] = []
    intro_text = starting_state
    try:
        intro = orchestrator.generate_intro()
        intro_text = intro.get("ic") or starting_state
    except Exception:
        st.warning("Intro generation failed; showing the starting state instead.")
    messages.append({"role": "assistant", "content": intro_text})

    st.session_state.orchestrator = orchestrator
    st.session_state.messages = messages
    st.session_state.last_turn = {}
    st.session_state.config_sig = _config_signature(model, keys, starting_state)


def _get_orchestrator() -> Orchestrator:
    return st.session_state.orchestrator


def main() -> None:
    st.set_page_config(page_title="Dungeon Master's Companion", layout="centered")
    st.title("Dungeon Master's Companion")
    st.caption("Describe your character's actions. The Dungeon Master responds and advances the story.")

    with st.sidebar:
        st.header("Session")
        model = st.text_input("Ollama model", value=st.session_state.get("model_input", "llama3.1:8b"), key="model_input")
        keys_raw = st.text_input(
            "Starting keys (comma-separated)",
            value=st.session_state.get("keys_input", ""),
            key="keys_input",
        )
        starting_state = st.text_area(
            "Starting state",
            value=st.session_state.get("starting_state_input", STARTING_STATE),
            height=200,
            key="starting_state_input",
        )
        start_new = st.button("Start new session")
        show_status = st.checkbox("Show story status", value=True)
        show_debug = st.checkbox("Show debug info", value=False)

    keys = _parse_keys(keys_raw)
    sig = _config_signature(model, keys, starting_state)

    if "orchestrator" not in st.session_state:
        _initialize_session(model, keys, starting_state)
    elif start_new or st.session_state.get("config_sig") != sig:
        _initialize_session(model, keys, starting_state)

    orchestrator = _get_orchestrator()
    messages: List[Dict[str, str]] = st.session_state.get("messages", [])

    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    player_input = st.chat_input("Describe what your character does...")
    if player_input:
        st.session_state.messages.append({"role": "user", "content": player_input})
        with st.chat_message("user"):
            st.markdown(player_input)
        with st.chat_message("assistant"):
            with st.spinner("The Dungeon Master is thinking..."):
                try:
                    turn = orchestrator.run_turn(player_input)
                    response = turn["narration"]["ic"]
                    st.session_state.last_turn = turn
                except Exception as exc:
                    response = "The Dungeon Master is unavailable right now."
                    st.error(f"Failed to generate a response: {exc}")
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

    if show_status:
        turn: Dict[str, Any] | None = st.session_state.get("last_turn")
        with st.expander("Story status", expanded=False):
            if turn:
                beat = turn.get("beat_state", {})
                st.markdown(
                    f"**Beat:** {beat.get('current_index', 0) + 1} "
                    f"of {len(orchestrator.beat_list)} - {beat.get('current', '')}"
                )
                st.markdown(f"**Focus:** {', '.join(turn.get('focus') or []) or 'None'}")
                st.markdown(f"**Active keys:** {', '.join(turn.get('active_keys') or []) or 'None'}")
                st.markdown(f"**Story status:** {turn.get('story_status') or 'Not set'}")
                summary = turn.get("session_summary") or ""
                if summary:
                    st.text_area("Session summary", value=summary, height=120)
            else:
                st.markdown("No turns yet. Submit an action to see story status.")

    if show_debug:
        debug_data = st.session_state.get("last_turn", {}).get("llm_debug")
        with st.expander("Debug", expanded=False):
            if debug_data:
                for step, payload in debug_data.items():
                    st.markdown(f"**{step}**")
                    st.text_area(f"{step} prompt", value=payload.get("prompt", ""), height=120)
                    st.text_area(f"{step} raw", value=payload.get("raw", ""), height=120)
            else:
                st.markdown("No debug info available yet.")


if __name__ == "__main__":
    main()
