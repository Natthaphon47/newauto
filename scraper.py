import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


def extract_article_urls(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    article_urls = []
    seen = set()

    for link in soup.find_all('a', href=True):
        href = link.get('href', '').strip()
        if not href:
            continue

        full_url = urljoin(base_url, href)
        if '/news/' in full_url and full_url not in seen:
            article_urls.append(full_url)
            seen.add(full_url)

    return article_urls


def extract_title_and_content(html, source_url):
    soup = BeautifulSoup(html, 'html.parser')

    title = None
    for selector in ['.text-4xl.font-bold.text-black', '.text-4xl.font-bold', 'h1', 'h2', 'article h1', '.title', '.post-title']:
        tag = soup.select_one(selector)
        if tag:
            title = tag.get_text(' ', strip=True)
            break

    if not title:
        title_tag = soup.find('title')
        title = title_tag.get_text(' ', strip=True) if title_tag else 'ไม่พบหัวข้อข่าว'

    content_block = soup.select_one('.content div.w-full.bg-white.rounded.p-6.mt-4') or soup.select_one('.content') or soup.body or soup
    paragraphs = []
    seen = set()

    body_paragraphs = content_block.find_all('p', class_='MsoNormal')
    if not body_paragraphs:
        body_paragraphs = content_block.find_all('p')

    ignore_patterns = [
        'home', 'news', 'share this post', 'total views', 'printer',
        'market development', 'calendar', 'link oils & fats international',
        'english', 'bahasa melayu'
    ]

    for p in body_paragraphs:
        text = p.get_text(' ', strip=True)
        if not text or len(text) < 40:
            continue
        lower = text.lower()
        if any(pattern in lower for pattern in ignore_patterns):
            continue
        if text in seen:
            continue
        seen.add(text)
        paragraphs.append(text)

    if not paragraphs:
        for p in content_block.find_all(['p', 'li']):
            text = p.get_text(' ', strip=True)
            if not text or len(text) < 40:
                continue
            lower = text.lower()
            if any(pattern in lower for pattern in ignore_patterns):
                continue
            if text in seen:
                continue
            seen.add(text)
            paragraphs.append(text)

    content = '\n'.join(paragraphs).strip()
    if not content:
        content = soup.get_text('\n', strip=True)

    if not title or title == 'Prestasi Sawit Malaysia':
        title = 'ไม่พบหัวข้อข่าว'

    return title, content


def get_news_content(url):
    """
    ดึงข้อความและหัวข้อข่าวจากเว็บไซต์

    Returns:
        tuple: (title, content, source_url)
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.encoding = 'utf-8'
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        article_urls = extract_article_urls(response.text, url)

        source_url = url
        if article_urls:
            article_url = article_urls[0]
            if article_url != url:
                print(f"🔗 พบลิงก์บทความจริง: {article_url}")
                article_response = requests.get(article_url, headers=HEADERS, timeout=20)
                article_response.encoding = 'utf-8'
                article_response.raise_for_status()
                title, content = extract_title_and_content(article_response.text, article_url)
                source_url = article_url
            else:
                title, content = extract_title_and_content(response.text, url)
        else:
            title, content = extract_title_and_content(response.text, url)

        if not content or len(content) < 80:
            print("❌ ไม่สามารถดึงเนื้อหาจากหน้าเว็บได้")
            return None, None, None

        print(f"✅ ดึงข้อมูลสำเร็จ - หัวข้อ: {title[:60]}...")
        return title, content, source_url

    except requests.exceptions.RequestException as e:
        print(f"❌ เกิดข้อผิดพลาดในการเข้าถึง URL: {e}")
        return None, None, None
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการดึงข้อมูล: {e}")
        return None, None, None


def get_article_urls(page_url):
    """
    ดึงลิงก์ข่าวใหม่ทั้งหมดจากหน้ารวมข่าว
    """
    try:
        response = requests.get(page_url, headers=HEADERS, timeout=20)
        response.encoding = 'utf-8'
        response.raise_for_status()
        return extract_article_urls(response.text, page_url)
    except requests.exceptions.RequestException as e:
        print(f"❌ เกิดข้อผิดพลาดในการเข้าถึง URL: {e}")
        return []
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการดึงลิงก์บทความ: {e}")
        return []


def is_palm_oil_related(title: str, content: str) -> bool:
    """
    ตรวจสอบว่าข่าวเกี่ยวกับปาล์มน้ำมันหรือไม่ โดยเช็คคำสำคัญในหัวข้อและเนื้อหา

    Returns:
        bool: True ถ้าเกี่ยวข้อง, False ถ้าไม่เกี่ยวข้อง
    """
    if not title and not content:
        return False

    text = " ".join(filter(None, [title, content])).lower()

    # คำสำคัญภาษาไทยและอังกฤษที่เกี่ยวกับปาล์มน้ำมัน
    keywords = [
        "ปาล์มน้ำมัน", "ปาล์ม", "น้ำมันปาล์ม", "palm oil", "palm", "palm-oil","PCO","MPOB","palm kernel","palm fruit","palm plantation"
    ]

    for kw in keywords:
        if kw in text:
            return True
    return False
