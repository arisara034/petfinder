-- เพิ่มช่องทางติดต่อ LINE และ Facebook ให้โปรไฟล์ผู้ใช้
-- รันสคริปต์นี้ใน Supabase Dashboard > SQL Editor

alter table public.users_profile add column if not exists line_id text;
alter table public.users_profile add column if not exists facebook text;
