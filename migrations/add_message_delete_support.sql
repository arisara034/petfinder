-- รองรับการลบ/ยกเลิกข้อความในแชท (soft delete)
-- รันสคริปต์นี้ใน Supabase Dashboard > SQL Editor

alter table public.messages add column if not exists deleted_at timestamptz;
