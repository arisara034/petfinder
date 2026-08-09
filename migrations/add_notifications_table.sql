-- ระบบแจ้งเตือนเมื่อมีคนกดถูกใจ/แสดงความคิดเห็นในโพสต์ของเรา
-- รันสคริปต์นี้ใน Supabase Dashboard > SQL Editor

create table if not exists public.notifications (
    id bigint generated always as identity primary key,
    recipient_id uuid not null,
    actor_id uuid not null,
    type text not null, -- 'like' หรือ 'comment'
    post_type text not null,
    post_id bigint not null,
    read_at timestamptz,
    created_at timestamptz default now()
);

create index if not exists idx_notifications_recipient on public.notifications(recipient_id, created_at desc);
