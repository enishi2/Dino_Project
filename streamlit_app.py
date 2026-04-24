from __future__ import annotations

import base64
import html
import json
import os
import random
import re
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile

import streamlit as st
import streamlit.components.v1 as components

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
        .stTabs [data-baseweb="tab"]:hover {
            color: #7fc4ff !important;
        }
        .stTabs [aria-selected="true"] {
            color: #7fc4ff !important;
        }
        .stTabs [data-baseweb="tab-highlight"] {
            background-color: #7fc4ff !important;
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
            border-radius: 999px !important;
            overflow: hidden !important;
            padding: 0 !important;
            box-shadow: none !important;
        }
        [data-testid="stChatMessageAvatarUser"] > div,
        [data-testid="stChatMessageAvatarAssistant"] > div {
            background: transparent !important;
            border-radius: 999px !important;
            overflow: hidden !important;
            padding: 0 !important;
            box-shadow: none !important;
        }
        [data-testid="stChatMessageAvatarUser"] img,
        [data-testid="stChatMessageAvatarAssistant"] img {
            border-radius: 50% !important;
            background: transparent !important;
            box-shadow: none !important;
            display: block !important;
            overflow: hidden !important;
        }
        [data-testid="stChatMessageContent"] {
            background: transparent;
        }
        .dm-chat-row {
            display: flex;
            gap: 0.7rem;
            align-items: flex-start;
            margin: 0.85rem 0;
        }
        .dm-chat-avatar {
            width: 2.4rem;
            height: 2.4rem;
            border-radius: 50%;
            object-fit: cover;
            flex: 0 0 2.4rem;
            display: block;
            box-shadow: none;
            background: transparent;
        }
        .dm-chat-bubble {
            flex: 1;
            padding: 0.9rem 1rem;
            border-radius: 10px;
            background: rgba(18, 17, 13, 0.58);
            border: 1px solid rgba(250, 198, 62, 0.14);
            color: rgba(255, 248, 232, 0.96);
            line-height: 1.6;
        }
        .stTabs [data-baseweb="tab"]:hover {
            color: #8ac8ff !important;
        }
        .stTabs [aria-selected="true"] {
            color: #8ac8ff !important;
        }
        .stTabs [data-baseweb="tab-highlight"] {
            background-color: #8ac8ff !important;
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


def render_chat_message(role: str, content: str) -> None:
    avatar = chat_avatar(role)
    avatar_html = ""
    if avatar:
        avatar_html = f'<img class="dm-chat-avatar" src="{avatar}" alt="{role} avatar" />'
    safe_content = html.escape(content).replace("\n", "<br>")
    st.markdown(
        f"""
        <div class="dm-chat-row">
            {avatar_html}
            <div class="dm-chat-bubble">{safe_content}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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


def normalize_guess_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def guess_quote_difficulty(text: str, players: list[str]) -> int:
    cleaned = normalize_guess_text(text)
    lowered = cleaned.lower()
    difficulty = 0
    if 55 <= len(cleaned) <= 180:
        difficulty += 2
    elif 35 <= len(cleaned) <= 220:
        difficulty += 1
    if cleaned.count("!") <= 1 and cleaned.count("?") <= 1:
        difficulty += 1
    if not re.search(r"\b(?:haha|kkkk|lol|lmao|omg)\b", lowered):
        difficulty += 1
    if not any(player.lower().split()[0] in lowered for player in players):
        difficulty += 1
    if re.search(r"\b(?:maybe|perhaps|acho|talvez|wonder|feel|seems|kind of)\b", lowered):
        difficulty += 1
    return difficulty


def multiplayer_quote_candidates(messages: list, limit: int = 140) -> list[dict[str, str | int]]:
    players = sorted({message.sender for message in messages if message.sender != "Sistema"})
    seen: set[str] = set()
    candidates: list[dict[str, str | int]] = []
    for index, message in enumerate(messages):
        if message.sender == "Sistema" or not message.timestamp:
            continue
        text = normalize_guess_text(message.text)
        if len(text) < 35 or len(text) > 220:
            continue
        if text in seen:
            continue
        seen.add(text)
        difficulty = guess_quote_difficulty(text, players)
        if difficulty < 3:
            continue
        candidates.append(
            {
                "id": f"q-{index}",
                "sender": message.sender,
                "text": text,
                "date": message.timestamp.strftime("%Y-%m-%d"),
                "difficulty": difficulty,
            }
        )
    candidates.sort(key=lambda item: (item["difficulty"], len(str(item["text"]))), reverse=True)
    return candidates[:limit]


def render_multiplayer_guess(messages: list, user_label: str) -> None:
    host = os.getenv("PARTYKIT_HOST", "").strip()
    quotes = multiplayer_quote_candidates(messages)
    if not host:
        st.info("Set `PARTYKIT_HOST` to enable realtime multiplayer rooms.")
        return
    if len(quotes) < 12:
        st.info("The current conversation does not have enough solid quotes for multiplayer yet.")
        return

    payload = json.dumps(
        {
            "host": host,
            "quotes": quotes,
            "players": sorted({message.sender for message in messages if message.sender != "Sistema"}),
            "userLabel": user_label or "Player",
        }
    )
    components.html(
        f"""
        <div id="dm-multi-root"></div>
        <script>
        const config = {payload};
        const root = document.getElementById("dm-multi-root");
        root.innerHTML = `
          <style>
            :root {{
              color-scheme: dark;
              font-family: Inter, system-ui, sans-serif;
            }}
            .dm-wrap {{ color: #fff4df; }}
            .dm-row {{ display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 0.9rem; }}
            .dm-input, .dm-button {{
              border-radius: 10px; border: 1px solid rgba(138, 200, 255, 0.18);
              background: rgba(17, 16, 12, 0.72); color: #fff4df; padding: 0.8rem 0.95rem;
            }}
            .dm-input {{ min-width: 10rem; flex: 1; }}
            .dm-button {{ cursor: pointer; font-weight: 600; }}
            .dm-button.primary {{ background: rgba(138, 200, 255, 0.18); }}
            .dm-panel {{
              background: rgba(17, 16, 12, 0.72); border: 1px solid rgba(250, 198, 62, 0.14);
              border-radius: 12px; padding: 1rem; margin-top: 0.8rem;
            }}
            .dm-muted {{ color: rgba(255, 244, 210, 0.72); font-size: 0.92rem; }}
            .dm-quote {{ font-size: 1.06rem; line-height: 1.7; }}
            .dm-answers {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.7rem; margin-top: 1rem; }}
            .dm-score {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.7rem; margin-top: 1rem; }}
            .dm-chip {{ border-radius: 999px; padding: 0.35rem 0.75rem; background: rgba(138, 200, 255, 0.12); display: inline-block; }}
            .dm-list {{ margin: 0.5rem 0 0; padding-left: 1rem; }}
            .dm-banner {{ margin-top: 0.85rem; padding: 0.8rem 0.95rem; border-radius: 10px; }}
            .dm-success {{ background: rgba(59, 130, 90, 0.18); color: #b8f7ce; }}
            .dm-error {{ background: rgba(180, 54, 54, 0.18); color: #ffc7c7; }}
          </style>
          <div class="dm-wrap">
            <div class="dm-row">
              <input id="room" class="dm-input" placeholder="Room code" value="" />
              <input id="name" class="dm-input" placeholder="Display name" value="${{config.userLabel}}" />
              <button id="join" class="dm-button primary">Join room</button>
              <button id="next" class="dm-button">Next round</button>
            </div>
            <div class="dm-muted">Realtime room powered by PartyKit. Quotes are prefiltered to lean naturally harder.</div>
            <div id="status" class="dm-panel">Join a room to start.</div>
            <div id="game" class="dm-panel" style="display:none;"></div>
          </div>
        `;

        const roomInput = root.querySelector("#room");
        const nameInput = root.querySelector("#name");
        const joinButton = root.querySelector("#join");
        const nextButton = root.querySelector("#next");
        const statusEl = root.querySelector("#status");
        const gameEl = root.querySelector("#game");

        let socket = null;
        let connectionId = null;
        let latestState = null;
        let seededRoom = null;

        function setStatus(text) {{
          statusEl.textContent = text;
        }}

        function send(type, payload = {{}}) {{
          if (!socket || socket.readyState !== WebSocket.OPEN) return;
          socket.send(JSON.stringify({{ type, ...payload }}));
        }}

        function renderState(state) {{
          latestState = state;
          const players = Object.values(state.players || {{}}).sort((a, b) => b.score - a.score);
          const round = state.currentRound;
          const scoreboard = players.map((player) => `
            <div class="dm-panel">
              <div><strong>${{player.name}}</strong></div>
              <div class="dm-muted">${{player.score}} points</div>
            </div>
          `).join("");

          if (!round) {{
            gameEl.style.display = "block";
            gameEl.innerHTML = `
              <div class="dm-chip">Players online: ${{players.length}}</div>
              <div class="dm-score">${{scoreboard || '<div class="dm-muted">No players yet.</div>'}}</div>
              <div class="dm-muted" style="margin-top: 1rem;">Press "Next round" when everyone is ready.</div>
            `;
            return;
          }}

          const alreadyGuessed = connectionId && round.guesses && round.guesses[connectionId];
          const answers = (round.options || []).map((option) => `
            <button class="dm-button answer" data-answer="${{option}}" ${{alreadyGuessed ? "disabled" : ""}}>${{option}}</button>
          `).join("");

          const banner = round.reveal
            ? `<div class="dm-banner ${{round.lastCorrect === connectionId ? "dm-success" : "dm-error"}}">
                Correct answer: <strong>${{round.correctSender}}</strong><br>
                Date: ${{round.dateLabel}}
              </div>`
            : "";

          gameEl.style.display = "block";
          gameEl.innerHTML = `
            <div class="dm-chip">Difficulty: hard</div>
            <div class="dm-muted" style="margin-top: 0.75rem;">Room: <strong>${{state.roomId}}</strong></div>
            <div class="dm-panel" style="margin-top: 0.9rem;">
              <div class="dm-quote">${{round.text}}</div>
              <div class="dm-answers">${{answers}}</div>
              ${{banner}}
            </div>
            <div class="dm-score">${{scoreboard}}</div>
          `;

          gameEl.querySelectorAll(".answer").forEach((button) => {{
            button.addEventListener("click", () => send("submit_guess", {{ answer: button.dataset.answer }}));
          }});
        }}

        function connect() {{
          const room = roomInput.value.trim().toLowerCase();
          const displayName = nameInput.value.trim() || "Player";
          if (!room) {{
            setStatus("Choose a room code first.");
            return;
          }}
          if (socket) socket.close();
          const protocol = config.host.includes("localhost") ? "ws" : "wss";
          socket = new WebSocket(`${{protocol}}://${{config.host}}/party/${{room}}`);

          socket.addEventListener("open", () => {{
            setStatus(`Connected to room ${{room}}.`);
            send("join", {{ displayName }});
            if (seededRoom !== room) {{
              send("seed_quotes", {{ quotes: config.quotes, options: config.players }});
              seededRoom = room;
            }}
          }});

          socket.addEventListener("message", (event) => {{
            const payload = JSON.parse(event.data);
            if (payload.type === "session") {{
              connectionId = payload.connectionId;
            }}
            if (payload.type === "state") {{
              renderState(payload.state);
            }}
            if (payload.type === "notice") {{
              setStatus(payload.message);
            }}
          }});

          socket.addEventListener("close", () => {{
            setStatus("Disconnected from the room.");
          }});
        }}

        joinButton.addEventListener("click", connect);
        nextButton.addEventListener("click", () => send("next_round"));
        </script>
        """,
        height=760,
    )


cloud_mode = supabase_store.supabase_configured()

if cloud_mode and ("user" not in st.session_state or "session" not in st.session_state):
    render_auth()
    st.stop()

inject_app_styles()

st.title("Dino Memo")
st.caption("A chat bot with semantic search and smart conversation excerpts.")

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
    tab_chat, tab_guess, tab_multiplayer = st.tabs(["Chat", "Guess Who Said It", "Multiplayer"])

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
            render_chat_message(item["role"], item["content"])

        if question:
            render_chat_message("user", question)
            results = search_blocks(question, blocks, top_k=top_k)
            with st.spinner("Reading the most relevant excerpts and preparing an answer..."):
                selected_model = gemini_model if provider == "Gemini" else groq_model
                answer = ask_ai(question, results, provider=provider, model=selected_model, temperature=temperature)
            st.session_state["chat"].append({"role": "user", "content": question})
            st.session_state["chat"].append({"role": "assistant", "content": answer})
            render_chat_message("assistant", answer)

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
                st.caption("Random quote from the indexed conversation.")
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

    with tab_multiplayer:
        st.subheader("Guess Who Said It Multiplayer")
        st.caption("Create a room, join from multiple browsers, and play live rounds with harder quotes.")
        user_label = ""
        if cloud_mode and "user" in st.session_state:
            user_label = st.session_state["user"].email.split("@", 1)[0]
        render_multiplayer_guess(messages, user_label)

with right:
    st.subheader("Knowledge Base Summary")
    st.metric("Messages", meta.get("message_count", "0"))
    st.metric("Excerpts", meta.get("block_count", "0"))
    st.caption(f"Source: {meta.get('source_name', 'no source')}")

    st.subheader("Direct Search")
    query = st.text_input("Search by meaning or topic")
    if query:
        for block, score in search_blocks(query, blocks, top_k=5):
            with st.expander(f"{block.start_at[:10]} - {block.title} - {score:.2f}"):
                st.text(block.text[:1800])
