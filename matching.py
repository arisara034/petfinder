"""
ระบบ AI จับคู่รูปภาพสัตว์หาย (lost) กับสัตว์ที่พบ (found)
ใช้ perceptual hashing (average hash + difference hash) เทียบความเหมือนของรูปภาพ
เบาพอที่จะรันบน Render free tier ได้ ไม่ต้องใช้ GPU หรือโมเดล deep learning ขนาดใหญ่
"""
import httpx
from io import BytesIO
from datetime import datetime
from PIL import Image
import imagehash

HASH_SIZE = 16  # 16x16 -> hash ละเอียดขึ้น (256 บิต) แม่นยำกว่าค่า default ของไลบรารี (8x8)

IMAGE_WEIGHT = 0.7  # น้ำหนักของความเหมือนรูปภาพในคะแนนรวม
TIME_WEIGHT = 0.3   # น้ำหนักของความสอดคล้องของช่วงเวลาในคะแนนรวม


def compute_image_hash(image_url):
    """ดาวน์โหลดรูปจาก URL แล้วคำนวณ perceptual hash คืนเป็น string เก็บลง DB ได้"""
    if not image_url:
        return None
    try:
        resp = httpx.get(image_url, timeout=10.0, follow_redirects=True)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        ahash = imagehash.average_hash(img, hash_size=HASH_SIZE)
        dhash = imagehash.dhash(img, hash_size=HASH_SIZE)
        return f"{ahash}:{dhash}"
    except Exception as e:
        print(f"❌ IMAGE HASH ERROR: {e}")
        return None


def hash_similarity_percent(hash_a, hash_b):
    """เทียบ hash สองอัน คืนค่าเปอร์เซ็นต์ความเหมือน (0-100)"""
    if not hash_a or not hash_b:
        return 0.0
    try:
        a1, a2 = hash_a.split(":")
        b1, b2 = hash_b.split(":")
        ah1, ah2 = imagehash.hex_to_hash(a1), imagehash.hex_to_hash(a2)
        bh1, bh2 = imagehash.hex_to_hash(b1), imagehash.hex_to_hash(b2)
        bits = ah1.hash.size
        dist = ((ah1 - bh1) + (ah2 - bh2)) / 2
        similarity = max(0.0, 1 - (dist / bits)) * 100
        return round(similarity, 1)
    except Exception as e:
        print(f"❌ HASH COMPARE ERROR: {e}")
        return 0.0


def parse_date_safe(value):
    """แปลงค่าวันที่ (string เช่น '2026-08-01' หรือ ISO timestamp) เป็น date object คืน None ถ้าแปลงไม่ได้"""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except Exception:
        return None


def time_proximity_percent(lost_date_str, found_date_str):
    """
    ให้คะแนนความสอดคล้องของช่วงเวลา (0-100): วันที่ 'พบสัตว์' ควรอยู่ในหรือหลังวันที่ 'หายไป' ไม่นานนัก
    ยิ่งห่างกันมาก คะแนนยิ่งลด, ถ้าวันที่พบมาก่อนวันที่หาย (ผิดปกติ) ให้คะแนนต่ำ
    """
    lost_d = parse_date_safe(lost_date_str)
    found_d = parse_date_safe(found_date_str)
    if not lost_d or not found_d:
        return 70.0  # ไม่มีข้อมูลวันที่ให้เทียบ ไม่ตัดสิทธิ์ ให้คะแนนกลางๆ

    diff_days = (found_d - lost_d).days

    if diff_days < 0:
        return 20.0
    if diff_days <= 3:
        return 100.0
    if diff_days <= 7:
        return 90.0
    if diff_days <= 14:
        return 75.0
    if diff_days <= 30:
        return 55.0
    if diff_days <= 90:
        return 35.0
    return 15.0


def combined_match_percent(image_score, lost_date_str, found_date_str):
    """รวมคะแนนความเหมือนของรูปภาพกับความสอดคล้องของช่วงเวลาที่หาย/พบ เป็นเปอร์เซ็นต์เดียว"""
    time_score = time_proximity_percent(lost_date_str, found_date_str)
    combined = image_score * IMAGE_WEIGHT + time_score * TIME_WEIGHT
    return round(combined, 1)
