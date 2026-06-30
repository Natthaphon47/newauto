import os
import requests
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env
load_dotenv()

# ตั้งค่า API Key ของ Google Gemini
api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
USE_GEMINI = os.getenv("USE_GEMINI", "true").strip().lower() in ("1", "true", "yes", "on")
DEFAULT_MODELS = [
    os.getenv("GEMINI_MODEL", "").strip(),
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


def _contains_thai(text: str) -> bool:
    return any('\u0E00' <= ch <= '\u0E7F' for ch in text)


def _is_mostly_english(text: str) -> bool:
    if not text:
        return False
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    ascii_count = sum(1 for ch in letters if ord(ch) < 128)
    return (ascii_count / len(letters)) >= 0.6


def _split_sentences(text: str):
    import re
    if not text:
        return []
    text = text.replace('\n', ' ').strip()
    parts = re.split(r'(?<=[.!?])\s+|\n+', text)
    return [p.strip() for p in parts if p.strip()]


def _translate_text(text: str, source: str, target: str) -> str:
    if not text:
        return ''
    try:
        from googletrans import Translator
        translator = Translator()
        translated = translator.translate(text, src=source, dest=target).text
        if translated:
            return translated
    except Exception:
        pass

    try:
        resp = requests.post(
            'https://libretranslate.de/translate',
            json={'q': text, 'source': source, 'target': target, 'format': 'text'},
            timeout=10,
        )
        if resp.ok:
            translated = resp.json().get('translatedText', '')
            if translated:
                return translated
    except Exception:
        pass

    try:
        params = {
            'client': 'gtx',
            'sl': source,
            'tl': target,
            'dt': 't',
            'q': text,
        }
        url = 'https://translate.googleapis.com/translate_a/single'
        resp = requests.get(url, params=params, timeout=10)
        if resp.ok:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                translated = ''.join(part[0] for part in data[0] if part and part[0])
                if translated:
                    return translated
    except Exception:
        pass

    return ''


import nltk
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer

try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)

def _extract_key_sentences(text: str, max_sentences: int = 2) -> str:
    if not text or len(text.strip()) == 0:
        return ''
    try:
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = LexRankSummarizer()
        summary_sentences = summarizer(parser.document, max_sentences)
        if not summary_sentences:
            return text[:280].strip()
        return ' '.join(str(sentence) for sentence in summary_sentences).strip()
    except Exception as e:
        print(f"⚠️ คำนวณ LexRank ล้มเหลว: {e}")
        sentences = _split_sentences(text)
        return ' '.join(sentences[:max_sentences]).strip()

def _shorten_summary(text: str, max_sentences: int = 2, max_chars: int = 280) -> str:
    if not text:
        return text
    sentences = _split_sentences(text)
    if not sentences:
        return text[:max_chars].strip()
    shortened = ' '.join(sentences[:max_sentences]).strip()
    if len(shortened) <= max_chars:
        return shortened
    return shortened[:max_chars].rsplit(' ', 1)[0].strip()

def _local_summary(text, language: str) -> str:
    if not text:
        return 'ไม่มีเนื้อหาสำหรับสรุป' if language == 'ไทย' else 'No content to summarize'

    if language == 'ไทย':
        if not _contains_thai(text):
            best = _extract_key_sentences(text, max_sentences=3)
            if best:
                translated = _translate_text(best, 'en', 'th')
                if translated:
                    return _shorten_summary(translated, max_sentences=3, max_chars=400)
            translated_text = _translate_text(text, 'en', 'th')
            if translated_text:
                summary = _extract_key_sentences(translated_text, max_sentences=3)
                if summary:
                    return _shorten_summary(summary, max_sentences=3, max_chars=400)
                return _shorten_summary(translated_text, max_sentences=3, max_chars=400)
            return 'สรุปข่าว: ไม่มีเนื้อหาสำคัญ'

        best = _extract_key_sentences(text, max_sentences=3)
        if best:
            return _shorten_summary(best, max_sentences=3, max_chars=400)
        sentences = _split_sentences(text)
        return _shorten_summary(' '.join(sentences[:3]), max_sentences=3, max_chars=400)

    if not _contains_thai(text):
        best = _extract_key_sentences(text, max_sentences=3)
        if best:
            return best
        sentences = _split_sentences(text)
        return ' '.join(sentences[:3]).strip()

    best = _extract_key_sentences(text, max_sentences=3)
    if not best:
        sentences = _split_sentences(text)
        best = ' '.join(sentences[:3]) if sentences else ''
    translated = _translate_text(best, 'th', 'en')
    if translated:
        return translated
    return f"Summary: {best[:250].strip()}"


