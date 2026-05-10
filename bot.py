# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║          🔥 Card Generator Pro  — by @o8380                 ║
║  متغيرات البيئة المطلوبة:                                   ║
║    BOT_TOKEN      – توكن البوت من @BotFather               ║
║    OWNER_ID       – معرف المالك (رقم)                       ║
║    OPENAI_API_KEY – مفتاح OpenAI (اختياري)                  ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import json
import random
import time
import re
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

import requests
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# محاولة استيراد OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# ══════════════════════════════════════════════════════════════
# السجلات والإعدادات
# ══════════════════════════════════════════════════════════════
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# الثوابت من متغيرات البيئة
# ══════════════════════════════════════════════════════════════
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    BOT_TOKEN = "ضع_توكنك_هنا"

OWNER_ID = int(os.environ.get("OWNER_ID", "6285783725"))
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
BOT_TAG = "@o8380"
VERSION = "4.0 Pro"

# ══════════════════════════════════════════════════════════════
# المسارات
# ══════════════════════════════════════════════════════════════
DATA_DIR = Path("data")
USER_DATA_DIR = DATA_DIR / "user_data"
TEMP_DIR = Path("temp_files")
PRIVATE_BINS_FILE = DATA_DIR / "private_bins.json"
STATS_FILE = DATA_DIR / "stats.json"

