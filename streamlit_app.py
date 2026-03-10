# streamlit_app.py — TapTap Analytics Chatbot v3 Frontend

import os
import requests
import pandas as pd
import streamlit as st

# ── Config ────────────────────────────────────────────────────────────────────

API_BASE = os.getenv("TAPTAP_API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="TapTap Analytics",
    page_icon="🎓",
    layout="wide",
)

# ── Smart chart helper ────────────────────────────────────────────────────────
# FIX: moved to top of file — Streamlit reruns top-to-bottom so the function
#      must be defined before the block that calls it.

def _render_chart(df: pd.DataFrame, intent: str) -> None:
    """Render an appropriate chart based on intent and data shape."""
    try:
        if intent == "band_distribution" and "employabilityBand" in df.columns:
            st.bar_chart(df.set_index("employabilityBand")["count"])

        elif intent == "score_distribution" and "bucket_start" in df.columns:
            df = df.copy()
            df["range"] = df["bucket_start"].astype(str) + "–" + df["bucket_end"].astype(str)
            st.bar_chart(df.set_index("range")["count"])

        elif intent in ("top_students", "bottom_students") and "employabilityScore" in df.columns:
            label_col = "name" if "name" in df.columns else df.columns[0]
            st.bar_chart(df.set_index(label_col)["employabilityScore"])

        elif intent == "department_summary" and "avg_score" in df.columns:
            st.bar_chart(df.set_index("department")["avg_score"])

        elif intent == "hackathon_performance" and "score" in df.columns:
            label_col = "name" if "name" in df.columns else df.columns[0]
            st.bar_chart(df.set_index(label_col)["score"])

    except Exception:
        pass  # Chart rendering is best-effort


# ── Session state ─────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []   # [{role, content, data, intent}]

if "college_name" not in st.session_state:
    st.session_state.college_name = ""

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    # FIX: use_container_width replaces deprecated use_column_width
    st.image("https://via.placeholder.com/200x60?text=TapTap", use_container_width=True)
    st.markdown("## ⚙️ Settings")

    college_input = st.text_input(
        "Your College Name",
        value=st.session_state.college_name,
        placeholder="e.g. Sri Venkateswara College of Engineering",
        help="Automatically scopes every query to your college.",
    )
    st.session_state.college_name = college_input.strip()

    st.divider()
    st.markdown("### 💡 Example Questions")
    examples = [
        "Show me the top 10 students by employability score",
        "What is the band distribution in my college?",
        "Which department has the highest average score?",
        "Show bottom 5 students in CSE department",
        "How did students perform in the last hackathon?",
        "Give me a pod pass/fail summary",
        "What is the score distribution across my college?",
        "Show profile for student REG001",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["_prefill"] = ex

    st.divider()
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.caption("TapTap Analytics v3 · Powered by LangGraph + FastAPI")


# ── Header ────────────────────────────────────────────────────────────────────

st.title("🎓 TapTap Analytics Chatbot")
st.markdown(
    "Ask any question about student employability, hackathon performance, or pod submissions."
)

if st.session_state.college_name:
    st.info(f"📍 College context: **{st.session_state.college_name}**", icon="🏫")
else:
    st.warning("Set your college name in the sidebar to get scoped results.", icon="⚠️")

st.divider()


# ── Chat history ──────────────────────────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("data"):
            with st.expander("📊 View raw data"):
                df = pd.DataFrame(msg["data"])
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False)
                st.download_button(
                    "⬇️ Download CSV",
                    data=csv,
                    file_name="taptap_result.csv",
                    mime="text/csv",
                    key=f"dl_{id(msg)}",
                )
        if msg.get("intent"):
            st.caption(f"Intent: `{msg['intent']}`")


# ── Chat input ────────────────────────────────────────────────────────────────

prefill = st.session_state.pop("_prefill", None)
user_input = st.chat_input("Ask about student performance…", key="chat_input")

query = prefill or user_input

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Analysing…"):
            try:
                payload = {
                    "message": query,
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
                        df = pd.DataFrame(data)
                        st.dataframe(df, use_container_width=True)
                        _render_chart(df, intent)
                        csv = df.to_csv(index=False)
                        st.download_button(
                            "⬇️ Download CSV",
                            data=csv,
                            file_name="taptap_result.csv",
                            mime="text/csv",
                        )

                if error:
                    st.error(f"Backend error: {error}")

                if intent:
                    st.caption(f"Intent: `{intent}`")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "data": data,
                    "intent": intent,
                })

            except requests.exceptions.ConnectionError:
                msg = "❌ Cannot connect to the backend. Is the FastAPI server running?"
                st.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
            except requests.exceptions.Timeout:
                msg = "⏳ The request timed out. Please try again."
                st.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
            except Exception as exc:
                msg = f"❌ Unexpected error: {exc}"
                st.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})