-- ให้ผู้ใช้เลือกซ่อน/แสดงข้อมูลติดต่อแต่ละช่องทางจากคนอื่นได้
-- รันสคริปต์นี้ใน Supabase Dashboard > SQL Editor

alter table public.users_profile add column if not exists show_phone boolean not null default true;
alter table public.users_profile add column if not exists show_line boolean not null default true;
alter table public.users_profile add column if not exists show_facebook boolean not null default true;
alter table public.users_profile add column if not exists show_address boolean not null default true;