for directory in [DATA_DIR, USER_DATA_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════
# OpenAI Client (مخفي)
# ══════════════════════════════════════════════════════════════
ai_client = None
if OPENAI_AVAILABLE and OPENAI_API_KEY:
    try:
        ai_client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("✅ OpenAI client initialized")
    except Exception as e:
        logger.warning(f"OpenAI init failed: {e}")

# ══════════════════════════════════════════════════════════════
# إنشاء البوت
# ══════════════════════════════════════════════════════════════
bot = telebot.TeleBot(BOT_TOKEN)

# إزالة أي ويب هوك قديم
try:
    bot.remove_webhook()
except:
    pass

time.sleep(1)

# ══════════════════════════════════════════════════════════════
# قاموس لتخزين بيانات المستخدمين المؤقتة
# ══════════════════════════════════════════════════════════════
user_data: Dict[int, Dict] = {}
user_steps: Dict[int, str] = {}

# ══════════════════════════════════════════════════════════════
# ██  أدوات JSON  ██
# ══════════════════════════════════════════════════════════════

def load_user_settings(uid: int) -> dict:
    """تحميل إعدادات المستخدم"""
    file_path = USER_DATA_DIR / f"{uid}.json"
    if file_path.exists():
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except:
            pass
    return {}

def save_user_settings(uid: int, data: dict):
    """حفظ إعدادات المستخدم"""
    file_path = USER_DATA_DIR / f"{uid}.json"
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_private_bins() -> dict:
    """تحميل BINs الخاصة (مخفي)"""
    if PRIVATE_BINS_FILE.exists():
        try:
            return json.loads(PRIVATE_BINS_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return {}

def save_private_bins(data: dict):
    """حفظ BINs الخاصة (مخفي)"""
    PRIVATE_BINS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_stats() -> dict:
    """تحميل الإحصائيات"""
    if STATS_FILE.exists():
        try:
            return json.loads(STATS_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return {"total_files": 0, "total_generated": 0, "total_users": 0}

def save_stats(data: dict):
    """حفظ الإحصائيات"""
    STATS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ══════════════════════════════════════════════════════════════
# ██  Luhn Algorithm  ██
# ══════════════════════════════════════════════════════════════

def luhn_check(card_num: str) -> bool:
    """التحقق من صحة الرقم باستخدام Luhn Algorithm"""
    digits = [int(d) for d in str(card_num) if d.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    for i, d in enumerate(digits[::-1]):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0

def luhn_digit(partial: str) -> str:
    """حساب الرقم الأخير لضمان صحة Luhn"""
    for n in range(10):
        if luhn_check(partial + str(n)):
            return str(n)
    return "0"

# ══════════════════════════════════════════════════════════════
# ██  تحليل البطاقات  ██
# ══════════════════════════════════════════════════════════════

def parse_card(line: str) -> Optional[dict]:
    """تحليل سطر بطاقة واستخراج البيانات"""
    line = line.strip()
    if not line or line.startswith("#") or "|" not in line:
        return None
    parts = line.split("|")
    if len(parts) < 4:
        return None
    
    card_num = re.sub(r"\D", "", parts[0].strip())
    month = parts[1].strip().zfill(2)
    year = parts[2].strip()
    cvv = parts[3].strip()
    
    if len(card_num) < 13 or not month.isdigit() or not year.isdigit():
        return None
    
    if len(year) == 4:
        year = year[-2:]
    
    return {
        "num": card_num,
        "month": month,
        "year": year,
        "cvv": cvv,
        "bin6": card_num[:6]
    }

def is_expired(month: str, year: str) -> bool:
    """التحقق من صلاحية البطاقة"""
    try:
        now = datetime.now()
        exp_year = int("20" + year) if len(year) == 2 else int(year)
        exp_month = int(month)
        return datetime(exp_year, exp_month, 1) < datetime(now.year, now.month, 1)
    except:
        return False

def filter_cards(lines: List[str]) -> dict:
    """تصفية البطاقات (Luhn + تاريخ + مكررات + BINs مكررة)"""
    result = {
        "original": len(lines),
        "invalid": 0,
        "expired": 0,
        "luhn_fail": 0,
        "dup_card": 0,
        "dup_bin": 0,
        "valid": []
    }
    seen_cards = set()
    seen_bins = set()
    
    for line in lines:
        card = parse_card(line)
        if not card:
            result["invalid"] += 1
            continue
        
        if is_expired(card["month"], card["year"]):
            result["expired"] += 1
            continue
        
        if not luhn_check(card["num"]):
            result["luhn_fail"] += 1
            continue
        
        card_key = f"{card['num']}|{card['month']}|{card['year']}"
        if card_key in seen_cards:
            result["dup_card"] += 1
            continue
        seen_cards.add(card_key)
        
        if card["bin6"] in seen_bins:
            result["dup_bin"] += 1
            continue
        seen_bins.add(card["bin6"])
        
        result["valid"].append(card)
    
    return result

# ══════════════════════════════════════════════════════════════
# ██  BIN Analysis (مخفي)  ██
# ══════════════════════════════════════════════════════════════

BIN_CACHE = {}

def fetch_bin_info(bin6: str) -> dict:
    """جلب معلومات BIN من binlist.net"""
    if bin6 in BIN_CACHE:
        return BIN_CACHE[bin6]
    
    try:
        response = requests.get(
            f"https://lookup.binlist.net/{bin6}",
            headers={"Accept-Version": "3"},
            timeout=6
        )
        if response.status_code == 200:
            data = response.json()
            info = {
                "scheme": data.get("scheme", "?").upper(),
                "type": data.get("type", "?").upper(),
                "bank": data.get("bank", {}).get("name", "Unknown"),
                "country": data.get("country", {}).get("name", "Unknown"),
                "flag": data.get("country", {}).get("emoji", "🏳️"),
                "prepaid": data.get("prepaid", False)
            }
            BIN_CACHE[bin6] = info
            return info
    except:
        pass
    return {}

def classify_bin(info: dict) -> str:
    """تصنيف BIN (مخفي - يستخدم للتخزين فقط)"""
    scheme = info.get("scheme", "")
    country = info.get("country", "")
    prepaid = info.get("prepaid", False)
    
    if prepaid or scheme in ("UNIONPAY", "MIR") or country not in ("United States", "United Kingdom", ""):
        return "private"
    if scheme in ("AMEX", "DISCOVER", "DINERS"):
        return "semi"
    return "public"

def store_private_bin(bin6: str, info: dict, cls: str):
    """تخزين BIN خاص (مخفي)"""
    db = load_private_bins()
    if bin6 not in db:
        db[bin6] = {
            "info": info,
            "classification": cls,
            "first_seen": datetime.now().isoformat(),
            "usage": 0
        }
    else:
        db[bin6]["usage"] = db[bin6].get("usage", 0) + 1
    save_private_bins(db)

def analyze_bins(cards: List[dict]) -> List[dict]:
    """تحليل BINs (مخفي)"""
    analyzed = []
    for card in cards:
        info = fetch_bin_info(card["bin6"])
        cls = classify_bin(info)
        store_private_bin(card["bin6"], info, cls)
        analyzed.append({**card, "bin_info": info, "cls": cls})
        time.sleep(0.1)
    return analyzed

# ══════════════════════════════════════════════════════════════
# ██  AI Hidden Function  ██
# ══════════════════════════════════════════════════════════════

def ai_hidden_analysis(analyzed: List[dict]) -> str:
    """تحليل AI مخفي (لا يظهر للمستخدم)"""
    if not ai_client or not analyzed:
        return ""
    try:
        summary = "\n".join([
            f"BIN {c['bin6']}: {c['cls']} | {c['bin_info'].get('scheme', '')}"
            for c in analyzed[:10]
        ])
        response = ai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "user",
                "content": f"Analyze these BINs and give short recommendation (2 sentences):\n{summary}"
            }],
            max_tokens=100,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"AI error: {e}")
        return ""

# ══════════════════════════════════════════════════════════════
# ██  توليد البطاقات  ██
# ══════════════════════════════════════════════════════════════

def generate_cards(
    card: dict,
    digits: int,
    date_mode: str,
    cvv_mode: str,
    count: int
) -> List[str]:
    """توليد بطاقات جديدة من بطاقة أصلية"""
    base = card["num"][:digits]
    full_len = 16
    results = []
    seen = set()
    max_attempts = count * 60
    
    for _ in range(max_attempts):
        if len(results) >= count:
            break
        
        remaining = full_len - len(base) - 1
        middle = "".join(str(random.randint(0, 9)) for _ in range(remaining))
        partial = base + middle
        check = luhn_digit(partial)
        new_num = partial + check
        
        if not luhn_check(new_num):
            continue
        
        month = card["month"] if date_mode == "fixed" else str(random.randint(1, 12)).zfill(2)
        year = card["year"] if date_mode == "fixed" else str(random.randint(26, 30))
        cvv = card["cvv"] if cvv_mode == "fixed" else str(random.randint(100, 999))
        
        card_line = f"{new_num}|{month}|{year}|{cvv}"
        if card_line not in seen:
            seen.add(card_line)
            results.append(card_line)
    
    return results

# ══════════════════════════════════════════════════════════════
# ██  دوال إنشاء لوحات المفاتيح (بالألوان والأيقونات)  ██
# ══════════════════════════════════════════════════════════════

def create_main_menu(uid: int = None) -> InlineKeyboardMarkup:
    """القائمة الرئيسية - زر رفع ملف فقط"""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            "📤 رفع ملف",
            callback_data="upload_file",
            style="success",
            icon_custom_emoji_id="5330274810582827128"
        )
    )
    return markup

