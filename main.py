import os
import httpx
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Any
from dotenv import load_dotenv
from supabase import create_client, Client
from typing import Dict, Any
from fastapi import Header, HTTPException
from matching import compute_image_hash, compute_image_hash_from_bytes, hash_similarity_percent, combined_match_percent
from fastapi import File, UploadFile, Form
from datetime import datetime, timezone

# โหลดค่าจากไฟล์ .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("กรุณาตั้งค่า SUPABASE_URL และ SUPABASE_KEY ในไฟล์ .env ก่อนเริ่มทำงาน")

# 🔌 เชื่อมต่อ Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="PetFinder Unified Backend")

# 🔓 เปิด CORS เพื่อให้ฝั่ง React (Frontend) สามารถยิง API มาหาได้ครบทุกหน้าต่าง
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 📐 SECTION 1: PYDANTIC SCHEMAS (รองรับทั้ง camelCase และ snake_case 100%)
# ==========================================

# 1. โครงสร้างข้อมูลสำหรับหน้าหาบ้าน (Adopt)
class AdoptPostItem(BaseModel):
    name: str
    type: str
    gender: str
    breed: Optional[str] = "พันธุ์ทาง"
    age: str
    location_note: Optional[str] = None
    locationNote: Optional[str] = None  # รองรับเผื่อฟรอนต์เอนด์ส่งแบบอูฐ
    province: Optional[str] = None
    district: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    note: str
    contact: str
    status: Optional[str] = "กำลังหาบ้าน"
    image_url: Optional[str] = None
    imageUrl: Optional[str] = None   # รองรับเผื่อฟรอนต์เอนด์ส่งแบบอูฐ
    images: Optional[list[str]] = None
    user_id:str | None = None

# 2. โครงสร้างข้อมูลสำหรับหน้าตามหาสัตว์หาย (Lost)
class LostPostItem(BaseModel):
    name: str
    type: str
    gender: str
    breed: Optional[str] = "ไม่ระบุสายพันธุ์"
    reward: Optional[float] = 0.0
    lost_date: Optional[str] = None
    lostDate: Optional[str] = None      # รองรับเผื่อฟรอนต์เอนด์ส่งแบบอูฐ
    location_note: Optional[str] = None
    locationNote: Optional[str] = None  # รองรับเผื่อฟรอนต์เอนด์ส่งแบบอูฐ
    province: Optional[str] = None
    district: Optional[str] = None
    latitude: float
    longitude: float
    note: str
    image_url: Optional[str] = None
    imageUrl: Optional[str] = None     # รองรับเผื่อฟรอนต์เอนด์ส่งแบบอูฐ
    images: Optional[list[str]] = None
    status: Optional[str] = "กำลังตามหา"
    user_id:str | None = None

# 3. โครงสร้างข้อมูลสำหรับหน้าแจ้งพบสัตว์หลงทาง (Found)
class FoundPostItem(BaseModel):
    type: str
    breed: Optional[str] = "ไม่ระบุ"
    location_note: Optional[str] = None
    locationNote: Optional[str] = None  # รองรับเผื่อฟรอนต์เอนด์ส่งแบบอูฐ
    province: Optional[str] = None
    district: Optional[str] = None
    latitude: float
    longitude: float
    note: str
    image_url: Optional[str] = None
    imageUrl: Optional[str] = None     # รองรับเผื่อฟรอนต์เอนด์ส่งแบบอูฐ
    images: Optional[list[str]] = None
    status: Optional[str] = "รอเจ้าของติดต่อกลับ"
    user_id:str | None = None


# ==========================================
# 🔔 SECTION 1.5: แจ้งเตือนผู้ใช้ที่ปักหมุดที่อยู่ในอำเภอเดียวกันเมื่อมีประกาศใหม่
# ==========================================

def notify_nearby_users(post_type: str, province: str | None, district: str | None, poster_id: str, post_id):
    if not province or not district or not post_id:
        return
    try:
        nearby = supabase.table("users_profile") \
            .select("id") \
            .eq("home_province", province) \
            .eq("home_district", district) \
            .neq("id", poster_id) \
            .execute()

        rows = [
            {
                "recipient_id": u["id"],
                "actor_id": poster_id,
                "type": "nearby",
                "post_type": post_type,
                "post_id": post_id,
            }
            for u in (nearby.data or [])
        ]
        if rows:
            supabase.table("notifications").insert(rows).execute()
    except Exception as e:
        print(f"❌ NEARBY NOTIFY ERROR: {str(e)}")


