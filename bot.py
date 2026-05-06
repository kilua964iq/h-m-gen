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
VERSION = "2.0"
TEMP_DIR = "temp_files"

os.makedirs(TEMP_DIR, exist_ok=True)

# إنشاء البوت
bot = telebot.TeleBot(BOT_TOKEN)


# ==================== دوال مساعدة ====================

def extract_bin_and_date(card):
    """
    استخراج أول 6 أرقام (BIN) والتاريخ من البطاقة
    الإدخال: xxxxxxxxxxxxxxxx|MM|YY|CVV
    الإخراج: (first6, month, year, last4_original, cvv_original)
    """
    parts = card.split('|')
    if len(parts) >= 4:
        card_num = parts[0].strip()
        month = parts[1].strip()
        year = parts[2].strip()
        cvv = parts[3].strip()
        
        # معالجة السنة (2026 -> 26)
        if len(year) == 4:
            year = year[-2:]
        
        # أول 6 أرقام (BIN)
        first6 = card_num[:6] if len(card_num) >= 6 else card_num
        
        # أول 12 رقم (للحفاظ على البطاقة)
        first12 = card_num[:12] if len(card_num) >= 12 else card_num
        
        # آخر 4 أرقام أصلية (للمعلومات فقط)
        last4_original = card_num[-4:] if len(card_num) >= 4 else ""
        
        return first6, first12, month, year, last4_original, cvv
    
    return None, None, None, None, None, None

def random_digits(length):
    """توليد أرقام عشوائية بطول محدد"""
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])

def generate_cards_from_bin(first6, first12, month, year, count=10):
    """
    توليد بطاقات جديدة من BIN والتاريخ
    يولد آخر 4 أرقام عشوائية + CVV عشوائي
    """
    cards = []
    generated_last4 = set()  # لتجنب تكرار آخر 4 أرقام
    generated_cvv = set()    # لتجنب تكرار CVV
    
    for _ in range(count):
        # توليد آخر 4 أرقام عشوائية (غير مكررة)
        last4 = random_digits(4)
        while last4 in generated_last4:
            last4 = random_digits(4)
        generated_last4.add(last4)
        
        # توليد CVV عشوائي 3 أرقام (غير مكرر)
        cvv = random_digits(3)
        while cvv in generated_cvv:
            cvv = random_digits(3)
        generated_cvv.add(cvv)
        
        # تكوين البطاقة الكاملة: أول12 + آخر4
        full_card_num = first12 + last4
        
        # تنسيق البطاقة
        card = f"{full_card_num}|{month}|{year}|{cvv}"
        cards.append(card)
    
    return cards

