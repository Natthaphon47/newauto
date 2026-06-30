import json
from pathlib import Path

import schedule
import sys
import time
import io

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from scraper import get_article_urls, get_news_content, is_palm_oil_related
from summarizer import summarize_text, summarize_text_en
from email_sender import send_email

STATE_FILE = Path(__file__).with_name('sent_articles.json')
MAX_HISTORY = 200


def load_sent_articles():
    if not STATE_FILE.exists():
        return set()
    try:
        with STATE_FILE.open('r', encoding='utf-8') as f:
            data = json.load(f)
        return set(data if isinstance(data, list) else [])
    except Exception as e:
        print(f"⚠️ ไม่สามารถโหลดสถานะข่าวเก่าได้: {e}")
        return set()


def save_sent_articles(urls):
    try:
        payload = list(urls)[-MAX_HISTORY:]
        with STATE_FILE.open('w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาดในการบันทึกสถานะข่าว: {e}")


def job(max_articles: int | None = 5):
    """รันกระบวนการดึงและสรุปข่าว"""
    print("\n--- ⏳ เริ่มกระบวนการดึงและสรุปข่าว ---")
    
    url = "https://prestasisawit.mpob.gov.my/en/palmnews"
    print(f"1. กำลังดึงรายการข่าวจาก: {url}")

    article_urls = get_article_urls(url)
    if not article_urls:
        print("❌ ไม่พบรายการข่าวหรือดึงลิงก์ไม่ได้")
        return

    sent_articles = load_sent_articles()
    new_articles = [link for link in article_urls if link not in sent_articles]

    if not new_articles:
        print("ℹ️ ไม่มีข่าวใหม่ในรอบนี้")
        return

    if max_articles is not None:
        new_articles = new_articles[:max_articles]

    print(f"🔔 พบข่าวใหม่ {len(new_articles)} ชิ้น")
    for article_url in reversed(new_articles):
        print(f"2. กำลังดึงข่าวใหม่: {article_url}")
        title, content, source_url = get_news_content(article_url)
        if not title or not content:
            print(f"❌ ดึงข่าวใหม่ไม่สำเร็จสำหรับ {article_url}")
            continue

        if not is_palm_oil_related(title, content):
            print("ℹ️ ข่าวใหม่ไม่เกี่ยวกับปาล์มน้ำมัน — ข้ามการส่งอีเมล")
            sent_articles.add(article_url)
            save_sent_articles(sent_articles)
            continue

        print("3. กำลังสรุปเนื้อหาและส่งอีเมล...")
        summary_th = summarize_text(content)
        summary_en = summarize_text_en(content)

        email_body = f"""
📰 หัวข้อข่าว: {title}
🔗 ที่มา: {source_url}

{'='*60}
🇹🇭 สรุปเนื้อหา (ภาษาไทย):
{'='*60}
{summary_th}

{'='*60}
🇬🇧 Summary (English):
{'='*60}
{summary_en}
{'='*60}
"""
        if send_email(f"📰 ข่าวใหม่: {title}", email_body):
            sent_articles.add(article_url)
            save_sent_articles(sent_articles)
        else:
            print(f"❌ ไม่สามารถส่งอีเมลสำหรับข่าว: {title}")

    print("--------------------------------------\n")

if __name__ == "__main__":
    if "--test-fetch" in sys.argv:
        print("🔧 Running fetch-only test mode...")
        title, content, source_url = get_news_content("https://prestasisawit.mpob.gov.my/en/palmnews")
        if title and content:
            print(f"\nTITLE: {title}\n")
            print(f"SOURCE: {source_url}\n")
            print("SNIPPET:\n")
            print(content[:1400])
        else:
            print("❌ ไม่สามารถดึงข้อมูลได้")
        sys.exit(0)

    print("🚀 ระบบสรุปข่าวอัตโนมัติ (Automated News Summarizer) เริ่มทำงานแล้ว!")
    if "--one" in sys.argv:
        job(max_articles=1)
        print("✅ ส่งข่าวใหม่แค่ 1 ชิ้นเสร็จสิ้น")
        sys.exit(0)

    try:
        # รันทันที 1 ครั้งเพื่อทดสอบระบบ
        job()

        if "--once" in sys.argv:
            print("✅ ทำงานครั้งเดียวเสร็จสิ้น")
            sys.exit(0)

        # ตั้งเวลาตรวจสอบข่าวใหม่ทุก 15 นาที
        schedule.every(15).minutes.do(job)

        print("⏰ รอเวลาทำงานตามรอบถัดไป... (กด Ctrl+C เพื่อหยุดโปรแกรม)")

        # ลูปทำงานวนไปเรื่อยๆ เพื่อเช็คเวลา
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n🛑 โปรแกรมถูกหยุดโดยผู้ใช้")
        sys.exit(0)
