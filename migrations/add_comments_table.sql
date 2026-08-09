-- ระบบความคิดเห็นใต้โพสต์
-- รันสคริปต์นี้ใน Supabase Dashboard > SQL Editor

create table if not exists public.comments (
    id bigint generated always as identity primary key,
    post_type text not null,
    post_id bigint not null,
    user_id uuid not null,
    content text not null,
    created_at timestamptz default now()
);

create index if not exists idx_comments_post on public.comments(post_type, post_id, created_at);
