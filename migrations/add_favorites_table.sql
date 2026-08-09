-- ระบบกดถูกใจ/รายการโปรดของโพสต์
-- รันสคริปต์นี้ใน Supabase Dashboard > SQL Editor

create table if not exists public.favorites (
    id bigint generated always as identity primary key,
    post_type text not null,
    post_id bigint not null,
    user_id uuid not null,
    created_at timestamptz default now(),
    unique (post_type, post_id, user_id)
);

create index if not exists idx_favorites_user on public.favorites(user_id);