def get_bin_info(bin6):
    """جلب معلومات BIN من API (اختياري)"""
    try:
        import requests
        response = requests.get(f"https://lookup.binlist.net/{bin6}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            brand = data.get('scheme', 'Unknown').upper()
            type_card = data.get('type', 'Unknown').upper()
            country = data.get('country', {}).get('name', 'Unknown')
            flag = data.get('country', {}).get('emoji', '🏳️')
            bank = data.get('bank', {}).get('name', 'Unknown')
            return f"💳 {brand} - {type_card}\n🏦 {bank}\n🌍 {country} {flag}"
    except:
        pass
    return "ℹ️ معلومات BIN غير متوفرة"


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
        f"✨ **بوت توليد البطاقات الذكي V{VERSION}** ✨\n\n"
        f"📌 **كيف يعمل:**\n"
        f"1️⃣ أرسل ملف `.txt` يحتوي على بطاقات\n"
        f"2️⃣ يستخرج أول 12 رقم + التاريخ من كل بطاقة\n"
        f"3️⃣ يحافظ على التاريخ الأصلي (MM|YY)\n"
        f"4️⃣ يولد آخر 4 أرقام عشوائية لكل بطاقة جديدة\n"
        f"5️⃣ يولد CVV عشوائي لكل بطاقة جديدة\n"
        f"6️⃣ ينتج **10 بطاقات جديدة** من كل بطاقة أصلية\n\n"
        f"📌 **صيغة البطاقة المطلوبة:**\n"
        f"`xxxxxxxxxxxxxxxx|MM|YY|CVV`\n\n"
        f"🔹 {BOT_USERNAME}",
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
    
    # إعلام المستخدم ببدء المعالجة
    status_msg = bot.reply_to(message, "🔄 **جاري معالجة البطاقات...**", parse_mode='Markdown')
    
    # تحميل الملف
    file_info = bot.get_file(message.document.file_id)
    downloaded = bot.download_file(file_info.file_path)
    
    input_path = os.path.join(TEMP_DIR, f"{user_id}_input.txt")
    with open(input_path, 'wb') as f:
        f.write(downloaded)
    
    # قراءة البطاقات من الملف
    original_cards = []
    with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if line and '|' in line:
                original_cards.append(line)
    
    if not original_cards:
        bot.reply_to(message, "❌ الملف لا يحتوي على بطاقات صالحة!")
        os.remove(input_path)
        return
    
    # معالجة البطاقات
    seen_bins = set()  # لتجنب تكرار BIN
    all_generated = []
    processed = 0
    skipped = 0
    bin_info_dict = {}
    
    for card in original_cards:
        # استخراج البيانات
        first6, first12, month, year, last4_original, cvv_original = extract_bin_and_date(card)
        
        if not first6 or not month or not year:
            skipped += 1
            continue
        
        # التحقق من عدم تكرار BIN
        if first6 in seen_bins:
            skipped += 1
            continue
        seen_bins.add(first6)
        
        # تخزين معلومات BIN (اختياري)
        if first6 not in bin_info_dict:
            bin_info_dict[first6] = get_bin_info(first6)
        
        # توليد 10 بطاقات جديدة
        new_cards = generate_cards_from_bin(first6, first12, month, year, count=10)
        all_generated.extend(new_cards)
        processed += 1
    
    # تنظيف الملف المؤقت
    os.remove(input_path)
    
    if not all_generated:
        bot.edit_message_text(
            "❌ لم يتم توليد أي بطاقات! تأكد من صيغة البطاقات.",
            message.chat.id,
            status_msg.message_id
        )
        return
    
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
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 البطاقات الأصلية: `{len(original_cards)}`\n"
                f"✅ تمت معالجتها: `{processed}`\n"
                f"⏭️ تم تخطيها: `{skipped}`\n"
                f"🆕 البطاقات المولدة: `{len(all_generated)}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔹 {BOT_USERNAME} | V{VERSION}"
            ),
            parse_mode='Markdown'
        )
    
    # حذف الملف المؤقت
    os.remove(output_path)
    
    # تحديث رسالة الحالة
    bot.edit_message_text(
        f"✅ **تم الانتهاء!**\n"
        f"📊 تم توليد `{len(all_generated)}` بطاقة جديدة",
        message.chat.id,
        status_msg.message_id,
        parse_mode='Markdown'
    )


# ==================== أمر /gen يدوي ====================

@bot.message_handler(commands=['gen'])
def gen_command(message):
    """معالجة أمر /gen يدوياً"""
    text = message.text.strip()
    parts = text.split()
    
    if len(parts) < 2:
        bot.reply_to(
            message,
            "❌ **الاستخدام الصحيح:**\n"
            "`/gen 464005776057|08|2026|`\n\n"
            "أو\n"
            "`/gen 464005` (BIN فقط + تاريخ افتراضي 08|26)",
            parse_mode='Markdown'
        )
        return
    
    card_input = parts[1]
    
    # محاولة استخراج البيانات
    if '|' in card_input:
        # صيغة: BIN|MM|YY|CVV (CVV اختياري)
        bin_part = card_input.split('|')[0]
        month = card_input.split('|')[1] if len(card_input.split('|')) > 1 else "08"
        year = card_input.split('|')[2] if len(card_input.split('|')) > 2 else "26"
        
        # معالجة السنة
        if len(year) == 4:
            year = year[-2:]
    else:
        # فقط BIN
        bin_part = card_input
        month = "08"
        year = "26"
    
    # استخراج أول 6 أرقام (BIN)
    first6 = bin_part[:6] if len(bin_part) >= 6 else bin_part
    # أول 12 رقم
    first12 = bin_part[:12] if len(bin_part) >= 12 else bin_part.ljust(12, '0')
    
    # توليد 10 بطاقات
    cards = generate_cards_from_bin(first6, first12, month, year, count=10)
    
    # جلب معلومات BIN
    bin_info = get_bin_info(first6)
    
    # تنسيق الرد
    response = f"✨ **تم توليد 10 بطاقات من BIN {first6}** ✨\n"
    response += f"━━━━━━━━━━━━━━━━━━━━━━\n"
    response += f"📅 التاريخ: `{month}|{year}`\n"
    response += f"{bin_info}\n"
    response += f"━━━━━━━━━━━━━━━━━━━━━━\n"
    
    for card in cards:
        response += f"`{card}`\n"
    
    response += f"━━━━━━━━━━━━━━━━━━━━━━\n"
    response += f"🔹 {BOT_USERNAME} | V{VERSION}"
    
    bot.reply_to(message, response, parse_mode='Markdown')


# ==================== التشغيل ====================

if __name__ == "__main__":
    print(f"✅ بوت {BOT_USERNAME} شغال...")
    print(f"📁 مجلد الملفات المؤقتة: {TEMP_DIR}")
    bot.infinity_polling(timeout=30)
