create extension if not exists "pgcrypto";

create table if not exists public.conversations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    source_name text not null,
    message_count integer not null default 0,
    block_count integer not null default 0,
    indexed_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    constraint conversations_message_count_nonnegative check (message_count >= 0),
    constraint conversations_block_count_nonnegative check (block_count >= 0),
    constraint conversations_user_source_unique unique (user_id, source_name)
);

create table if not exists public.messages (
    id bigserial primary key,
    conversation_id uuid not null references public.conversations(id) on delete cascade,
    position integer not null,
    timestamp timestamptz,
    sender text not null,
    text text not null,
    raw text not null,
    constraint messages_position_nonnegative check (position >= 0),
    constraint messages_conversation_position_unique unique (conversation_id, position)
);

create table if not exists public.blocks (
    id bigserial primary key,
    conversation_id uuid not null references public.conversations(id) on delete cascade,
    position integer not null,
    start_at timestamptz,
    end_at timestamptz,
    senders text,
    title text,
    text text not null,
    message_count integer not null default 0,
    constraint blocks_position_nonnegative check (position >= 0),
    constraint blocks_message_count_nonnegative check (message_count >= 0),
    constraint blocks_conversation_position_unique unique (conversation_id, position)
);

create index if not exists conversations_user_id_idx on public.conversations(user_id);
create index if not exists conversations_user_id_source_name_idx on public.conversations(user_id, source_name);
create index if not exists messages_conversation_id_position_idx on public.messages(conversation_id, position);
create index if not exists blocks_conversation_id_position_idx on public.blocks(conversation_id, position);

revoke all on schema public from anon;
revoke all on public.conversations from anon;
revoke all on public.messages from anon;
revoke all on public.blocks from anon;
revoke all on public.conversations from authenticated;
revoke all on public.messages from authenticated;
revoke all on public.blocks from authenticated;

grant usage on schema public to authenticated;
grant select, insert, update, delete on public.conversations to authenticated;
grant select, insert, update, delete on public.messages to authenticated;
grant select, insert, update, delete on public.blocks to authenticated;
grant usage, select on sequence public.messages_id_seq to authenticated;
grant usage, select on sequence public.blocks_id_seq to authenticated;

alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.blocks enable row level security;
alter table public.conversations force row level security;
alter table public.messages force row level security;
alter table public.blocks force row level security;

drop policy if exists "Users can read their conversations" on public.conversations;
create policy "Users can read their conversations"
on public.conversations for select
using (auth.uid() = user_id);

drop policy if exists "Users can insert their conversations" on public.conversations;
create policy "Users can insert their conversations"
on public.conversations for insert
with check (auth.uid() = user_id);

drop policy if exists "Users can update their conversations" on public.conversations;
create policy "Users can update their conversations"
on public.conversations for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists "Users can delete their conversations" on public.conversations;
create policy "Users can delete their conversations"
on public.conversations for delete
using (auth.uid() = user_id);

drop policy if exists "Users can read their messages" on public.messages;
create policy "Users can read their messages"
on public.messages for select
using (
    exists (
        select 1 from public.conversations
        where conversations.id = messages.conversation_id
        and conversations.user_id = auth.uid()
    )
);

drop policy if exists "Users can insert their messages" on public.messages;
create policy "Users can insert their messages"
on public.messages for insert
with check (
    exists (
        select 1 from public.conversations
        where conversations.id = messages.conversation_id
        and conversations.user_id = auth.uid()
    )
);

drop policy if exists "Users can delete their messages" on public.messages;
create policy "Users can delete their messages"
on public.messages for delete
using (
    exists (
        select 1 from public.conversations
        where conversations.id = messages.conversation_id
        and conversations.user_id = auth.uid()
    )
);

drop policy if exists "Users can update their messages" on public.messages;
create policy "Users can update their messages"
on public.messages for update
using (
    exists (
        select 1 from public.conversations
        where conversations.id = messages.conversation_id
        and conversations.user_id = auth.uid()
    )
)
with check (
    exists (
        select 1 from public.conversations
        where conversations.id = messages.conversation_id
        and conversations.user_id = auth.uid()
    )
);

drop policy if exists "Users can read their blocks" on public.blocks;
create policy "Users can read their blocks"
on public.blocks for select
using (
    exists (
        select 1 from public.conversations
        where conversations.id = blocks.conversation_id
        and conversations.user_id = auth.uid()
    )
);

drop policy if exists "Users can insert their blocks" on public.blocks;
create policy "Users can insert their blocks"
on public.blocks for insert
with check (
    exists (
        select 1 from public.conversations
        where conversations.id = blocks.conversation_id
        and conversations.user_id = auth.uid()
    )
);

drop policy if exists "Users can delete their blocks" on public.blocks;
create policy "Users can delete their blocks"
on public.blocks for delete
using (
    exists (
        select 1 from public.conversations
        where conversations.id = blocks.conversation_id
        and conversations.user_id = auth.uid()
    )
);

drop policy if exists "Users can update their blocks" on public.blocks;
create policy "Users can update their blocks"
on public.blocks for update
using (
    exists (
        select 1 from public.conversations
        where conversations.id = blocks.conversation_id
        and conversations.user_id = auth.uid()
    )
)
with check (
    exists (
        select 1 from public.conversations
        where conversations.id = blocks.conversation_id
        and conversations.user_id = auth.uid()
    )
);