def _fallback_summary(text, language):
    if not text:
        return "ไม่มีเนื้อหาสำหรับสรุป" if language == "ไทย" else "No content to summarize"

    sentences = [s.strip() for s in text.replace('\n', ' ').split('.') if s.strip()]
    preview = ' '.join(sentences[:2])

    # พยายามแปลส่วนภาษาอังกฤษเป็นภาษาไทยหากมี library แปลภาษา (optional)
    translator = None
    try:
        from googletrans import Translator
        translator = Translator()
    except Exception:
        translator = None

    def is_mostly_ascii(s: str) -> bool:
        if not s:
            return False
        ascii_chars = sum(1 for ch in s if ord(ch) < 128 and ch.isalpha())
        total_chars = sum(1 for ch in s if ch.isalpha())
        return total_chars > 0 and (ascii_chars / total_chars) > 0.6

    def split_into_chunks(s: str):
        # แบ่งเป็นประโยคย่อยโดยใช้ punctuation
        import re
        parts = re.split(r'[\n\r]+|(?<=[.!?])\s+', s)
        return [p.strip() for p in parts if p.strip()]

    def translate_chunk(chunk: str):
        if not chunk:
            return ''
        if translator:
            try:
                res = translator.translate(chunk, dest='th')
                return res.text
            except Exception:
                return ''
        # ถ้าไม่มี googletrans ให้ลองใช้ LibreTranslate สาธารณะ
        try:
            import requests
            resp = requests.post(
                'https://libretranslate.de/translate',
                json={'q': chunk, 'source': 'en', 'target': 'th', 'format': 'text'},
                timeout=10,
            )
            if resp.ok:
                return resp.json().get('translatedText', '')
        except Exception:
            return ''
        return ''

    # ถ้าพรีวิวมีเนื้อหาที่เป็นภาษาอังกฤษครบประโยค ให้พยายามแปล
    chunks = split_into_chunks(preview)
    translated_parts = []
    for ch in chunks:
        if is_mostly_ascii(ch):
            tr = translate_chunk(ch)
            if tr:
                translated_parts.append(tr)
        else:
            translated_parts.append(ch)

    preview = ' '.join(translated_parts).strip()
    # ถ้าหลังการแปล/ตัดแล้ว preview ว่าง ให้พยายามแปลทั้งข้อความต้นฉบับ
    if not preview:
        try:
            # แปลทั้งข้อความจาก en->th
            import requests
            resp = requests.post(
                'https://libretranslate.de/translate',
                json={'q': text, 'source': 'en', 'target': 'th', 'format': 'text'},
                timeout=10,
            )
            if resp.ok:
                entire = resp.json().get('translatedText', '').strip()
                if entire:
                    # เอาประโยคสองประโยคแรกของการแปลมาใช้
                    import re
                    sents = re.split(r'(?<=[.!?])\s+', entire)
                    preview = ' '.join(sents[:2]).strip()
        except Exception:
            preview = ''
    if language == "ไทย":
        return f"สรุปแบบพื้นฐาน: ข่าวนี้เกี่ยวกับปาล์มน้ำมันและมีเนื้อหาที่สำคัญคือ {preview[:180]}"
    return f"Basic summary: this news is about palm oil and the key point is {preview[:180]}"


def _extract_text_from_response(payload):
    if not isinstance(payload, dict):
        return ""

    parts = []
    for candidate in payload.get("candidates", []):
        content = candidate.get("content") or {}
        for part in content.get("parts", []):
            if isinstance(part, dict) and part.get("text"):
                parts.append(part["text"])

    return "\n".join(parts).strip()