# ==========================================
# 🤖 SECTION 1.6: AI จับคู่รูปสัตว์หาย (lost) กับสัตว์ที่พบ (found)
# ==========================================

MATCH_NOTIFY_THRESHOLD = 55.0  # % ความเหมือนรวม (รูปภาพ + ช่วงเวลา) ขั้นต่ำที่จะแจ้งเตือนว่าอาจเจอคู่กัน

def find_and_notify_matches(new_post_type: str, new_post_id, animal_type: str, image_hash, poster_id: str, new_post_date):
    """
    เทียบรูปโพสต์ใหม่กับโพสต์ฝั่งตรงข้าม (lost<->found ชนิดสัตว์เดียวกัน) โดยรวมคะแนนความเหมือนของรูปภาพ
    กับความสอดคล้องของช่วงเวลาที่หาย/พบ แล้วแจ้งเตือนเจ้าของโพสต์เดิมถ้าคล้ายกันมากพอ
    """
    if not image_hash or not new_post_id:
        return
    opposite_type = "found" if new_post_type == "lost" else "lost"
    opposite_table = "found_posts" if new_post_type == "lost" else "lost_posts"
    # lost_posts เก็บวันที่หายไว้ที่ lost_date, found_posts ไม่มีวันที่ระบุ ใช้ created_at (วันที่โพสต์) แทนวันที่พบ
    date_field = "lost_date" if opposite_table == "lost_posts" else "created_at"
    try:
        candidates = supabase.table(opposite_table) \
            .select(f"id, user_id, image_hash, {date_field}") \
            .eq("type", animal_type) \
            .execute().data or []

        for c in candidates:
            if not c.get("image_hash") or not c.get("user_id") or c["user_id"] == poster_id:
                continue
            img_score = hash_similarity_percent(image_hash, c["image_hash"])
            if new_post_type == "lost":
                lost_date_str, found_date_str = new_post_date, c.get(date_field)
            else:
                lost_date_str, found_date_str = c.get(date_field), new_post_date
            combined_score = combined_match_percent(img_score, lost_date_str, found_date_str)
            if combined_score >= MATCH_NOTIFY_THRESHOLD:
                # แจ้งเตือนเจ้าของโพสต์เดิม (ฝั่งตรงข้าม) ว่ามีโพสต์ใหม่ที่ AI ตรวจพบว่าอาจตรงกับของเขา
                supabase.table("notifications").insert({
                    "recipient_id": c["user_id"],
                    "actor_id": poster_id,
                    "type": "match",
                    "post_type": opposite_type,
                    "post_id": c["id"],
                }).execute()
    except Exception as e:
        print(f"❌ MATCH NOTIFY ERROR: {str(e)}")


# ==========================================
# 📌 SECTION 2: ADOPT ENDPOINTS (ระบบประกาศหาบ้าน)
# ==========================================

@app.get("/api/adopt")
def get_adopt_posts():
    try:
        response = supabase.table("adopt_posts").select("*").order("created_at", descending=True).execute()
        return response.data
    except Exception as e:
        try:
            response = supabase.table("adopt_posts").select("*").execute()
            return response.data
        except Exception as inner_e:
            raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการดึงข้อมูลหาบ้าน: {str(inner_e)}")

