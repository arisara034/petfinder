-- รองรับการส่งรูปภาพในแชท
-- รันสคริปต์นี้ใน Supabase Dashboard > SQL Editor

alter table public.messages add column if not exists image_url text;

-- นอกจากนี้ต้องสร้าง Storage bucket ชื่อ "chat-images" (ตั้งเป็น Public bucket)
-- ที่ Supabase Dashboard > Storage > New bucket ด้วยครับ (ไม่สามารถสร้างผ่าน SQL ได้)
