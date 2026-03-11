# streamlit_app.py — TapTap POD Analytics Chatbot Frontend

import os
import requests
import pandas as pd
import streamlit as st

API_BASE = os.getenv("TAPTAP_API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="TapTap POD Analytics",
    page_icon="🧩",
    layout="wide",
)


# ── Chart helper ──────────────────────────────────────────────────────────────

def _render_chart(df: pd.DataFrame, intent: str) -> None:
    try:
        if intent == "pod_difficulty_breakdown" and "difficulty" in df.columns:
            st.bar_chart(df.set_index("difficulty")["students_attempted"])

        elif intent == "pod_language_breakdown" and "language" in df.columns:
            st.bar_chart(df.set_index("language")["students"])

        elif intent in ("pod_top_passers", "pod_top_scorers", "pod_top_coins") and "name" in df.columns:
            score_col = (
                "questions_passed" if "questions_passed" in df.columns
                else "total_score" if "total_score" in df.columns
                else "total_coins" if "total_coins" in df.columns
                else None
            )
            if score_col:
                st.bar_chart(df.set_index("name")[score_col])

        elif intent in ("pod_longest_streak", "pod_active_streaks") and "streak_count" in df.columns:
            st.bar_chart(df.set_index("name")["streak_count"])

        elif intent == "pod_pass_rate" and "pass_rate_percent" in df.columns:
            st.bar_chart(df.set_index("college")["pass_rate_percent"])

    except Exception:
        pass  # Charts are best-effort


# ── Data renderer — handles both list and dict (student profile) ──────────────

def _render_data(data, intent: str) -> None:
    """Render data as table(s). data can be a list of dicts or a dict of sections."""
    if not data:
        return

    if isinstance(data, dict):
        # Student profile — render each section as its own table
        section_labels = {
            "submissions": "📝 Submissions",
            "streaks":     "🔥 Streaks",
            "badges":      "🏅 Badges",
            "coins":       "🪙 Coins",
        }
        for key, label in section_labels.items():
            rows = data.get(key, [])
            if rows:
                st.markdown(f"**{label}**")
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False)
                st.download_button(
                    f"⬇️ Download {label} CSV",
                    data=csv,
                    file_name=f"pod_{key}.csv",
                    mime="text/csv",
                    key=f"dl_{key}_{id(data)}",
                )
    else:
        # Regular list response
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
        _render_chart(df, intent)
        csv = df.to_csv(index=False)
        st.download_button(
            "⬇️ Download CSV",
            data=csv,
            file_name="pod_result.csv",
            mime="text/csv",
            key=f"dl_list_{id(data)}",
        )


# ── Session state ─────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []

if "college_name" not in st.session_state:
    st.session_state.college_name = ""


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Settings")
    college_input = st.text_input(
        "Your College Name",
        value=st.session_state.college_name,
        placeholder="e.g. Mahindra University",
        help="Automatically scopes every query to your college.",
    )
    st.session_state.college_name = college_input.strip()

    st.divider()
    st.markdown("### 💡 Example Questions")
    examples = [
        "Who solved today's POD?",
        "How many students attempted the POD today?",
        "What is today's POD question?",
        "Who solved the POD fastest today?",
        "Which students haven't attempted the POD yet?",
        "Give me a pass/fail summary",
        "What is our overall pass rate?",
        "Show me the top 10 passers",
        "Which students have never passed a POD?",
        "Who passed this week?",
        "Show difficulty breakdown",
        "Which languages are students using?",
        "Who solved hard problems?",
        "Who has the longest streak?",
        "Show active streaks",
        "Who lost their streak recently?",
        "Who has the most coins?",
        "Total points earned today",
        "Show top scorers",
        "Who earned badges?",
        "Who earned badges this week?",
        "What did Pranith Kumar Navath solve today?",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["_prefill"] = ex

    st.divider()
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.caption("TapTap POD Analytics · FastAPI + LangGraph + SQLAlchemy")


# ── Header ────────────────────────────────────────────────────────────────────

st.title("🧩 TapTap POD Analytics")
st.markdown("Ask any question about student Problem of the Day activity.")

if st.session_state.college_name:
    st.info(f"📍 College context: **{st.session_state.college_name}**", icon="🏫")
else:
    st.warning("Set your college name in the sidebar to scope results to your college.", icon="⚠️")

st.divider()


# ── Chat history ──────────────────────────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("data"):
            with st.expander("📊 View raw data"):
                _render_data(msg["data"], msg.get("intent", ""))
        if msg.get("intent"):
            st.caption(f"Intent: `{msg['intent']}`")


# ── Chat input ────────────────────────────────────────────────────────────────

prefill    = st.session_state.pop("_prefill", None)
user_input = st.chat_input("Ask about POD activity…")
query      = prefill or user_input

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Analysing…"):
            try:
                payload = {
                    "message":      query,
                    "college_name": st.session_state.college_name or None,
                }
                resp = requests.post(
                    f"{API_BASE}/chat",
                    json=payload,
                    timeout=30,
                )
                resp.raise_for_status()
                result = resp.json()

                answer = result.get("answer") or "No answer returned."
                intent = result.get("intent", "")
                data   = result.get("data") or []
                error  = result.get("error")

                st.markdown(answer)

                if data:
                    with st.expander("📊 View raw data"):
                        _render_data(data, intent)

                if error:
                    st.error(f"Backend error: {error}")

                if intent:
                    st.caption(f"Intent: `{intent}`")

                st.session_state.messages.append({
                    "role":    "assistant",
                    "content": answer,
                    "data":    data,
                    "intent":  intent,
                })

            except requests.exceptions.ConnectionError:
                msg = "❌ Cannot connect to the backend. Is uvicorn running on port 8000?"
                st.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
            except requests.exceptions.Timeout:
                msg = "⏳ Request timed out. Please try again."
                st.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
            except Exception as exc:
                msg = f"❌ Unexpected error: {exc}"
                st.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})