def create_back_button() -> InlineKeyboardMarkup:
    """زر رجوع"""
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            "🔙 رجوع",
            callback_data="back",
            style="danger",
            icon_custom_emoji_id="5060247798616687432"
        )
    )
    return markup

def create_digits_keyboard() -> InlineKeyboardMarkup:
    """لوحة اختيار عدد الأرقام"""
    markup = InlineKeyboardMarkup(row_width=3)
    buttons = [
        InlineKeyboardButton("6", callback_data="digits_6", style="primary"),
        InlineKeyboardButton("8", callback_data="digits_8", style="primary"),
        InlineKeyboardButton("10", callback_data="digits_10", style="primary"),
        InlineKeyboardButton("12 ✅", callback_data="digits_12", style="primary"),
        InlineKeyboardButton("14", callback_data="digits_14", style="primary"),
        InlineKeyboardButton("16", callback_data="digits_16", style="primary"),
    ]
    markup.add(*buttons[:3])
    markup.add(*buttons[3:6])
    markup.add(
        InlineKeyboardButton(
            "❌ إلغاء",
            callback_data="cancel",
            style="danger",
            icon_custom_emoji_id="5060247798616687432"
        )
    )
    return markup

def create_date_keyboard() -> InlineKeyboardMarkup:
    """لوحة اختيار وضع التاريخ"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(
            "📅 ثابت",
            callback_data="date_fixed",
            style="primary"
        ),
        InlineKeyboardButton(
            "🎲 متغير",
            callback_data="date_random",
            style="primary"
        )
    )
    markup.add(
        InlineKeyboardButton(
            "❌ إلغاء",
            callback_data="cancel",
            style="danger",
            icon_custom_emoji_id="5060247798616687432"
        )
    )
    return markup

def create_cvv_keyboard() -> InlineKeyboardMarkup:
    """لوحة اختيار وضع CVV"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(
            "🔐 ثابت",
            callback_data="cvv_fixed",
            style="primary"
        ),
        InlineKeyboardButton(
            "🎲 متغير",
            callback_data="cvv_random",
            style="primary"
        )
    )
    markup.add(
        InlineKeyboardButton(
            "❌ إلغاء",
            callback_data="cancel",
            style="danger",
            icon_custom_emoji_id="5060247798616687432"
        )
    )
    return markup

