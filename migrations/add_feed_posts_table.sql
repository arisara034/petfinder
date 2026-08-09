-- ระบบฟีดอัปเดตชีวิตประจำวัน (เช่น "วันนี้พาหมาไปเดินเล่น" พร้อมรูป)
-- แสดงในหน้าโปรไฟล์ของแต่ละคน กดถูกใจ/คอมเมนต์ได้เหมือนโพสต์ทั่วไป
-- รันสคริปต์นี้ใน Supabase Dashboard > SQL Editor

create table if not exists public.feed_posts (
    id bigint generated always as identity primary key,
    user_id uuid not null,
    content text,
    image_url text,
    images jsonb,
    created_at timestamptz default now()
);

create index if not exists idx_feed_posts_user on public.feed_posts(user_id, created_at desc);

-- สร้าง storage bucket สำหรับรูปในฟีด (public bucket)
insert into storage.buckets (id, name, public)
values ('feed-images', 'feed-images', true)
on conflict (id) do nothing;

create policy "Public upload for feed-images"
on storage.objects for insert
to public
with check (bucket_id = 'feed-images');

create policy "Public read for feed-images"
on storage.objects for select
to public
using (bucket_id = 'feed-images');
