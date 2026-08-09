-- ระบบแชทระหว่างผู้ใช้ (1:1) — conversations + messages
-- รันสคริปต์นี้ใน Supabase Dashboard > SQL Editor

create table if not exists public.conversations (
    id bigint generated always as identity primary key,
    user_a uuid not null,
    user_b uuid not null,
    last_message text,
    last_message_at timestamptz default now(),
    created_at timestamptz default now(),
    unique (user_a, user_b)
);

create table if not exists public.messages (
    id bigint generated always as identity primary key,
    conversation_id bigint not null references public.conversations(id) on delete cascade,
    sender_id uuid not null,
    content text not null,
    created_at timestamptz default now(),
    read_at timestamptz
);

create index if not exists idx_messages_conversation on public.messages(conversation_id, created_at);
create index if not exists idx_conversations_user_a on public.conversations(user_a);
create index if not exists idx_conversations_user_b on public.conversations(user_b);

-- เปิดใช้งาน Realtime สำหรับตาราง messages
-- ถ้าคำสั่งนี้ error (เช่น "already member of publication") ให้ข้ามไปได้เลย
-- หรือไปเปิดเองที่ Database > Replication > เลือกตาราง messages ใน Dashboard
alter publication supabase_realtime add table public.messages;
