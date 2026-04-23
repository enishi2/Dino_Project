from __future__ import annotations

import base64
import os
import random
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile

import streamlit as st

import supabase_store
from whatsapp_memory_core import (
    ask_ai,
    build_blocks,
    load_blocks,
    load_messages,
    load_meta,
    parse_messages,
    read_whatsapp_export,
    rebuild_database,
    search_blocks,
    timeline_by_day,
)


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("LOCALAPPDATA", APP_DIR)) / "WhatsAppMemoryBot"
DB_PATH = DATA_DIR / "whatsapp_memory_app.sqlite3"
LOGO_PATH = APP_DIR / "assets" / "dino-memo-logo.png"
USER_CHAT_ICON_PATH = APP_DIR / "assets" / "dino-chat-icon.png"
BOT_CHAT_ICON_PATH = APP_DIR / "assets" / "bot-chat-icon.png"


st.set_page_config(page_title="Dino Memo", page_icon="Chat", layout="wide")


def inject_auth_styles() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 30% 18%, rgba(243, 188, 58, 0.42), transparent 24rem),
                linear-gradient(135deg, #d19a25 0%, #5d481c 42%, #11100c 100%);
        }
        [data-testid="stHeader"] {
            background: transparent;
        }
        [data-testid="stMainBlockContainer"] {
            padding-top: 4.8rem;
        }
        .auth-logo {
            display: block;
            width: 132px;
            height: 132px;
            object-fit: cover;
            border-radius: 50%;
            margin: 0 auto 1.15rem;
            filter: drop-shadow(0 16px 26px rgba(0, 0, 0, 0.34));
        }
        .auth-title {
            text-align: center;
            margin-bottom: 1.35rem;
        }
        .auth-title h1 {
            color: rgba(255, 255, 255, 0.95);
            font-size: 2.35rem;
            font-weight: 500;
            line-height: 1.1;
            margin: 0 0 0.55rem;
        }
        .auth-title p {
            color: rgba(255, 255, 255, 0.68);
            font-size: 0.98rem;
            margin: 0;
        }
        div[data-testid="stTextInput"] input {
            height: 2.75rem;
            border-radius: 3px;
            background: rgba(255, 255, 255, 0.15);
            border: 1px solid rgba(255, 255, 255, 0.18);
            color: rgba(255, 255, 255, 0.94);
        }
        div[data-testid="stTextInput"] label {
            color: rgba(255, 255, 255, 0.78);
            font-size: 0.86rem;
        }
        .stButton button {
            height: 2.85rem;
            border-radius: 999px;
            border: 0;
            background: rgba(255, 255, 255, 0.76);
            color: #20242b;
            font-weight: 600;
        }
        .stButton button:hover {
            background: rgba(255, 255, 255, 0.9);
            color: #20242b;
        }
        .stTabs [data-baseweb="tab-list"] {
            justify-content: center;
            gap: 0.45rem;
            margin-bottom: 0.75rem;
        }
        .stTabs [data-baseweb="tab"] {
            height: 2.35rem;
            padding: 0 0.75rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_app_styles() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 28% 8%, rgba(243, 188, 58, 0.26), transparent 22rem),
                linear-gradient(135deg, #d19a25 0%, #5d481c 34%, #11100c 100%);
        }
        [data-testid="stHeader"] {
            background: transparent;
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #18130a 0%, #221b0d 58%, #0d0c09 100%);
            border-right: 1px solid rgba(250, 198, 62, 0.18);
        }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] label {
            color: rgba(255, 244, 210, 0.86);
        }
        .sidebar-brand {
            text-align: center;
            margin: 0.2rem 0 1.35rem;
        }
        .sidebar-logo {
            display: block;
            width: 86px;
            height: 86px;
            object-fit: cover;
            border-radius: 50%;
            margin: 0 auto 0.55rem;
            filter: drop-shadow(0 10px 18px rgba(0, 0, 0, 0.38));
        }
        .sidebar-brand-title {
            color: rgba(255, 245, 217, 0.96);
            font-size: 1.05rem;
            font-weight: 700;
            letter-spacing: 0;
        }
        div[data-testid="stMetric"] {
            background: rgba(18, 17, 13, 0.58);
            border: 1px solid rgba(250, 198, 62, 0.14);
            border-radius: 8px;
            padding: 0.65rem 0.75rem;
        }
        div[data-testid="stExpander"] {
            background: rgba(18, 17, 13, 0.46);
            border-color: rgba(250, 198, 62, 0.14);
        }
        [data-testid="stChatMessageAvatarUser"],
        [data-testid="stChatMessageAvatarAssistant"] {
            background: transparent !important;
        }
        [data-testid="stChatMessageAvatarUser"] img,
        [data-testid="stChatMessageAvatarAssistant"] img {
            border-radius: 50% !important;
            background: transparent !important;
            box-shadow: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def image_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def chat_avatar(role: str) -> str | None:
    if role == "user" and USER_CHAT_ICON_PATH.exists():
        return image_data_uri(USER_CHAT_ICON_PATH)
    if role in {"assistant", "bot"} and BOT_CHAT_ICON_PATH.exists():
        return image_data_uri(BOT_CHAT_ICON_PATH)
    return None


def local_import_conversation(path: Path) -> None:
    text = read_whatsapp_export(path)
    messages = parse_messages(text)
    blocks = build_blocks(messages)
    rebuild_database(DB_PATH, messages, blocks, path.name)
    st.session_state["chat"] = []
    st.success(f"Conversation imported: {len(messages)} messages across {len(blocks)} excerpts.")


def cloud_import_conversation(uploaded_file) -> None:
    session = st.session_state["session"]
    user = st.session_state["user"]
    client = supabase_store.session_client(session.access_token, session.refresh_token)
    with NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
        temp_file.write(uploaded_file.getvalue())
        temp_path = Path(temp_file.name)
    text = read_whatsapp_export(temp_path)
    temp_path.unlink(missing_ok=True)
    messages = parse_messages(text)
    blocks = build_blocks(messages)
    with st.spinner("Saving the indexed conversation to Supabase..."):
        conversation_id = supabase_store.save_conversation(client, user.id, uploaded_file.name, messages, blocks)
    st.session_state["conversation_id"] = conversation_id
    st.session_state["chat"] = []
    st.success(f"Conversation imported: {len(messages)} messages across {len(blocks)} excerpts.")


def render_auth() -> None:
    auth_screen = st.empty()
    with auth_screen.container():
        inject_auth_styles()
        logo_html = ""
        if LOGO_PATH.exists():
            logo_html = f'<img class="auth-logo" src="{image_data_uri(LOGO_PATH)}" alt="Dino Memo logo" />'
        st.markdown(
            f"""
            <div class="auth-title">
                {logo_html}
                <h1>Dino Memo</h1>
                <p>Sign in to access your private WhatsApp conversation memory.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if supabase_store.supabase_url_has_rest_path():
            st.error("SUPABASE_URL should not include /rest/v1. Use only https://your-project.supabase.co")
        _left, center, _right = st.columns([1, 0.44, 1])
        with center:
            tab_login, tab_signup = st.tabs(["Sign in", "Create account"])

            with tab_login:
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_password")
                if st.button("Sign in", use_container_width=True):
                    try:
                        auth = supabase_store.sign_in(email, password)
                        if not auth["session"]:
                            st.error("Sign-in did not return a session. Check if email confirmation is required.")
                            st.stop()
                        st.session_state["user"] = auth["user"]
                        st.session_state["session"] = auth["session"]
                        auth_screen.empty()
                        st.rerun()
                    except Exception as exc:
                        st.error(auth_error_message(exc))

            with tab_signup:
                email = st.text_input("Email", key="signup_email")
                password = st.text_input("Password", type="password", key="signup_password")
                if st.button("Create account", use_container_width=True):
                    try:
                        auth = supabase_store.sign_up(email, password)
                        if not auth["session"]:
                            st.warning("Account created, but no session was returned. Check your email or disable email confirmation for testing.")
                            st.stop()
                        st.session_state["user"] = auth["user"]
                        st.session_state["session"] = auth["session"]
                        st.success("Account created. Check your email if confirmation is enabled.")
                        auth_screen.empty()
                        st.rerun()
                    except Exception as exc:
                        st.error(auth_error_message(exc))


def auth_error_message(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if "invalid login credentials" in lowered:
        return "Invalid email or password. Check the user in Supabase Authentication > Users."
    if "email not confirmed" in lowered or "confirm" in lowered:
        return "Email is not confirmed. Confirm the user in Supabase or disable email confirmation while testing."
    if "api key" in lowered or "jwt" in lowered:
        return "Supabase anon key looks invalid. Check SUPABASE_ANON_KEY."
    if "getaddrinfo failed" in lowered or "name or service not known" in lowered:
        return (
            "Could not reach Supabase. Check SUPABASE_URL for typos and make sure it looks like "
            "https://your-project.supabase.co without /rest/v1."
        )
    return f"Authentication error: {message}"


def load_cloud_data() -> tuple[dict[str, str], list, list]:
    session = st.session_state["session"]
    client = supabase_store.session_client(session.access_token, session.refresh_token)
    conversations = supabase_store.list_conversations(client, st.session_state["user"].id)
    if not conversations:
        return {}, [], []

    options = {f"{item['source_name']} - {item['indexed_at'][:10]}": item["id"] for item in conversations}
    selected = st.sidebar.selectbox("Conversation", list(options))
    st.session_state["conversation_id"] = options[selected]
    return supabase_store.load_conversation(client, st.session_state["conversation_id"])


def load_local_data() -> tuple[dict[str, str], list, list]:
    return load_meta(DB_PATH), load_messages(DB_PATH), load_blocks(DB_PATH)


def guess_candidates(messages: list) -> list:
    return [
        message
        for message in messages
        if message.sender != "Sistema" and len(message.text.strip()) >= 28 and "\n" not in message.text[:220]
    ]


def guess_period_key(message) -> str:
    if not message.timestamp:
        return "Unknown period"
    return message.timestamp.strftime("%Y-%m")


def pick_guess_candidate(messages: list):
    candidates = guess_candidates(messages)
    if not candidates:
        return None

    current_text = st.session_state.get("guess_round_text")
    recent_texts = st.session_state.get("guess_recent_texts", [])
    usable = [message for message in candidates if message.text != current_text and message.text not in recent_texts]
    if not usable:
        usable = [message for message in candidates if message.text != current_text] or candidates

    by_period: dict[str, list] = defaultdict(list)
    for message in usable:
        by_period[guess_period_key(message)].append(message)

    chosen_period = random.choice(list(by_period))
    return random.choice(by_period[chosen_period])


def ensure_guess_round(messages: list) -> None:
    if st.session_state.get("guess_round_answered"):
        return
    if st.session_state.get("guess_round_text"):
        return
    pick = pick_guess_candidate(messages)
    if not pick:
        return
    st.session_state["guess_round_text"] = pick.text
    st.session_state["guess_round_sender"] = pick.sender
    st.session_state["guess_round_date"] = pick.timestamp.strftime("%B %d, %Y") if pick.timestamp else "Unknown date"
    st.session_state["guess_round_period"] = guess_period_key(pick)


def start_new_guess_round(messages: list) -> None:
    st.session_state["guess_round_text"] = None
    st.session_state["guess_round_sender"] = None
    st.session_state["guess_round_date"] = None
    st.session_state["guess_round_period"] = None
    st.session_state["guess_round_answered"] = False
    st.session_state["guess_feedback"] = ""
    st.session_state["guess_feedback_kind"] = None
    ensure_guess_round(messages)


cloud_mode = supabase_store.supabase_configured()

if cloud_mode and ("user" not in st.session_state or "session" not in st.session_state):
    render_auth()
    st.stop()

inject_app_styles()

st.title("Dino Memo")
st.caption("A chat bot with semantic search, smart conversation excerpts, and a timeline.")

with st.sidebar:
    with st.popover("Settings", use_container_width=True):
        provider = st.selectbox("Provider", ["Auto", "Groq", "Gemini"])
        groq_model = st.selectbox(
            "Groq model",
            [
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "deepseek-r1-distill-llama-70b",
            ],
        )
        gemini_model = st.selectbox(
            "Gemini model",
            [
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-flash-latest",
                "gemini-2.5-pro",
            ],
        )
        top_k = st.slider("Retrieved excerpts", min_value=3, max_value=10, value=6)
        temperature = st.slider("Creativity", min_value=0.0, max_value=1.0, value=0.35, step=0.05)
        st.caption("API keys stay on the server.")

    if LOGO_PATH.exists():
        st.markdown(
            f"""
            <div class="sidebar-brand">
                <img class="sidebar-logo" src="{image_data_uri(LOGO_PATH)}" alt="Dino Memo logo" />
                <div class="sidebar-brand-title">Dino Memo</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    if cloud_mode:
        st.header("Account")
        st.caption(st.session_state["user"].email)
        if st.button("Sign out", use_container_width=True):
            supabase_store.sign_out()
            st.session_state.clear()
            st.rerun()
    else:
        st.warning("Local mode: configure SUPABASE_URL and SUPABASE_ANON_KEY to enable login.")

    st.divider()
    st.header("Knowledge Base")
    uploaded = st.file_uploader("Import a WhatsApp .txt export", type=["txt"])
    if uploaded and st.button("Index uploaded file", use_container_width=True):
        if cloud_mode:
            cloud_import_conversation(uploaded)
        else:
            DATA_DIR.mkdir(exist_ok=True)
            upload_path = DATA_DIR / "uploaded_whatsapp.txt"
            upload_path.write_bytes(uploaded.getvalue())
            local_import_conversation(upload_path)

    st.info("Uploading a file creates or replaces an indexed conversation with the same source name.")


try:
    meta, messages, blocks = load_cloud_data() if cloud_mode else load_local_data()
except Exception as exc:
    message = str(exc)
    if "permission denied for table conversations" in message:
        st.error(
            "Supabase is connected, but the authenticated role does not have table permissions yet. "
            "Run the GRANT section from supabase_schema.sql in the Supabase SQL editor."
        )
        st.stop()
    raise

if not blocks:
    st.info("Import a conversation to create the searchable memory.")
    st.stop()

left, right = st.columns([0.68, 0.32], gap="large")

with left:
    tab_chat, tab_guess = st.tabs(["Chat", "Guess Who Said It"])

    with tab_chat:
        st.subheader("Bot")
        if "chat" not in st.session_state:
            st.session_state["chat"] = []

        examples = [
            "How did the friendship start?",
            "What signs show interest or connection between them?",
            "What did she say about art, AI, and Portugal?",
            "Are there any relationship concerns or points to be careful about?",
        ]
        selected_example = st.selectbox("Quick questions", [""] + examples)
        question = st.chat_input("Ask something about the conversation")
        if selected_example and st.button("Ask example"):
            question = selected_example

        for item in st.session_state["chat"]:
            with st.chat_message(item["role"], avatar=chat_avatar(item["role"])):
                st.markdown(item["content"])

        if question:
            with st.chat_message("user", avatar=chat_avatar("user")):
                st.markdown(question)
            results = search_blocks(question, blocks, top_k=top_k)
            with st.spinner("Reading the most relevant excerpts and preparing an answer..."):
                selected_model = gemini_model if provider == "Gemini" else groq_model
                answer = ask_ai(question, results, provider=provider, model=selected_model, temperature=temperature)
            st.session_state["chat"].append({"role": "user", "content": question})
            st.session_state["chat"].append({"role": "assistant", "content": answer})
            with st.chat_message("assistant", avatar=chat_avatar("assistant")):
                st.markdown(answer)

    with tab_guess:
        st.subheader("Guess Who Said It")
        players = sorted({message.sender for message in messages if message.sender != "Sistema"})
        if len(players) < 2:
            st.info("This game needs at least two participants in the conversation.")
        else:
            if "guess_score" not in st.session_state:
                st.session_state["guess_score"] = 0
                st.session_state["guess_total"] = 0
                st.session_state["guess_round_answered"] = False
                st.session_state["guess_feedback"] = ""
                st.session_state["guess_feedback_kind"] = None
                st.session_state["guess_recent_texts"] = []
            ensure_guess_round(messages)

            rounds_played = st.session_state["guess_total"]
            correct_answers = st.session_state["guess_score"]
            accuracy = round((correct_answers / rounds_played) * 100) if rounds_played else 0

            metric_col1, metric_col2, metric_col3, action_col = st.columns([0.22, 0.22, 0.22, 0.34])
            with metric_col1:
                st.metric("Correct", str(correct_answers))
            with metric_col2:
                st.metric("Rounds", str(rounds_played))
            with metric_col3:
                st.metric("Accuracy", f"{accuracy}%")
            with action_col:
                if st.button("Next quote", key="new_guess_round", use_container_width=True):
                    start_new_guess_round(messages)
                    st.rerun()

            if st.session_state.get("guess_round_text"):
                st.caption(
                    f"Selected from {st.session_state.get('guess_round_period', 'the conversation timeline')}."
                )
                st.markdown(
                    f"""
                    <div style="padding: 1rem 1.1rem; border-radius: 10px; background: rgba(18,17,13,0.52); border: 1px solid rgba(250,198,62,0.14);">
                        <div style="font-size: 1.06rem; line-height: 1.6;">{st.session_state['guess_round_text']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                button_cols = st.columns(len(players))
                for idx, player in enumerate(players):
                    with button_cols[idx]:
                        if st.button(player, key=f"guess_{idx}", use_container_width=True):
                            if not st.session_state.get("guess_round_answered"):
                                st.session_state["guess_total"] += 1
                                st.session_state["guess_round_answered"] = True
                                recent = st.session_state.get("guess_recent_texts", [])
                                st.session_state["guess_recent_texts"] = (
                                    [st.session_state["guess_round_text"], *recent][:12]
                                )
                                if player == st.session_state["guess_round_sender"]:
                                    st.session_state["guess_score"] += 1
                                    st.session_state["guess_feedback"] = f"Correct. It was {player}."
                                    st.session_state["guess_feedback_kind"] = "success"
                                else:
                                    st.session_state["guess_feedback"] = (
                                        f"Not quite. The correct answer was {st.session_state['guess_round_sender']}."
                                    )
                                    st.session_state["guess_feedback_kind"] = "error"
                            st.rerun()

                if st.session_state.get("guess_feedback"):
                    if st.session_state.get("guess_feedback_kind") == "success":
                        st.success(
                            f"{st.session_state['guess_feedback']} Conversation date: {st.session_state['guess_round_date']}."
                        )
                    else:
                        st.error(
                            f"{st.session_state['guess_feedback']} Conversation date: {st.session_state['guess_round_date']}."
                        )

with right:
    st.subheader("Knowledge Base Summary")
    st.metric("Messages", meta.get("message_count", "0"))
    st.metric("Excerpts", meta.get("block_count", "0"))
    st.caption(f"Source: {meta.get('source_name', 'no source')}")

    st.subheader("Timeline")
    timeline = timeline_by_day(messages)
    if timeline:
        labels = [f"{day['date']} - {day['messages']} messages" for day in timeline]
        selected_label = st.selectbox("Choose a day", labels)
        selected_day = timeline[labels.index(selected_label)]
        st.write("Participants:", selected_day["senders"])
        st.write("Topics:", selected_day["topics"] or "no topics detected")
        st.caption(str(selected_day["first"]))
    else:
        st.caption("No timeline available.")

    st.subheader("Direct Search")
    query = st.text_input("Search by meaning or topic")
    if query:
        for block, score in search_blocks(query, blocks, top_k=5):
            with st.expander(f"{block.start_at[:10]} - {block.title} - {score:.2f}"):
                st.text(block.text[:1800])