def _summarize_with_gemini(text, prompt, error_prefix):
    if not text:
        return "ไม่มีเนื้อหาสำหรับสรุป" if error_prefix == "ไทย" else "No content to summarize"

    if not api_key:
        return "ไม่สามารถสรุปข่าวได้เนื่องจากไม่มี GEMINI_API_KEY" if error_prefix == "ไทย" else "Unable to summarize news because GEMINI_API_KEY is missing"

    last_error = None

    def _get_models_to_try():
        # ให้ความสำคัญกับการตั้งค่า GEMINI_MODEL ก่อน แล้วตามด้วยรายการสำรอง
        env_model = os.getenv("GEMINI_MODEL", "").strip()
        candidates = [m for m in DEFAULT_MODELS if m]
        if env_model and env_model not in candidates:
            candidates.insert(0, env_model)
        if not api_key or not candidates:
            return candidates
        try:
            list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            resp = requests.get(list_url, timeout=10)
            if resp.ok:
                data = resp.json()
                available = set()
                for m in data.get('models', []):
                    # model name may be like 'models/gemini-2.0-flash'
                    name = m.get('name') if isinstance(m, dict) else None
                    if name:
                        # keep both full and short forms
                        available.add(name)
                        if name.startswith('models/'):
                            available.add(name.split('/', 1)[1])
                # If user explicitly requested a model, keep it first even if not in ListModels
                explicit = [env_model] if env_model else []
                other = [c for c in candidates if c != env_model and c in available]
                if explicit:
                    return explicit + other
                filtered = [c for c in candidates if c in available]
                if filtered:
                    return filtered
        except Exception:
            pass
        return candidates

    models_to_try = _get_models_to_try()
    print(f"🔧 Gemini models to try: {models_to_try}")
    for model_name in models_to_try:
        try:
            print(f"🔧 Trying Gemini model: {model_name}")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": prompt}]}
                ]
            }
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if response.ok:
                response_text = _extract_text_from_response(response.json())
                if response_text:
                    return response_text
                last_error = "Gemini returned an empty response"
                continue

            error_payload = response.json()
            error_message = error_payload.get("error", {}).get("message", response.text)
            last_error = error_message

            if "API key not valid" in error_message:
                break
        except Exception as e:
            last_error = str(e)

    print(f"❌ เกิดข้อผิดพลาดในการสรุปข่าว (Gemini): {last_error}")
    return _fallback_summary(text, "ไทย" if error_prefix == "ไทย" else "อังกฤษ")


def summarize_text(text):
    """
    ส่งข้อความไปให้ Google Gemini AI สรุปเนื้อหา หรือใช้ local summary ถ้าไม่เปิดใช้งาน AI

    Args:
        text (str): เนื้อข่าวที่ต้องการสรุป

    Returns:
        str: ข้อความสรุปหรือข้อความแสดงข้อผิดพลาด
    """
    if not USE_GEMINI:
        return _local_summary(text, 'ไทย')

    prompt = f"ช่วยสรุปข่าวต่อไปนี้เป็นภาษาไทยเท่านั้น ให้กระชับ อ่านง่าย และเน้นใจความสำคัญแบบสั้นๆ โดยตอบเป็นภาษาไทยทั้งหมด และอย่าใช้ภาษาอังกฤษเลย:\n\n{text}"
    return _summarize_with_gemini(text, prompt, "ไทย")


def summarize_text_en(text):
    """
    ส่งข้อความไปให้ Google Gemini AI สรุปเนื้อหา (ภาษาอังกฤษ)

    Args:
        text (str): เนื้อข่าวที่ต้องการสรุป

    Returns:
        str: ข้อความสรุปหรือข้อความแสดงข้อผิดพลาด
    """
    if not USE_GEMINI:
        return _local_summary(text, 'อังกฤษ')

    prompt = f"Please summarize the following news in English briefly and clearly, focusing on the key points. Respond only in English and keep it concise:\n\n{text}"
    result = _summarize_with_gemini(text, prompt, "อังกฤษ")

    # หากผลลัพธ์มีตัวอักษรไทย แปลผลสรุปเป็นอังกฤษด้วยตัวช่วยแปล
    def contains_thai(s: str) -> bool:
        return any('\u0E00' <= ch <= '\u0E7F' for ch in s)

    if contains_thai(result):
        # พยายามแปลด้วย googletrans ถ้ามี ถ้าไม่ใช้ LibreTranslate
        translated = ''
        try:
            from googletrans import Translator
            tr = Translator()
            translated = tr.translate(result, dest='en').text
        except Exception:
            # LibreTranslate public instance fallback
            try:
                import requests
                resp = requests.post(
                    'https://libretranslate.de/translate',
                    json={
                        'q': result,
                        'source': 'th',
                        'target': 'en',
                        'format': 'text'
                    },
                    timeout=10,
                )
                if resp.ok:
                    translated = resp.json().get('translatedText', '')
            except Exception:
                translated = ''

        if translated:
            return translated

    return result