@app.post("/api/adopt")
def create_adopt_post(item: AdoptPostItem, authorization: str = Header(None)): # 1. รับ Token
    try:
        # 2. แกะ user_id จาก Token
        if not authorization:
            raise HTTPException(status_code=401, detail="โปรดเข้าสู่ระบบก่อน")
            
        token = authorization.replace("Bearer ", "")
        user_response = supabase.auth.get_user(token)
        user_id = user_response.user.id

        final_location = item.location_note if item.location_note else item.locationNote
        final_images = item.images if item.images else ([item.image_url] if item.image_url else ([item.imageUrl] if item.imageUrl else []))
        final_image = final_images[0] if final_images else None

        data_to_insert = {
            "name": item.name,
            "type": item.type,
            "gender": item.gender,
            "breed": item.breed if item.breed else "พันธุ์ทาง",
            "location_note": final_location if final_location else "ไม่ระบุสถานที่",
            "province": item.province,
            "district": item.district,
            "latitude": item.latitude,
            "longitude": item.longitude,
            "note": item.note,
            "contact": item.contact,
            "status": item.status if item.status else "กำลังหาบ้าน",
            "image_url": final_image,
            "images": final_images,
            "user_id": user_id  # <--- 3. เพิ่มบรรทัดนี้ครับ!
        }
        
        print("📤 ข้อมูลที่จะ Insert ลง DB:", data_to_insert)

        response = supabase.table("adopt_posts").insert(data_to_insert).execute()

        new_post_id = response.data[0]["id"] if response.data else None
        notify_nearby_users("adopt", item.province, item.district, user_id, new_post_id)

        return {"status": "success", "message": "ลงประกาศหาบ้านสำเร็จ 🎉", "data": response.data}
        
    except Exception as e:
        import traceback
        traceback.print_exc() 
        raise HTTPException(status_code=500, detail=str(e))
    


# ==========================================
# 📌 SECTION 3: LOST ENDPOINTS (ระบบตามหาสัตว์หาย)
# ==========================================

@app.get("/api/lost")
def get_lost_posts():
    try:
        response = supabase.table("lost_posts").select("*").order("created_at", descending=True).execute()
        return response.data
    except Exception as e:
        try:
            response = supabase.table("lost_posts").select("*").execute()
            return response.data
        except Exception as inner_e:
            raise HTTPException(status_code=500, detail=f"ดึงข้อมูลสัตว์หายล้มเหลว: {str(inner_e)}")

@app.post("/api/lost")
def create_lost_post(item: LostPostItem, authorization: str = Header(None)):
    try:

        token = authorization.replace("Bearer ", "")
        user_response = supabase.auth.get_user(token)
        user_id = user_response.user.id
    
        final_date = item.lost_date if item.lost_date else item.lostDate
        final_location = item.location_note if item.location_note else item.locationNote
        final_images = item.images if item.images else ([item.image_url] if item.image_url else ([item.imageUrl] if item.imageUrl else []))
        final_image = final_images[0] if final_images else None
        final_reward = int(item.reward) if item.reward is not None else 0
        image_hash = compute_image_hash(final_image)

        data_to_insert = {
            "name": item.name,
            "type": item.type,
            "gender": item.gender,
            "breed": item.breed if item.breed else "ไม่ระบุสายพันธุ์",
            "reward": final_reward,
            "lost_date": final_date if final_date else "ไม่ระบุวัน",
            "location_note": final_location if final_location else "ไม่ระบุสถานที่",
            "province": item.province,
            "district": item.district,
            "latitude": item.latitude,
            "longitude": item.longitude,
            "note": item.note,
            "image_url": final_image,
            "images": final_images,
            "status": item.status if item.status else "กำลังตามหา",
            "user_id": user_id,
            "image_hash": image_hash
        }
        response = supabase.table("lost_posts").insert(data_to_insert).execute()

        new_post_id = response.data[0]["id"] if response.data else None
        notify_nearby_users("lost", item.province, item.district, user_id, new_post_id)
        find_and_notify_matches("lost", new_post_id, item.type, image_hash, user_id, final_date)

        return {"status": "success", "message": "ลงประกาศตามหาสำเร็จ 🎉", "data": response.data}
    except Exception as e:
        print(f"❌ DB POST ERROR [Lost]: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ไม่สามารถบันทึกข้อมูลสัตว์หายได้: {str(e)}")


# ==========================================
# 📌 SECTION 4: FOUND ENDPOINTS (ระบบแจ้งพบสัตว์หลงทาง)
# ==========================================

@app.get("/api/found")
def get_found_posts():
    try:
        response = supabase.table("found_posts").select("*").order("created_at", descending=True).execute()
        return response.data
    except Exception as e:
        try:
            response = supabase.table("found_posts").select("*").execute()
            return response.data
        except Exception as inner_e:
            raise HTTPException(status_code=500, detail=f"ดึงข้อมูลเบาะแสสัตว์หลงทางล้มเหลว: {str(inner_e)}")

