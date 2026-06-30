import os
import requests
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env
load_dotenv()

RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_FROM_EMAIL = "onboarding@resend.dev"  # ใช้แอดเดรสนี้สำหรับทดสอบบน Resend ได้ทันที

def send_email(subject, body):
    """
    ส่งอีเมลผ่าน Resend API
    
    Args:
        subject (str): หัวข้ออีเมล
        body (str): เนื้อหาอีเมล
    
    Returns:
        bool: True ถ้าส่งสำเร็จ, False ถ้าล้มเหลว
    """
    resend_api_key = os.getenv("RESEND_API_KEY")
    sender_email = os.getenv("EMAIL_FROM", DEFAULT_FROM_EMAIL)
    receiver_email = os.getenv("TO_EMAIL")

    if not all([resend_api_key, sender_email, receiver_email]):
        print("❌ กรุณาตั้งค่า RESEND_API_KEY, TO_EMAIL และกำหนด FROM_EMAIL ในโค้ดหรือ .env ให้ครบถ้วน")
        return False

    payload = {
        "from": sender_email,
        "to": [receiver_email],
        "subject": subject,
        "text": body
    }
    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json"
    }

    response = None
    try:
        response = requests.post(RESEND_API_URL, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        response_body = response.json()
        message_id = response_body.get('id')
        if message_id:
            print(f"✅ ส่งอีเมลสรุปข่าวสำเร็จผ่าน Resend API แล้ว! Message ID: {message_id}")
        else:
            print("✅ ส่งอีเมลสรุปข่าวสำเร็จผ่าน Resend API แล้ว!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ เกิดข้อผิดพลาดในการส่งอีเมลผ่าน Resend API: {e}")
        if response is not None:
            print(f"Response: {response.status_code} - {response.text}")
        return False