def create_count_keyboard() -> InlineKeyboardMarkup:
    """لوحة اختيار عدد البطاقات"""
    markup = InlineKeyboardMarkup(row_width=3)
    buttons = [
        InlineKeyboardButton("5", callback_data="count_5", style="primary"),
        InlineKeyboardButton("10 ✅", callback_data="count_10", style="success"),
        InlineKeyboardButton("20", callback_data="count_20", style="primary"),
        InlineKeyboardButton("50", callback_data="count_50", style="primary"),
        InlineKeyboardButton("100", callback_data="count_100", style="primary"),
        InlineKeyboardButton("200", callback_data="count_200", style="primary"),
    ]
    markup.add(*buttons[:3])
    markup.add(*buttons[3:6])
    markup.add(
        InlineKeyboardButton(
            "❌ إلغاء",
            callback_data="cancel",
            style="danger",
            icon_custom_emoji_id="5060247798616687432"
        )
    )
    return markup

# ══════════════════════════════════════════════════════════════
# ██  معالجات الأوامر  ██
# ══════════════════════════════════════════════════════════════

@bot.message_handler(commands=['start'])
def start_command(message):
    """معالج أمر /start مع فيديو ترحيبي"""
    uid = message.from_user.id
    name = message.from_user.first_name or "صديقي"
    username = message.from_user.username or name
    
    # تحديث الإحصائيات
    stats = load_stats()
    stats["total_users"] += 1
    save_stats(stats)
    
    # حفظ إعدادات المستخدم
    settings = load_user_settings(uid)
    settings["name"] = name
    save_user_settings(uid, settings)
    
    # نص الفيديو المزخرف (بدون كليشهات)
    video_caption = f"""
🌟 *GEN PRO* 🌟
━━━━━━━━━━━━━━━━━━━
✨ *Welcome / أهلاً بك* ✨
└─ @{username}

📤 *Send .txt file to start*
📌 *الصيغة: `NUM|MM|YY|CVV`*

━━━━━━━━━━━━━━━━━━━
⚡ *{BOT_TAG} · v{VERSION}*
"""
    
    # ✅ فيديو ترحيبي مع النص الجديد
    try:
        bot.send_video(
            message.chat.id,
            video="https://t.me/Mustafa964iq/3",
            caption=video_caption,
            parse_mode="Markdown",
            reply_markup=create_main_menu(uid)
        )
    except Exception as e:
        # لو فشل الفيديو، يرسل نص بديل
        bot.send_message(
            message.chat.id,
            f"👋 أهلاً بك *{name}*\n📤 أرسل ملف `.txt` لبدء التوليد",
            parse_mode="Markdown",
            reply_markup=create_main_menu(uid)
        )
        logger.error(f"Video send failed: {e}")# ██  معالجات الأزرار  ██
# ══════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: call.data == "upload_file")
def upload_file_callback(call):
    """معالج زر رفع الملف"""
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        "📤 *أرسل ملف `.txt` الآن*\n\n"
        "┌─────────────────────┐\n"
        "│ الصيغة: `NUM|MM|YY|CVV`\n"
        "│ مثال: `4111111111111111|08|26|123`\n"
        "└─────────────────────┘",
        parse_mode="Markdown",
        reply_markup=create_back_button()
    )
    user_steps[call.from_user.id] = "waiting_file"
