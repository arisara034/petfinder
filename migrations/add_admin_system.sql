-- ระบบแอดมิน: สิทธิ์ผู้ใช้ (role), แบนผู้ใช้ (is_banned), และระบบรายงานโพสต์ (reports)
-- รันสคริปต์นี้ใน Supabase Dashboard > SQL Editor

-- 1. เพิ่มคอลัมน์ role และ is_banned ให้ตารางโปรไฟล์ผู้ใช้
alter table public.users_profile add column if not exists role text not null default 'user';
alter table public.users_profile add column if not exists is_banned boolean not null default false;

create index if not exists idx_users_profile_role on public.users_profile(role);

-- 2. ตารางรายงานโพสต์ (ผู้ใช้กดรายงานโพสต์ที่ไม่เหมาะสม แอดมินตรวจสอบภายหลัง)
create table if not exists public.reports (
    id bigint generated always as identity primary key,
    reporter_id uuid not null,
    post_type text not null,       -- 'adopt' | 'lost' | 'found'
    post_id bigint not null,
    reason text not null,
    status text not null default 'pending',  -- 'pending' | 'reviewed' | 'dismissed'
    created_at timestamptz default now()
);

create index if not exists idx_reports_status on public.reports(status, created_at);
create index if not exists idx_reports_post on public.reports(post_type, post_id);

-- 3. ตั้งให้บัญชีของคุณเป็นแอดมิน
-- แก้ 'you@example.com' เป็นอีเมลที่ใช้สมัครสมาชิกจริง แล้วรันแยกทีหลัง (หลังจากรันสคริปต์ด้านบนแล้ว):
--
-- update public.users_profile set role = 'admin'
-- where id = (select id from auth.users where email = 'you@example.com');
