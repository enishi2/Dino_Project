from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from groq import Groq
    from groq import RateLimitError
except ImportError:
    Groq = None
    RateLimitError = None


MESSAGE_RE = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4}) (?P<time>\d{1,2}:\d{2}) - (?:(?P<sender>.*?): )?(?P<text>.*)$"
)

MOJIBAKE_MARKERS = ("Ã", "Â", "â€", "ðŸ")
STOPWORDS = {
    "a",
    "about",
    "agora",
    "ai",
    "ainda",
    "also",
    "and",
    "ao",
    "aos",
    "are",
    "as",
    "at",
    "até",
    "but",
    "com",
    "como",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "ela",
    "ele",
    "em",
    "eu",
    "for",
    "foi",
    "from",
    "have",
    "he",
    "i",
    "in",
    "is",
    "it",
    "like",
    "me",
    "meu",
    "minha",
    "na",
    "não",
    "nao",
    "no",
    "now",
    "of",
    "o",
    "os",
    "para",
    "por",
    "que",
    "say",
    "se",
    "she",
    "sobre",
    "that",
    "the",
    "this",
    "to",
    "um",
    "uma",
    "voce",
    "você",
    "was",
    "we",
    "will",
    "what",
    "with",
    "you",
    "allan",
    "carlos",
    "nadine",
}


@dataclass(frozen=True)
class Message:
    timestamp: datetime | None
    sender: str
    text: str
    raw: str


@dataclass(frozen=True)
class Block:
    block_id: int
    start_at: str
    end_at: str
    senders: str
    title: str
    text: str
    message_count: int


def read_whatsapp_export(path: str | Path) -> str:
    data = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        if looks_readable(text):
            return fix_mojibake(text)
    return fix_mojibake(data.decode("utf-8", errors="replace"))


def looks_readable(text: str) -> bool:
    sample = text[:2000]
    return sample.count("\ufffd") < 5


def fix_mojibake(text: str) -> str:
    if not any(marker in text for marker in MOJIBAKE_MARKERS):
        return text
    for source_encoding in ("cp1252", "latin-1"):
        try:
            fixed = text.encode(source_encoding).decode("utf-8")
        except UnicodeError:
            continue
        if len(fixed.strip()) >= len(text.strip()) * 0.7:
            return fixed
    return text


def parse_messages(text: str) -> list[Message]:
    messages: list[Message] = []
    current: Message | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip("\ufeff")
        match = MESSAGE_RE.match(line)
        if match:
            if current:
                messages.append(current)
            timestamp = parse_timestamp(match.group("date"), match.group("time"))
            sender = (match.group("sender") or "Sistema").strip()
            body = match.group("text").strip()
            current = Message(timestamp=timestamp, sender=sender, text=body, raw=line)
        elif current:
            current = Message(
                timestamp=current.timestamp,
                sender=current.sender,
                text=f"{current.text}\n{line}".strip(),
                raw=f"{current.raw}\n{line}",
            )
    if current:
        messages.append(current)
    return [message for message in messages if message.text]


def parse_timestamp(date_text: str, time_text: str) -> datetime | None:
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M"):
        try:
            return datetime.strptime(f"{date_text} {time_text}", fmt)
        except ValueError:
            pass
    return None


def build_blocks(messages: list[Message], max_chars: int = 2200, gap_hours: float = 6) -> list[Block]:
    blocks: list[Block] = []
    bucket: list[Message] = []

    def should_split(previous: Message, current: Message, current_chars: int) -> bool:
        if current_chars >= max_chars:
            return True
        if previous.timestamp and current.timestamp:
            gap = (current.timestamp - previous.timestamp).total_seconds() / 3600
            return gap > gap_hours
        return False

    for message in messages:
        if bucket:
            chars = sum(len(item.text) for item in bucket)
            if should_split(bucket[-1], message, chars):
                blocks.append(make_block(len(blocks) + 1, bucket))
                bucket = []
        bucket.append(message)

    if bucket:
        blocks.append(make_block(len(blocks) + 1, bucket))
    return blocks


def make_block(block_id: int, messages: list[Message]) -> Block:
    dated = [message.timestamp for message in messages if message.timestamp]
    start_at = min(dated).isoformat(sep=" ", timespec="minutes") if dated else ""
    end_at = max(dated).isoformat(sep=" ", timespec="minutes") if dated else ""
    senders = ", ".join(sorted({message.sender for message in messages}))
    lines = []
    for message in messages:
        when = message.timestamp.strftime("%d/%m/%Y %H:%M") if message.timestamp else "no date"
        lines.append(f"[{when}] {message.sender}: {message.text}")
    text = "\n".join(lines)
    return Block(
        block_id=block_id,
        start_at=start_at,
        end_at=end_at,
        senders=senders,
        title=guess_title(text),
        text=text,
        message_count=len(messages),
    )


