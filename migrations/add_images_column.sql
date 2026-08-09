-- เพิ่มคอลัมน์ images (array ของ URL รูปภาพ) ให้ทั้ง 3 ตารางประกาศ
-- รันสคริปต์นี้ใน Supabase Dashboard > SQL Editor

alter table public.lost_posts   add column if not exists images jsonb default '[]'::jsonb;
alter table public.found_posts  add column if not exists images jsonb default '[]'::jsonb;
alter table public.adopt_posts  add column if not exists images jsonb default '[]'::jsonb;
