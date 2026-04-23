from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from supabase import Client, create_client

from whatsapp_memory_core import Block, Message


def fetch_all_rows(
    client: Client,
    table: str,
    columns: str,
    filters: dict[str, Any] | None = None,
    order_by: str | None = None,
    page_size: int = 1000,
) -> list[dict[str, Any]]:
    filters = filters or {}
    start = 0
    rows: list[dict[str, Any]] = []

    while True:
        query = client.table(table).select(columns)
        for key, value in filters.items():
            query = query.eq(key, value)
        if order_by:
            query = query.order(order_by)
        batch = query.range(start, start + page_size - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size

    return rows


def supabase_configured() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY"))


def supabase_url_has_rest_path() -> bool:
    return os.getenv("SUPABASE_URL", "").rstrip("/").endswith("/rest/v1")


def configured_supabase_host() -> str:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    return urlparse(url).netloc or "not configured"


def get_client() -> Client:
    url = os.environ["SUPABASE_URL"].rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    anon_key = os.environ["SUPABASE_ANON_KEY"]
    return create_client(url, anon_key)


def sign_in(email: str, password: str) -> dict[str, Any]:
    response = get_client().auth.sign_in_with_password({"email": email.strip(), "password": password})
    return {"user": response.user, "session": response.session}


def sign_up(email: str, password: str) -> dict[str, Any]:
    response = get_client().auth.sign_up({"email": email.strip(), "password": password})
    return {"user": response.user, "session": response.session}


def sign_out() -> None:
    get_client().auth.sign_out()


def session_client(access_token: str, refresh_token: str) -> Client:
    client = get_client()
    client.auth.set_session(access_token, refresh_token)
    return client


def save_conversation(
    client: Client,
    user_id: str,
    source_name: str,
    messages: list[Message],
    blocks: list[Block],
) -> str:
    existing = (
        client.table("conversations")
        .select("id")
        .eq("user_id", user_id)
        .eq("source_name", source_name)
        .limit(1)
        .execute()
    )
    payload = {
        "user_id": user_id,
        "source_name": source_name,
        "message_count": len(messages),
        "block_count": len(blocks),
        "indexed_at": datetime.utcnow().isoformat(),
    }
    if existing.data:
        conversation_id = existing.data[0]["id"]
        client.table("conversations").update(payload).eq("id", conversation_id).execute()
        clear_conversation(client, conversation_id)
    else:
        created = client.table("conversations").insert(payload).execute()
        conversation_id = created.data[0]["id"]

    message_rows = [
        {
            "conversation_id": conversation_id,
            "position": index,
            "timestamp": message.timestamp.isoformat(sep=" ", timespec="minutes") if message.timestamp else None,
            "sender": message.sender,
            "text": message.text,
            "raw": message.raw,
        }
        for index, message in enumerate(messages)
    ]
    block_rows = [
        {
            "conversation_id": conversation_id,
            "position": index,
            "start_at": block.start_at or None,
            "end_at": block.end_at or None,
            "senders": block.senders,
            "title": block.title,
            "text": block.text,
            "message_count": block.message_count,
        }
        for index, block in enumerate(blocks)
    ]
    bulk_insert(client, "messages", message_rows)
    bulk_insert(client, "blocks", block_rows)
    return conversation_id


def clear_conversation(client: Client, conversation_id: str) -> None:
    client.table("messages").delete().eq("conversation_id", conversation_id).execute()
    client.table("blocks").delete().eq("conversation_id", conversation_id).execute()


def bulk_insert(client: Client, table: str, rows: list[dict[str, Any]], chunk_size: int = 500) -> None:
    for start in range(0, len(rows), chunk_size):
        client.table(table).insert(rows[start : start + chunk_size]).execute()


def list_conversations(client: Client, user_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("conversations")
        .select("id, source_name, message_count, block_count, indexed_at")
        .eq("user_id", user_id)
        .order("indexed_at", desc=True)
        .execute()
    )
    return response.data or []


def load_conversation(client: Client, conversation_id: str) -> tuple[dict[str, str], list[Message], list[Block]]:
    conversation = client.table("conversations").select("*").eq("id", conversation_id).single().execute().data
    message_rows = fetch_all_rows(
        client,
        "messages",
        "timestamp, sender, text, raw",
        filters={"conversation_id": conversation_id},
        order_by="position",
    )
    block_rows = fetch_all_rows(
        client,
        "blocks",
        "position, start_at, end_at, senders, title, text, message_count",
        filters={"conversation_id": conversation_id},
        order_by="position",
    )
    messages = [
        Message(
            timestamp=datetime.fromisoformat(row["timestamp"]) if row.get("timestamp") else None,
            sender=row["sender"],
            text=row["text"],
            raw=row["raw"],
        )
        for row in message_rows
    ]
    blocks = [
        Block(
            block_id=index + 1,
            start_at=row.get("start_at") or "",
            end_at=row.get("end_at") or "",
            senders=row.get("senders") or "",
            title=row.get("title") or "",
            text=row["text"],
            message_count=row.get("message_count") or 0,
        )
        for index, row in enumerate(block_rows)
    ]
    meta = {
        "source_name": conversation.get("source_name", "no source"),
        "message_count": str(conversation.get("message_count", 0)),
        "block_count": str(conversation.get("block_count", 0)),
        "indexed_at": str(conversation.get("indexed_at", "")),
    }
    return meta, messages, blocks