@app.post("/api/found")
def create_found_post(item: FoundPostItem, authorization: str = Header(None)):
    try:

        token = authorization.replace("Bearer ", "")
        user_response = supabase.auth.get_user(token)
        user_id = user_response.user.id

        final_location = item.location_note if item.location_note else item.locationNote
        final_images = item.images if item.images else ([item.image_url] if item.image_url else ([item.imageUrl] if item.imageUrl else []))
        final_image = final_images[0] if final_images else None
        image_hash = compute_image_hash(final_image)

        data_to_insert = {
            "type": item.type,
            "breed": item.breed if item.breed else "ไม่ระบุ",
            "location_note": final_location if final_location else "ไม่ระบุสถานที่",
            "province": item.province,
            "district": item.district,
            "latitude": item.latitude,
            "longitude": item.longitude,
            "note": item.note,
            "image_url": final_image,
            "images": final_images,
            "status": item.status if item.status else "รอเจ้าของติดต่อกลับ",
            "user_id":user_id,
            "image_hash": image_hash
        }
        response = supabase.table("found_posts").insert(data_to_insert).execute()

        new_post_id = response.data[0]["id"] if response.data else None
        notify_nearby_users("found", item.province, item.district, user_id, new_post_id)
        found_at = datetime.now(timezone.utc).isoformat()
        find_and_notify_matches("found", new_post_id, item.type, image_hash, user_id, found_at)

        return {"status": "success", "message": "ส่งข้อมูลแจ้งพบสัตว์เลี้ยงสำเร็จ 🐾", "data": response.data}
    except Exception as e:
        print(f"❌ DB POST ERROR [Found]: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ไม่สามารถบันทึกข้อมูลแจ้งพบสัตว์หลงทางได้: {str(e)}")


# ==========================================
# 🔐 SECTION 5: AUTHENTICATION & USER PROFILES (ระบบสมาชิก - แก้ไขสมบูรณ์)
# ==========================================

