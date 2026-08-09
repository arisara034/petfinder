-- เพิ่มพิกัดที่อยู่ของผู้ใช้ (ปักหมุดในหน้าโปรไฟล์)
-- เพื่อใช้แจ้งเตือนเมื่อมีประกาศใหม่ในระดับอำเภอเดียวกัน
-- รันสคริปต์นี้ใน Supabase Dashboard > SQL Editor

alter table public.users_profile add column if not exists home_lat double precision;
alter table public.users_profile add column if not exists home_lng double precision;
alter table public.users_profile add column if not exists home_province text;
alter table public.users_profile add column if not exists home_district text;

create index if not exists idx_users_profile_home_area on public.users_profile(home_province, home_district);
