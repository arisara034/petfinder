-- เพิ่มคอลัมน์ province (จังหวัด) และ district (อำเภอ/เขต) ให้ทั้ง 3 ตารางประกาศ
-- รันสคริปต์นี้ใน Supabase Dashboard > SQL Editor

alter table public.lost_posts   add column if not exists province text;
alter table public.lost_posts   add column if not exists district text;

alter table public.found_posts  add column if not exists province text;
alter table public.found_posts  add column if not exists district text;

alter table public.adopt_posts  add column if not exists province text;
alter table public.adopt_posts  add column if not exists district text;