@bot.message_handler(commands=['start'])
def start_command(message):
    """معالج أمر /start مع فيديو ترحيبي"""
    uid = message.from_user.id
    name = message.from_user.first_name or "صديقي"
    
    # تحديث الإحصائيات
    stats = load_stats()
    stats["total_users"] += 1
    save_stats(stats)
    
    # حفظ إعدادات المستخدم
    settings = load_user_settings(uid)
    settings["name"] = name
    save_user_settings(uid, settings)
    
    # نص الفيديو المزخرف
    video_caption = f"""
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃        🔥 *GEN PRO* 🔥          ┃
┃    {BOT_TAG} · v{VERSION}       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

✨ *Welcome / أهلاً بك* ✨
└── @{message.from_user.username or name}

┌────────────────────────────────┐
│  📤 *أرسل ملف `.txt` لبدء العمل* │
│  📌 الصيغة: `NUM|MM|YY|CVV`     │
└────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ *Powered by @o8380* ⚡
"""
    
    # إرسال فيديو ترحيبي
    try:
        bot.send_video(
            message.chat.id,
            video="https://t.me/Mustafa964iq/3",
            caption=video_caption,
            parse_mode="Markdown",
            reply_markup=create_main_menu(uid)
        )
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"👋 أهلاً بك *{name}*\n📤 أرسل ملف `.txt` لبدء التوليد",
            parse_mode="Markdown",
            reply_markup=create_main_menu(uid)
        )
        logger.error(f"Video send failed: {e}")# ══════════════════════════════════════════════════════════════
# ██  معالج رفع الملف  ██
# ══════════════════════════════════════════════════════════════

