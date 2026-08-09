-- เพิ่มพิกัดแผนที่ให้ประกาศหาบ้าน (adopt_posts) เหมือนกับประกาศหายและแจ้งพบ
-- รันสคริปต์นี้ใน Supabase Dashboard > SQL Editor

alter table public.adopt_posts add column if not exists latitude double precision;
alter table public.adopt_posts add column if not exists longitude double precision;
