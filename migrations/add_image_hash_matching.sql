-- ระบบจับคู่ AI ระหว่างประกาศสัตว์หาย (lost) กับประกาศพบสัตว์ (found)
-- เก็บลายนิ้วมือของรูปภาพ (perceptual hash) ไว้เทียบความเหมือน
-- รันสคริปต์นี้ใน Supabase Dashboard > SQL Editor

alter table public.lost_posts add column if not exists image_hash text;
alter table public.found_posts add column if not exists image_hash text;

create index if not exists idx_lost_posts_type on public.lost_posts(type);
create index if not exists idx_found_posts_type on public.found_posts(type);