@bot.message_handler(content_types=['document'])
def handle_document(message):
    """معالج رفع الملفات"""
    uid = message.from_user.id
    
    if user_steps.get(uid) != "waiting_file":
        bot.reply_to(
            message,
            "❌ يرجى الضغط على زر 📤 رفع ملف أولاً",
            reply_markup=create_main_menu(uid)
        )
        return
    
    if not message.document.file_name.endswith('.txt'):
        bot.reply_to(message, "❌ يرجى إرسال ملف `.txt` فقط")
        return
    
    status_msg = bot.reply_to(message, "🔄 **جاري معالجة الملف...**", parse_mode="Markdown")
    
    try:
        # تحميل الملف
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        # قراءة المحتوى
        content = downloaded.decode('utf-8', errors='ignore')
        lines = content.splitlines()
        
        # تصفية البطاقات
        filtered = filter_cards(lines)
        valid_cards = filtered["valid"]
        
        if not valid_cards:
            bot.edit_message_text(
                f"""❌ *لا توجد بطاقات صالحة!*

📊 الإحصائيات:
├ الأصلي: `{filtered['original']}`
├ غير صالحة: `{filtered['invalid']}`
├ منتهية: `{filtered['expired']}`
├ فشل Luhn: `{filtered['luhn_fail']}`
└ مكررة: `{filtered['dup_card'] + filtered['dup_bin']}`

━━━━━━━━━━━━━━━━━━━━━━━━
🏷 {BOT_TAG}""",
                message.chat.id,
                status_msg.message_id,
                parse_mode="Markdown"
            )
            return
        
        # تحليل BINs (مخفي)
        bot.edit_message_text(
            "🔄 **جاري تحليل البطاقات...**\n_(قد يستغرق بضع ثوانٍ)_",
            message.chat.id,
            status_msg.message_id,
            parse_mode="Markdown"
        )
        
        analyzed = analyze_bins(valid_cards)
        
        # AI تحليل مخفي (فقط للتسجيل)
        if ai_client:
            ai_result = ai_hidden_analysis(analyzed)
            if ai_result:
                logger.info(f"AI Analysis for {uid}: {ai_result}")
        
        # حفظ البيانات
        user_data[uid] = {
            "analyzed": analyzed,
            "filtered": filtered,
            "status_msg_id": status_msg.message_id
        }
        
        # تحديث الإحصائيات
        stats = load_stats()
        stats["total_files"] += 1
        save_stats(stats)
        
        # عرض ملخص بسيط ثم السؤال الأول
        bot.edit_message_text(
            f"""✅ *تم تحليل الملف بنجاح!*

📁 البطاقات الصالحة: `{len(valid_cards)}`
🗂 عدد BINs الفريدة: `{len(analyzed)}`

━━━━━━━━━━━━━━━━━━━━━━━━
📏 *كم رقم تريد تاخذ من البطاقة الأصلية؟*
(الباقي يُولَّد عشوائياً + Luhn مضمون)

✅ الافتراضي الموصى به: `12`""",
            message.chat.id,
            status_msg.message_id,
            parse_mode="Markdown",
            reply_markup=create_digits_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        bot.edit_message_text(
            f"❌ *خطأ في معالجة الملف:*\n`{str(e)[:100]}`",
            message.chat.id,
            status_msg.message_id,
            parse_mode="Markdown"
        )

# ══════════════════════════════════════════════════════════════
# ██  معالجات اختيارات المستخدم  ██
# ══════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: call.data.startswith("digits_"))
def digits_callback(call):
    """معالج اختيار عدد الأرقام"""
    uid = call.from_user.id
    digits = int(call.data.split("_")[1])
    
    if uid not in user_data:
        bot.answer_callback_query(call.id, "❌ انتهت الجلسة. أعد رفع الملف")
        return
    
    user_data[uid]["digits"] = digits
    
    bot.edit_message_text(
        "📅 *اختر وضع التاريخ:*",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=create_date_keyboard()
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("date_"))
def date_callback(call):
    """معالج اختيار وضع التاريخ"""
    uid = call.from_user.id
    date_mode = call.data.split("_")[1]
    
    if uid not in user_data:
        bot.answer_callback_query(call.id, "❌ انتهت الجلسة. أعد رفع الملف")
        return
    
    user_data[uid]["date_mode"] = date_mode
    
    bot.edit_message_text(
        "🔐 *اختر وضع CVV:*",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=create_cvv_keyboard()
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cvv_"))
def cvv_callback(call):
    """معالج اختيار وضع CVV"""
    uid = call.from_user.id
    cvv_mode = call.data.split("_")[1]
    
    if uid not in user_data:
        bot.answer_callback_query(call.id, "❌ انتهت الجلسة. أعد رفع الملف")
        return
    
    user_data[uid]["cvv_mode"] = cvv_mode
    
    bot.edit_message_text(
        "🔢 *كم بطاقة تريد توليدها من كل BIN؟*",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=create_count_keyboard()
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("count_"))
def count_callback(call):
    """معالج اختيار عدد البطاقات والتوليد النهائي"""
    uid = call.from_user.id
    count = int(call.data.split("_")[1])
    
    if uid not in user_data:
        bot.answer_callback_query(call.id, "❌ انتهت الجلسة. أعد رفع الملف")
        return
    
    data = user_data[uid]
    digits = data.get("digits", 12)
    date_mode = data.get("date_mode", "fixed")
    cvv_mode = data.get("cvv_mode", "random")
    analyzed = data.get("analyzed", [])
    
    if not analyzed:
        bot.answer_callback_query(call.id, "❌ لا توجد بطاقات صالحة")
        return
    
    bot.edit_message_text(
        "⚙️ **جاري توليد البطاقات...**\n_(قد يستغرق بضع ثوانٍ)_",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )
    
    # توليد البطاقات في خيط منفصل
    def generate_and_send():
        all_cards = []
        seen = set()
        
        for card in analyzed:
            generated = generate_cards(card, digits, date_mode, cvv_mode, count)
            for card_line in generated:
                if card_line not in seen:
                    seen.add(card_line)
                    all_cards.append(card_line)
        
        if not all_cards:
            bot.send_message(
                call.message.chat.id,
                "❌ *فشل التوليد.* حاول مجدداً.",
                parse_mode="Markdown",
                reply_markup=create_main_menu(uid)
            )
            return
        
        # حفظ الملف
        output_file = TEMP_DIR / f"{uid}_output.txt"
        output_file.write_text("\n".join(all_cards), encoding="utf-8")
        
        # تحديث الإحصائيات
        stats = load_stats()
        stats["total_generated"] += len(all_cards)
        save_stats(stats)
        
        # إرسال الملف
        caption = f"""╔══════════════════════════╗
║  🎉  *تم التوليد بنجاح!*  ║
╚══════════════════════════╝

├ 🆕 البطاقات المولدة: `{len(all_cards)}`
├ 🗂 عدد BINs المستخدمة: `{len(analyzed)}`
├ 📏 طول الرقم: `{digits}`
├ 📅 التاريخ: `{'ثابت' if date_mode == 'fixed' else 'عشوائي'}`
├ 🔐 CVV: `{'ثابت' if cvv_mode == 'fixed' else 'عشوائي'}`
└ ✅ Luhn: `مضمون 100%`

━━━━━━━━━━━━━━━━━━━━━━━━
🏷 {BOT_TAG} · v{VERSION}"""

        with open(output_file, 'rb') as f:
            bot.send_document(
                call.message.chat.id,
                f,
                caption=caption,
                parse_mode="Markdown"
            )
        
        # حذف الملف المؤقت
        try:
            output_file.unlink()
        except:
            pass
        
        # حذف بيانات الجلسة
        user_data.pop(uid, None)
        
        # إرسال زر الرجوع للقائمة
        bot.send_message(
            call.message.chat.id,
            "✅ *اكتمل التوليد!*\n\nاضغط /start للبدء من جديد",
            parse_mode="Markdown",
            reply_markup=create_main_menu(uid)
        )
    
    threading.Thread(target=generate_and_send).start()
    bot.answer_callback_query(call.id)

# ══════════════════════════════════════════════════════════════
# ██  أوامر المالك (Admin)  ██
# ══════════════════════════════════════════════════════════════

@bot.message_handler(commands=['admin'])
def admin_command(message):
    """لوحة تحكم المالك (تظهر فقط للمالك)"""
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "⛔ هذا الأمر للمالك فقط")
        return
    
    stats = load_stats()
    bins = load_private_bins()
    
    pc = sum(1 for v in bins.values() if v.get("classification") == "private")
    sc = sum(1 for v in bins.values() if v.get("classification") == "semi")
    pub = sum(1 for v in bins.values() if v.get("classification") == "public")
    
    text = f"""
╔══════════════════════════╗
║  📊  *لوحة التحكم*  ║
╚══════════════════════════╝

👥 المستخدمون: `{stats.get('total_users', 0)}`
📁 ملفات محللة: `{stats.get('total_files', 0)}`
🆕 بطاقات مولدة: `{stats.get('total_generated', 0)}`

🗄 *قاعدة BINs الخاصة:*
├ 🔒 Private: `{pc}`
├ 📈 Semi: `{sc}`
└ 🌐 Public: `{pub}`
   المجموع: `{len(bins)}`

━━━━━━━━━━━━━━━━━━━━━━━━
🏷 {BOT_TAG} · v{VERSION}
"""
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['exportbins'])
def export_bins_command(message):
    """تصدير قاعدة BINs الخاصة (للمالك فقط)"""
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "⛔ هذا الأمر للمالك فقط")
        return
    
    bins = load_private_bins()
    if not bins:
        bot.reply_to(message, "❌ لا توجد BINs خاصة")
        return
    
    lines = [f"{b} | {v.get('classification', '?')} | {v.get('info', {}).get('scheme', '')}" 
             for b, v in bins.items()]
    content = "\n".join(lines)
    
    export_file = TEMP_DIR / f"bins_export_{int(time.time())}.txt"
    export_file.write_text(content, encoding="utf-8")
    
    with open(export_file, 'rb') as f:
        bot.send_document(
            message.chat.id,
            f,
            caption=f"📤 *قاعدة BINs الخاصة*\n📊 العدد: {len(bins)}",
            parse_mode="Markdown"
        )
    
    try:
        export_file.unlink()
    except:
        pass

@bot.message_handler(commands=['clearbins'])
def clearbins_command(message):
    """مسح قاعدة BINs الخاصة (للمالك فقط)"""
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "⛔ هذا الأمر للمالك فقط")
        return
    
    save_private_bins({})
    bot.reply_to(message, "✅ تم مسح قاعدة BINs الخاصة")

# ══════════════════════════════════════════════════════════════
# ██  تشغيل البوت  ██
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║              🔥 Card Generator Pro — by @o8380              ║
║                                                              ║
║              Version: 4.0 Pro | telebot                     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    print(f"✅ Bot Token: {BOT_TOKEN[:10]}...")
    print(f"✅ Owner ID: {OWNER_ID}")
    print(f"✅ OpenAI: {'Enabled' if ai_client else 'Disabled'}")
    print(f"✅ Data Directory: {DATA_DIR}")
    print("\n🚀 Bot is running...\n")
    
    while True:
        try:
            bot.infinity_polling(timeout=30, skip_pending=True)
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(5)