def guess_title(text: str) -> str:
    words = [word for word in tokenize(text) if word not in STOPWORDS]
    common = [word for word, _count in Counter(words).most_common(4)]
    return " / ".join(common).title() if common else "Conversation excerpt"


def init_db(db_path: str | Path) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path.resolve()), timeout=30) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                sender TEXT NOT NULL,
                text TEXT NOT NULL,
                raw TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS blocks (
                id INTEGER PRIMARY KEY,
                start_at TEXT,
                end_at TEXT,
                senders TEXT,
                title TEXT,
                text TEXT NOT NULL,
                message_count INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )


def rebuild_database(db_path: str | Path, messages: list[Message], blocks: list[Block], source_name: str) -> None:
    init_db(db_path)
    with sqlite3.connect(str(Path(db_path).resolve()), timeout=30) as conn:
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM blocks")
        conn.execute("DELETE FROM meta")
        conn.executemany(
            "INSERT INTO messages (timestamp, sender, text, raw) VALUES (?, ?, ?, ?)",
            [
                (
                    message.timestamp.isoformat(sep=" ", timespec="minutes") if message.timestamp else "",
                    message.sender,
                    message.text,
                    message.raw,
                )
                for message in messages
            ],
        )
        conn.executemany(
            """
            INSERT INTO blocks (id, start_at, end_at, senders, title, text, message_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    block.block_id,
                    block.start_at,
                    block.end_at,
                    block.senders,
                    block.title,
                    block.text,
                    block.message_count,
                )
                for block in blocks
            ],
        )
        meta = {
            "source_name": source_name,
            "message_count": str(len(messages)),
            "block_count": str(len(blocks)),
            "indexed_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
        }
        conn.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", meta.items())


def load_blocks(db_path: str | Path) -> list[Block]:
    init_db(db_path)
    with sqlite3.connect(str(Path(db_path).resolve()), timeout=30) as conn:
        rows = conn.execute(
            "SELECT id, start_at, end_at, senders, title, text, message_count FROM blocks ORDER BY id"
        ).fetchall()
    return [Block(*row) for row in rows]


def load_messages(db_path: str | Path) -> list[Message]:
    init_db(db_path)
    with sqlite3.connect(str(Path(db_path).resolve()), timeout=30) as conn:
        rows = conn.execute("SELECT timestamp, sender, text, raw FROM messages ORDER BY id").fetchall()
    messages = []
    for timestamp, sender, text, raw in rows:
        parsed = datetime.fromisoformat(timestamp) if timestamp else None
        messages.append(Message(parsed, sender, text, raw))
    return messages


def load_meta(db_path: str | Path) -> dict[str, str]:
    init_db(db_path)
    with sqlite3.connect(str(Path(db_path).resolve()), timeout=30) as conn:
        return dict(conn.execute("SELECT key, value FROM meta").fetchall())


def search_blocks(query: str, blocks: list[Block], top_k: int = 6) -> list[tuple[Block, float]]:
    if not query.strip() or not blocks:
        return []
    corpus_tokens = [tokenize(block.text + " " + block.title) for block in blocks]
    query_tokens = tokenize(expand_query(query))
    idf = build_idf(corpus_tokens)
    query_vector = vectorize(query_tokens, idf)
    wants_beginning = asks_about_beginning(query)
    explicit_years = extract_years(query)

    scored = []
    for index, (block, tokens) in enumerate(zip(blocks, corpus_tokens)):
        vector = vectorize(tokens, idf)
        semantic = cosine(query_vector, vector)
        phrase_bonus = literal_bonus(query, block.text)
        beginning_bonus = 0.35 if wants_beginning and index < 8 else 0.0
        year_bonus = 0.05 if any(block.start_at.startswith(year) for year in explicit_years) else 0.0
        scored.append((block, semantic + phrase_bonus + beginning_bonus + year_bonus))
    scored.sort(key=lambda item: item[1], reverse=True)
    if len(explicit_years) >= 2:
        return diversify_by_year(scored, explicit_years, top_k)
    return [(block, score) for block, score in scored[:top_k] if score > 0]


def asks_about_beginning(query: str) -> bool:
    tokens = set(tokenize(query))
    beginning_words = {"comeco", "comecou", "inicio", "iniciou", "start", "started", "begin", "began", "first"}
    relationship_words = {"amizade", "friendship", "relacao", "relationship", "conversa", "conversation"}
    return bool(tokens & beginning_words) and bool(tokens & relationship_words)


def extract_years(query: str) -> list[str]:
    years = []
    for year in re.findall(r"\b20\d{2}\b", query):
        if year not in years:
            years.append(year)
    return years


def diversify_by_year(scored: list[tuple[Block, float]], years: list[str], top_k: int) -> list[tuple[Block, float]]:
    selected: list[tuple[Block, float]] = []
    seen_ids: set[int] = set()
    per_year = max(1, top_k // len(years))

    for year in years:
        matches = [(block, score) for block, score in scored if block.start_at.startswith(year)]
        for block, score in matches[:per_year]:
            selected.append((block, score))
            seen_ids.add(block.block_id)

    for block, score in scored:
        if len(selected) >= top_k:
            break
        if block.block_id not in seen_ids:
            selected.append((block, score))
            seen_ids.add(block.block_id)

    return [(block, score) for block, score in selected if score > 0]


def expand_query(query: str) -> str:
    synonyms = {
        "relacionamento": "amizade interesse carinho intimidade conexão confiança atenção reciprocidade",
        "conexao": "conexão amizade interesse carinho intimidade confiança atenção reciprocidade",
        "interesse": "conexão carinho atenção curiosidade reciprocidade atração",
        "amor": "romance carinho interesse atração saudade afeto",
        "red flags": "alerta risco desconforto limite insistência desequilíbrio",
        "ciumes": "ciúmes insegurança atenção exclusividade",
        "musica": "música instruments song suno ableton artista",
        "arte": "art painting sculpture video mixed media creative",
        "portugal": "lisbon lisboa português IADE universidade mestrado",
        "python": "programação tecnologia estudo aprender curso",
        "viagem": "cruzeiro navio juneau alaska porto",
    }
    lowered = query.lower()
    additions = [words for key, words in synonyms.items() if key in lowered]
    return " ".join([query, *additions])


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[\wÀ-ÿ']{2,}", text)
    return [normalize_token(word) for word in words if any(char.isalpha() for char in word)]


def normalize_token(word: str) -> str:
    normalized = unicodedata.normalize("NFKD", word.lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def build_idf(corpus_tokens: list[list[str]]) -> dict[str, float]:
    doc_count = len(corpus_tokens)
    freqs: defaultdict[str, int] = defaultdict(int)
    for tokens in corpus_tokens:
        for token in set(tokens):
            freqs[token] += 1
    return {token: math.log((doc_count + 1) / (count + 1)) + 1 for token, count in freqs.items()}


def vectorize(tokens: Iterable[str], idf: dict[str, float]) -> dict[str, float]:
    counts = Counter(token for token in tokens if token not in STOPWORDS)
    total = sum(counts.values()) or 1
    return {token: (count / total) * idf.get(token, 1.0) for token, count in counts.items()}


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    overlap = set(left) & set(right)
    dot = sum(left[token] * right[token] for token in overlap)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def literal_bonus(query: str, text: str) -> float:
    lowered = text.lower()
    query_terms = [term for term in tokenize(query) if term not in STOPWORDS]
    if not query_terms:
        return 0.0
    hits = sum(1 for term in query_terms if term in lowered)
    return min(0.25, hits / len(query_terms) * 0.18)


def timeline_by_day(messages: list[Message]) -> list[dict[str, object]]:
    groups: defaultdict[str, list[Message]] = defaultdict(list)
    for message in messages:
        key = message.timestamp.strftime("%Y-%m-%d") if message.timestamp else "no date"
        groups[key].append(message)
    timeline = []
    for day, items in sorted(groups.items()):
        senders = Counter(message.sender for message in items)
        sample_words = [word for message in items for word in tokenize(message.text) if word not in STOPWORDS]
        timeline.append(
            {
                "date": day,
                "messages": len(items),
                "senders": dict(senders),
                "topics": ", ".join(word for word, _count in Counter(sample_words).most_common(6)),
                "first": items[0].text[:180],
            }
        )
    return timeline


def build_context(results: list[tuple[Block, float]]) -> str:
    parts = []
    for block, score in results:
        date_label = format_context_date(block.start_at, block.end_at)
        parts.append(
            f"Conversation excerpt from {date_label} | relevance {score:.2f}\n{block.text}"
        )
    return "\n\n---\n\n".join(parts)


def format_context_date(start_at: str, end_at: str) -> str:
    start = parse_iso_datetime(start_at)
    end = parse_iso_datetime(end_at)
    if not start:
        return "an unknown date"
    start_label = start.strftime("%B %d, %Y")
    if end and end.date() != start.date():
        return f"{start_label} to {end.strftime('%B %d, %Y')}"
    return start_label


def parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def ask_ai(
    question: str,
    results: list[tuple[Block, float]],
    provider: str,
    model: str,
    temperature: float = 0.35,
) -> str:
    provider = provider.lower()
    if provider == "gemini":
        return ask_gemini(question, results, model, temperature)
    if provider == "groq":
        return ask_groq(question, results, model, temperature)

    groq_answer = ask_groq(question, results, model, temperature)
    if is_friendly_rate_limit_text(groq_answer) and os.getenv("GEMINI_API_KEY", "").strip():
        return ask_gemini(question, results, "gemini-2.5-flash", temperature)
    return groq_answer


def build_chat_prompt(question: str, results: list[tuple[Block, float]]) -> tuple[str, str]:
    context = build_context(results)
    system_prompt = (
        "You are a private bot that knows a WhatsApp conversation. "
        "Answer in the same language as the user's question. "
        "Be natural, emotionally careful, and do not invent facts. "
        "You may analyze relationship patterns when asked, but treat interpretations "
        "as hypotheses, not certainties. Mention month, day, and year when useful. "
        "Never mention internal excerpt IDs, block numbers, relevance scores, or retrieval mechanics. "
        "If the retrieved context does not support the answer, say that clearly."
    )
    user_prompt = f"Question: {question}\n\nRelevant conversation excerpts:\n{context}"
    return system_prompt, user_prompt


def ask_groq(question: str, results: list[tuple[Block, float]], model: str, temperature: float = 0.35) -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return "Set the GROQ_API_KEY environment variable to enable the bot."

    system_prompt, user_prompt = build_chat_prompt(question, results)
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]
    if Groq is not None:
        try:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            return completion.choices[0].message.content.strip()
        except Exception as exc:
            if is_rate_limit_error(exc):
                return friendly_rate_limit_message(exc)
            return "The AI service could not answer right now. Please try again in a moment."

    payload = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
    }
    request = Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "WhatsAppMemoryBot/0.1",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 429 or "rate_limit" in detail.lower():
            return friendly_rate_limit_message(detail)
        return "The AI service returned an error. Please try again later."
    except URLError:
        return "Could not connect to the AI service. Check the server connection and try again."
    except TimeoutError:
        return "The AI service took too long to respond. Try again with fewer retrieved excerpts."

    return data["choices"][0]["message"]["content"].strip()


def ask_gemini(question: str, results: list[tuple[Block, float]], model: str, temperature: float = 0.35) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return "Set the GEMINI_API_KEY environment variable to use Gemini."

    system_prompt, user_prompt = build_chat_prompt(question, results)
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={api_key}"
    )
    payload = {
        "systemInstruction": {
            "parts": [{"text": system_prompt}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
        },
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 429 or "quota" in detail.lower():
            return (
                "Gemini has reached its current usage limit. Try again later, "
                "lower 'Retrieved excerpts', or switch back to Groq."
            )
        if exc.code == 404 or "not found" in detail.lower():
            return (
                "Gemini could not find the selected model. Try gemini-2.5-flash or "
                "gemini-2.0-flash, and make sure the Gemini API is enabled for this key."
            )
        if exc.code in {400, 403}:
            return (
                "Gemini could not answer with the current configuration. Check GEMINI_API_KEY, "
                "confirm the Gemini API is enabled in Google AI Studio, and try gemini-2.5-flash."
            )
        return f"Gemini returned an error ({exc.code}). Please try again later."
    except URLError:
        return "Could not connect to Gemini. Check the server connection and try again."
    except TimeoutError:
        return "Gemini took too long to respond. Try again with fewer retrieved excerpts."

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError):
        return "Gemini did not return a usable answer. Try a different model or fewer retrieved excerpts."


def is_rate_limit_error(exc: Exception) -> bool:
    if RateLimitError is not None and isinstance(exc, RateLimitError):
        return True
    text = str(exc).lower()
    return "429" in text or "rate_limit" in text or "rate limit" in text


def is_friendly_rate_limit_text(text: str) -> bool:
    return text.startswith("The AI service has reached its current usage limit.")


def friendly_rate_limit_message(error: object) -> str:
    wait_text = extract_retry_wait(str(error))
    wait_sentence = f" Please try again in about {wait_text}." if wait_text else " Please try again in a few minutes."
    return (
        "The AI service has reached its current usage limit."
        f"{wait_sentence}\n\n"
        "What you can do now:\n"
        "- Try again later.\n"
        "- Lower 'Retrieved excerpts' to 3 or 4 and ask again.\n"
        "- Use a smaller/faster model like llama-3.1-8b-instant for lighter questions.\n"
        "- If this happens often, the app owner needs to increase the Groq plan or daily token limit."
    )


def extract_retry_wait(text: str) -> str:
    minute_match = re.search(r"try again in\s+([0-9.]+)m", text, flags=re.IGNORECASE)
    if minute_match:
        minutes = max(1, round(float(minute_match.group(1))))
        return f"{minutes} minutes"
    match = re.search(r"try again in\s+([0-9.]+)s", text, flags=re.IGNORECASE)
    if not match:
        return ""
    seconds = float(match.group(1))
    if seconds < 60:
        return f"{round(seconds)} seconds"
    minutes = max(1, round(seconds / 60))
    return f"{minutes} minutes"
