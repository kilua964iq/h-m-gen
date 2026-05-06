import os
import re
import random
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# توكن البوت
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    BOT_TOKEN = "ضع_توكنك_هنا"

# إعدادات
BOT_USERNAME = "@o8380"
VERSION = "1.0"
TEMP_DIR = "temp_files"

os.makedirs(TEMP_DIR, exist_ok=True)

# إنشاء البوت
bot = telebot.TeleBot(BOT_TOKEN)


# ==================== دوال مساعدة ====================

def clean_number(text):
    """استخراج أول 12 رقم فقط من أي نص"""
    digits = re.sub(r'\D', '', text)  # حذف كل شيء ما عدا الأرقام
    if len(digits) >= 12:
        return digits[:12]
    return None

def extract_date(card_line):
    """استخراج التاريخ من البطاقة وتحويل 2026 إلى 26"""
    # البحث عن تاريخ بصيغة MM|YYYY أو MM|YY
    match = re.search(r'(\d{2})\|(\d{2,4})', card_line)
    if match:
        month = match.group(1)
        year = match.group(2)
        if len(year) == 4:
            year = year[-2:]  # 2026 -> 26
        return f"{month}|{year}"
    return None

def random_digits(length):
    """توليد أرقام عشوائية بطول محدد"""
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])

def generate_new_card(first12, date, count=10):
    """توليد 10 بطاقات جديدة من أول 12 رقم والتاريخ"""
    cards = []
    seen_cvv = set()  # لتجنب تكرار CVV
    
    for _ in range(count):
        # آخر 4 أرقام عشوائية
        last4 = random_digits(4)
        # CVV عشوائي 3 أرقام
        cvv = random_digits(3)
        
        # التأكد من عدم تكرار CVV (اختياري)
        while cvv in seen_cvv:
            cvv = random_digits(3)
        seen_cvv.add(cvv)
        
        full_card = f"{first12}{last4}|{date}|{cvv}"
        cards.append(full_card)
    
    return cards


# ==================== الأزرار ====================

def start_btn():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📤 أرسل ملف البطاقات", callback_data="upload_file"))
    return markup


# ==================== الأوامر ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(
        message.chat.id,
        f"✨ بوت توليد البطاقات الذكي ✨\n\n"
        f"📌 **كيف يعمل:**\n"
        f"1️⃣ أرسل ملف txt يحتوي على بطاقات\n"
        f"2️⃣ يستخرج أول 12 رقم من كل بطاقة\n"
        f"3️⃣ يحافظ على التاريخ الأصلي\n"
        f"4️⃣ يولد 4 أرقام عشوائية + CVV عشوائي\n"
        f"5️⃣ ينتج 10 بطاقات جديدة من كل بطاقة\n\n"
        f"🔹 {BOT_USERNAME} | الإصدار {VERSION}",
        parse_mode='Markdown',
        reply_markup=start_btn()
    )

@bot.callback_query_handler(func=lambda call: call.data == "upload_file")
def upload_hint(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "📤 أرسل ملف `.txt` الآن", parse_mode='Markdown')


# ==================== معالجة الملفات ====================

@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    
    # التحقق من نوع الملف
    if not message.document.file_name.endswith('.txt'):
        bot.reply_to(message, "❌ يرجى إرسال ملف `.txt` فقط")
        return
    
    # تحميل الملف
    file_info = bot.get_file(message.document.file_id)
    downloaded = bot.download_file(file_info.file_path)
    
    input_path = os.path.join(TEMP_DIR, f"{user_id}_input.txt")
    with open(input_path, 'wb') as f:
        f.write(downloaded)
    
    # قراءة البطاقات من الملف
    cards = []
    with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if line:
                cards.append(line)
    
    if not cards:
        bot.reply_to(message, "❌ الملف فارغ!")
        os.remove(input_path)
        return
    
    # معالجة البطاقات
    bot.send_message(message.chat.id, "🔄 جاري معالجة البطاقات...")
    
    seen_first12 = set()  # لتجنب تكرار أول 12 رقم
    all_generated = []
    stats_processed = 0
    stats_skipped = 0
    
    for card in cards:
        # استخراج أول 12 رقم
        first12 = clean_number(card)
        if not first12:
            stats_skipped += 1
            continue
        
        # التحقق من التكرار
        if first12 in seen_first12:
            stats_skipped += 1
            continue
        seen_first12.add(first12)
        
        # استخراج التاريخ
        date = extract_date(card)
        if not date:
            date = "08|26"  # تاريخ افتراضي إذا لم يوجد
        
        # توليد 10 بطاقات جديدة
        new_cards = generate_new_card(first12, date, count=10)
        all_generated.extend(new_cards)
        stats_processed += 1
    
    # تنظيف الملف المؤقت
    os.remove(input_path)
    
    # حفظ النتائج
    output_path = os.path.join(TEMP_DIR, f"{user_id}_output.txt")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(all_generated))
    
    # إرسال الملف الناتج
    with open(output_path, 'rb') as f:
        bot.send_document(
            message.chat.id,
            f,
            caption=(
                f"✅ **تم التوليد بنجاح**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📁 البطاقات الأصلية: {len(cards)}\n"
                f"✅ تمت معالجتها: {stats_processed}\n"
                f"⏭️ تم تخطيها (مكررة): {stats_skipped}\n"
                f"🆕 البطاقات المولدة: {len(all_generated)}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔹 {BOT_USERNAME} | V{VERSION}"
            ),
            parse_mode='Markdown'
        )
    
    # حذف الملف المؤقت
    os.remove(output_path)


# ==================== التشغيل ====================

if __name__ == "__main__":
    print(f"✅ بوت {BOT_USERNAME} شغال...")
    bot.infinity_polling(timeout=30)