# โครงสร้างสำหรับการรับข้อมูลจากหน้าสมัครสมาชิก (Register)
class RegisterSchema(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None # รองรับเผื่อแผ่สไตล์ snake_case
    phone: Optional[Any] = None

# โครงสร้างสำหรับรับข้อมูลหน้าล็อกอิน (Login)
class LoginSchema(BaseModel):
    email: str
    password: str

# โครงสร้างสำหรับการอัปเดตข้อมูลโปรไฟล์ (Update Profile)
class UpdateProfileSchema(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatarUrl: Optional[str] = None
    address: Optional[str] = None

# 1. API สมัครสมาชิก (Register)
@app.post("/api/auth/register")
def register_user(item: RegisterSchema):
    try:
        # สมัครสมาชิกเข้าไปที่ระบบ Auth กลางของ Supabase
        auth_response = supabase.auth.sign_up({
    "email": item.email,
    "password": item.password,
    "options": {
        "data": {
            "full_name": item.full_name,
            "phone": str(item.phone) # ส่งข้อมูลที่นี่
        }
    }
})
        if not auth_response.user:
            raise HTTPException(status_code=400, detail="สมัครสมาชิกล้มเหลว กรุณาลองใหม่อีกครั้ง")

        # รวมร่างตัวแปรให้หยิบใช้ได้ทั้งสองสไตล์
        final_name = item.full_name

        # บันทึกข้อมูลเสริมลงในตารางข้อมูลส่วนตัว (users_profile)
       
        return {"status": "success", "message": "สมัครสมาชิกสำเร็จเรียบร้อย! 🎉"}

    except Exception as e:
        print(f"❌ REGISTER ERROR: {str(e)}")
        raise HTTPException(status_code=400, detail=f"ไม่สามารถสมัครสมาชิกได้: {str(e)}")


# 2. API เข้าสู่ระบบ (Login)
@app.post("/api/auth/login")
def login_user(item: LoginSchema):
    try:
        # สั่งให้ Supabase Auth ตรวจสอบรหัสผ่าน
        session_response = supabase.auth.sign_in_with_password({
            "email": item.email,
            "password": item.password
        })

        return {
            "status": "success",
            "message": "เข้าสู่ระบบสำเร็จ",
            "token": session_response.session.access_token,
            "user_id": session_response.user.id,
            "email": session_response.user.email
        }

    except Exception as e:
        print(f"❌ LOGIN ERROR: {str(e)}")
        raise HTTPException(status_code=401, detail="อีเมลหรือรหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง")


# 3. API ดึงข้อมูลโปรไฟล์ (Get Profile)
@app.get("/api/auth/profile/{user_id}")
def get_user_profile(user_id: str):
    try:
        response = supabase.table("users_profile").select("*").eq("id", user_id).single().execute()
        return response.data
    except Exception as e:
        print(f"❌ FETCH PROFILE ERROR: {str(e)}")
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลโปรไฟล์ของผู้ใช้งานนี้")


# 4. API อัปเดตข้อมูลโปรไฟล์ (Update Profile)
@app.put("/api/auth/profile/{user_id}")
def update_user_profile(user_id: str, item: UpdateProfileSchema):
    try:
        final_name = item.fullName if item.fullName else item.full_name

        update_data = {}
        if final_name is not None: update_data["full_name"] = final_name
        if item.phone is not None: update_data["phone"] = item.phone
        if item.avatarUrl is not None: update_data["avatar_url"] = item.avatarUrl
        if item.address is not None: update_data["address"] = item.address

        if not update_data:
            return {"status": "no_change", "message": "ไม่มีข้อมูลใดเปลี่ยนแปลง"}

        response = supabase.table("users_profile").update(update_data).eq("id", user_id).execute()
        return {"status": "success", "message": "อัปเดตโปรไฟล์เรียบร้อยครับ ✨", "data": response.data}

    except Exception as e:
        print(f"❌ UPDATE PROFILE ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ไม่สามารถอัปเดตข้อมูลโปรไฟล์ได้: {str(e)}")
    
  # ==========================================
# 🔐 SECTION 6: Profile post
# ==========================================

@app.get("/api/posts/my-posts")
def get_my_posts(user_id: str):
    # ดึงจากทั้ง 3 ตาราง
    lost = supabase.table("lost_posts").select("*").eq("user_id", user_id).execute().data
    found = supabase.table("found_posts").select("*").eq("user_id", user_id).execute().data
    adopt = supabase.table("adopt_posts").select("*").eq("user_id", user_id).execute().data

    return {"lost": lost, "found": found, "adopt": adopt}


# ==========================================
# 🗺️ SECTION 7: REVERSE GEOCODING (แปลงพิกัดบนแผนที่เป็นจังหวัด/อำเภอ)
# ==========================================

@app.get("/api/geocode/reverse")
def reverse_geocode(lat: float, lon: float):
    try:
        response = httpx.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format": "json", "lat": lat, "lon": lon, "accept-language": "th", "zoom": 14},
            headers={"User-Agent": "PetFinderAI/1.0 (student project)"},
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ไม่สามารถค้นหาที่อยู่จากพิกัดได้: {str(e)}")


# ==========================================
# 🚩 SECTION 8: REPORTS (ผู้ใช้รายงานโพสต์ที่ไม่เหมาะสม)
# ==========================================

class ReportSchema(BaseModel):
    post_type: str   # 'adopt' | 'lost' | 'found'
    post_id: int
    reason: str

@app.post("/api/reports")
def create_report(item: ReportSchema, authorization: str = Header(None)):
    try:
        if not authorization:
            raise HTTPException(status_code=401, detail="โปรดเข้าสู่ระบบก่อนรายงานโพสต์")
        token = authorization.replace("Bearer ", "")
        user_response = supabase.auth.get_user(token)
        user_id = user_response.user.id

        data_to_insert = {
            "reporter_id": user_id,
            "post_type": item.post_type,
            "post_id": item.post_id,
            "reason": item.reason,
        }
        response = supabase.table("reports").insert(data_to_insert).execute()
        return {"status": "success", "message": "ส่งรายงานเรียบร้อยแล้ว ทีมงานจะตรวจสอบโดยเร็วที่สุด 🙏", "data": response.data}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ CREATE REPORT ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ไม่สามารถส่งรายงานได้: {str(e)}")


# ==========================================
# 🛡️ SECTION 9: ADMIN (ระบบจัดการหลังบ้าน)
# ==========================================

ADMIN_POST_TABLES = {
    "adopt": "adopt_posts",
    "lost": "lost_posts",
    "found": "found_posts",
}

def require_admin(authorization: str = Header(None)) -> str:
    """ตรวจสอบ Token และสิทธิ์แอดมิน คืนค่า user_id ของแอดมินถ้าผ่าน"""
    if not authorization:
        raise HTTPException(status_code=401, detail="โปรดเข้าสู่ระบบก่อน")
    try:
        token = authorization.replace("Bearer ", "")
        user_response = supabase.auth.get_user(token)
        user_id = user_response.user.id
    except Exception:
        raise HTTPException(status_code=401, detail="เซสชันหมดอายุ กรุณาเข้าสู่ระบบใหม่")

    profile_response = supabase.table("users_profile").select("role, is_banned").eq("id", user_id).maybe_single().execute()
    profile = profile_response.data
    if not profile or profile.get("role") != "admin":
        raise HTTPException(status_code=403, detail="คุณไม่มีสิทธิ์เข้าถึงส่วนนี้")
    if profile.get("is_banned"):
        raise HTTPException(status_code=403, detail="บัญชีของคุณถูกระงับการใช้งาน")
    return user_id


class RoleUpdateSchema(BaseModel):
    role: str  # 'user' | 'admin'

class BanUpdateSchema(BaseModel):
    is_banned: bool

class PostStatusUpdateSchema(BaseModel):
    status: str

class ReportStatusUpdateSchema(BaseModel):
    status: str  # 'pending' | 'reviewed' | 'dismissed'


# --- Dashboard stats ---
@app.get("/api/admin/stats")
def admin_get_stats(admin_id: str = Depends(require_admin)):
    try:
        def count(table, **filters):
            q = supabase.table(table).select("id", count="exact")
            for k, v in filters.items():
                q = q.eq(k, v)
            return q.execute().count or 0

        return {
            "users": count("users_profile"),
            "adopt_posts": count("adopt_posts"),
            "lost_posts": count("lost_posts"),
            "found_posts": count("found_posts"),
            "comments": count("comments"),
            "pending_reports": count("reports", status="pending"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ไม่สามารถดึงข้อมูลสถิติได้: {str(e)}")


# --- User management ---
@app.get("/api/admin/users")
def admin_list_users(admin_id: str = Depends(require_admin)):
    try:
        response = supabase.table("users_profile").select("*").order("created_at", descending=True).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ไม่สามารถดึงรายชื่อผู้ใช้ได้: {str(e)}")

@app.patch("/api/admin/users/{user_id}/role")
def admin_update_role(user_id: str, item: RoleUpdateSchema, admin_id: str = Depends(require_admin)):
    if item.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="role ต้องเป็น 'user' หรือ 'admin'")
    try:
        response = supabase.table("users_profile").update({"role": item.role}).eq("id", user_id).execute()
        return {"status": "success", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ไม่สามารถอัปเดตสิทธิ์ผู้ใช้ได้: {str(e)}")

@app.patch("/api/admin/users/{user_id}/ban")
def admin_update_ban(user_id: str, item: BanUpdateSchema, admin_id: str = Depends(require_admin)):
    try:
        response = supabase.table("users_profile").update({"is_banned": item.is_banned}).eq("id", user_id).execute()
        return {"status": "success", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ไม่สามารถอัปเดตสถานะแบนได้: {str(e)}")


# --- Post management (adopt / lost / found) ---
@app.get("/api/admin/posts")
def admin_list_posts(admin_id: str = Depends(require_admin)):
    try:
        result = []
        for post_type, table in ADMIN_POST_TABLES.items():
            rows = supabase.table(table).select("*").order("created_at", descending=True).execute().data or []
            for r in rows:
                r["post_type"] = post_type
            result.extend(rows)
        result.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ไม่สามารถดึงรายการโพสต์ได้: {str(e)}")

@app.patch("/api/admin/posts/{post_type}/{post_id}/status")
def admin_update_post_status(post_type: str, post_id: int, item: PostStatusUpdateSchema, admin_id: str = Depends(require_admin)):
    table = ADMIN_POST_TABLES.get(post_type)
    if not table:
        raise HTTPException(status_code=400, detail="ประเภทโพสต์ไม่ถูกต้อง")
    try:
        response = supabase.table(table).update({"status": item.status}).eq("id", post_id).execute()
        return {"status": "success", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ไม่สามารถอัปเดตสถานะโพสต์ได้: {str(e)}")

@app.delete("/api/admin/posts/{post_type}/{post_id}")
def admin_delete_post(post_type: str, post_id: int, admin_id: str = Depends(require_admin)):
    table = ADMIN_POST_TABLES.get(post_type)
    if not table:
        raise HTTPException(status_code=400, detail="ประเภทโพสต์ไม่ถูกต้อง")
    try:
        supabase.table(table).delete().eq("id", post_id).execute()
        return {"status": "success", "message": "ลบโพสต์เรียบร้อยแล้ว"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ไม่สามารถลบโพสต์ได้: {str(e)}")


# --- Comment moderation ---
@app.get("/api/admin/comments")
def admin_list_comments(admin_id: str = Depends(require_admin)):
    try:
        comments = supabase.table("comments").select("*").order("created_at", descending=True).execute().data or []
        user_ids = list({c["user_id"] for c in comments if c.get("user_id")})
        profile_map = {}
        if user_ids:
            profiles = supabase.table("users_profile").select("id, full_name, avatar_url").in_("id", user_ids).execute().data or []
            profile_map = {p["id"]: p for p in profiles}
        for c in comments:
            c["users_profile"] = profile_map.get(c.get("user_id"))
        return comments
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ไม่สามารถดึงรายการคอมเมนต์ได้: {str(e)}")

@app.delete("/api/admin/comments/{comment_id}")
def admin_delete_comment(comment_id: int, admin_id: str = Depends(require_admin)):
    try:
        supabase.table("comments").delete().eq("id", comment_id).execute()
        return {"status": "success", "message": "ลบคอมเมนต์เรียบร้อยแล้ว"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ไม่สามารถลบคอมเมนต์ได้: {str(e)}")


# --- Reports moderation ---
@app.get("/api/admin/reports")
def admin_list_reports(admin_id: str = Depends(require_admin)):
    try:
        reports = supabase.table("reports").select("*").order("created_at", descending=True).execute().data or []
        reporter_ids = list({r["reporter_id"] for r in reports if r.get("reporter_id")})
        profile_map = {}
        if reporter_ids:
            profiles = supabase.table("users_profile").select("id, full_name, avatar_url").in_("id", reporter_ids).execute().data or []
            profile_map = {p["id"]: p for p in profiles}
        for r in reports:
            r["reporter_profile"] = profile_map.get(r.get("reporter_id"))
        return reports
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ไม่สามารถดึงรายการรายงานได้: {str(e)}")

@app.patch("/api/admin/reports/{report_id}")
def admin_update_report(report_id: int, item: ReportStatusUpdateSchema, admin_id: str = Depends(require_admin)):
    if item.status not in ("pending", "reviewed", "dismissed"):
        raise HTTPException(status_code=400, detail="status ไม่ถูกต้อง")
    try:
        response = supabase.table("reports").update({"status": item.status}).eq("id", report_id).execute()
        return {"status": "success", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ไม่สามารถอัปเดตสถานะรายงานได้: {str(e)}")


# ==========================================
# 🤖 SECTION 10: AI จับคู่รูปสัตว์หาย ↔ สัตว์ที่พบ (Matching)
# ==========================================

MATCH_SOURCE_TABLE = {"lost": "lost_posts", "found": "found_posts"}
MATCH_OPPOSITE = {"lost": "found", "found": "lost"}
MATCH_DISPLAY_THRESHOLD = 60.0  # % ความเหมือนรวมขั้นต่ำที่จะแสดงผล ตัดโพสต์ที่คล้ายกันแบบผิวเผินออกไป เพื่อความแม่นยำ

@app.get("/api/match/{post_type}/{post_id}")
def get_ai_matches(post_type: str, post_id: int):
    """หาโพสต์ฝั่งตรงข้าม (lost หาคู่ใน found, found หาคู่ใน lost) ที่รูปภาพคล้ายกัน เรียงจากเหมือนมากไปน้อย"""
    if post_type not in MATCH_SOURCE_TABLE:
        raise HTTPException(status_code=400, detail="ประเภทโพสต์ต้องเป็น 'lost' หรือ 'found' เท่านั้น")

    source_table = MATCH_SOURCE_TABLE[post_type]
    opposite_type = MATCH_OPPOSITE[post_type]
    opposite_table = MATCH_SOURCE_TABLE[opposite_type]

    try:
        source_post = supabase.table(source_table).select("*").eq("id", post_id).maybe_single().execute().data
        if not source_post:
            raise HTTPException(status_code=404, detail="ไม่พบโพสต์นี้")

        source_hash = source_post.get("image_hash")
        if not source_hash:
            return []

        # lost_posts เก็บวันที่หายไว้ที่ lost_date, found_posts ไม่มีวันที่ระบุ ใช้ created_at (วันที่โพสต์) แทนวันที่พบ
        source_date = source_post.get("lost_date") if post_type == "lost" else source_post.get("created_at")

        candidates = supabase.table(opposite_table) \
            .select("*") \
            .eq("type", source_post.get("type")) \
            .execute().data or []

        results = []
        for c in candidates:
            img_score = hash_similarity_percent(source_hash, c.get("image_hash"))
            if img_score <= 0:
                continue
            candidate_date = c.get("lost_date") if opposite_type == "lost" else c.get("created_at")
            if post_type == "lost":
                lost_date_str, found_date_str = source_date, candidate_date
            else:
                lost_date_str, found_date_str = candidate_date, source_date
            combined_score = combined_match_percent(img_score, lost_date_str, found_date_str)
            if combined_score < MATCH_DISPLAY_THRESHOLD:
                continue
            results.append({
                "post_type": opposite_type,
                "id": c["id"],
                "name": c.get("name"),
                "breed": c.get("breed"),
                "image_url": c.get("image_url"),
                "note": c.get("note"),
                "status": c.get("status"),
                "location_note": c.get("location_note"),
                "created_at": c.get("created_at"),
                "image_similarity_percent": img_score,
                "similarity_percent": combined_score,
            })

        results.sort(key=lambda r: r["similarity_percent"], reverse=True)
        return results[:8]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ไม่สามารถค้นหาการจับคู่ได้: {str(e)}")


SCAN_MATCH_THRESHOLD = 55.0  # % ความเหมือนขั้นต่ำที่จะถือว่าเป็นการจับคู่ที่ใช้ได้ สำหรับฟีเจอร์สแกนรูปด่วนหน้าแรก

@app.post("/api/match/scan")
async def scan_photo_for_match(file: UploadFile = File(...), animal_type: str = Form(...)):
    """
    ฟีเจอร์ 'สแกนรูปด่วน' หน้าแรก: อัปโหลดรูปสัตว์ที่เจอ ระบบจะเทียบกับประกาศ 'สัตว์หาย' (lost_posts)
    ที่เป็นสัตว์ชนิดเดียวกันทั้งหมด แล้วคืนโพสต์ที่รูปเหมือนที่สุด (ถ้ามีเหมือนพอ)
    """
    if animal_type not in ("สุนัข", "แมว"):
        raise HTTPException(status_code=400, detail="กรุณาระบุชนิดสัตว์เป็น 'สุนัข' หรือ 'แมว'")

    try:
        image_bytes = await file.read()
        upload_hash = compute_image_hash_from_bytes(image_bytes)
        if not upload_hash:
            raise HTTPException(status_code=400, detail="ไม่สามารถอ่านไฟล์รูปภาพนี้ได้ ลองอัปโหลดรูปใหม่อีกครั้ง")

        candidates = supabase.table("lost_posts") \
            .select("*") \
            .eq("type", animal_type) \
            .execute().data or []

        best = None
        for c in candidates:
            if not c.get("image_hash"):
                continue
            score = hash_similarity_percent(upload_hash, c["image_hash"])
            if score >= SCAN_MATCH_THRESHOLD and (best is None or score > best["similarity_percent"]):
                best = {
                    "post_type": "lost",
                    "id": c["id"],
                    "name": c.get("name"),
                    "breed": c.get("breed"),
                    "image_url": c.get("image_url"),
                    "location_note": c.get("location_note"),
                    "province": c.get("province"),
                    "district": c.get("district"),
                    "similarity_percent": score,
                }

        return {"match": best}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"สแกนรูปภาพไม่สำเร็จ: {str(e)}")