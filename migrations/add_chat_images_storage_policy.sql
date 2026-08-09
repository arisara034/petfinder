-- แก้ error "new row violates row-level security policy" ตอนอัปโหลดรูปแชท
-- สาเหตุ: bucket "chat-images" ถูกสร้างแล้ว แต่ยังไม่มี policy อนุญาตให้ upload/read
-- รันสคริปต์นี้ใน Supabase Dashboard > SQL Editor (หลังจากสร้าง bucket "chat-images" แล้ว)

create policy "Public upload for chat-images"
on storage.objects for insert
to public
with check (bucket_id = 'chat-images');

create policy "Public read for chat-images"
on storage.objects for select
to public
using (bucket_id = 'chat-images');
