import os
import re
import random
import time
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

# إزالة أي تعارض
try:
    bot.remove_webhook()
except:
    pass

time.sleep(1)


# ==================== دوال مساعدة ====================

def extract_bin_and_date(card):
    """استخراج أول 6 أرقام (BIN) والتاريخ من البطاقة"""
    parts = card.split('|')
    if len(parts) >= 4:
        card_num = parts[0].strip()
        month = parts[1].strip()
        year = parts[2].strip()
        cvv = parts[3].strip()
        
        if len(year) == 4:
            year = year[-2:]
        
        first6 = card_num[:6] if len(card_num) >= 6 else card_num
        first12 = card_num[:12] if len(card_num) >= 12 else card_num
        
        return first6, first12, month, year, cvv
    
    return None, None, None, None, None

def random_digits(length):
    """توليد أرقام عشوائية بطول محدد"""
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])

def generate_cards_from_bin(first6, first12, month, year, count=10):
    """توليد بطاقات جديدة من BIN والتاريخ"""
    cards = []
    generated_last4 = set()
    generated_cvv = set()
    
    for _ in range(count):
        last4 = random_digits(4)
        while last4 in generated_last4:
            last4 = random_digits(4)
        generated_last4.add(last4)
        
        cvv = random_digits(3)
        while cvv in generated_cvv:
            cvv = random_digits(3)
        generated_cvv.add(cvv)
        
        full_card_num = first12 + last4
        card = f"{full_card_num}|{month}|{year}|{cvv}"
        cards.append(card)
    
    return cards

def get_bin_info(bin6):
    """جلب معلومات BIN من API"""
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

def main_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📤 رفع ملف", callback_data="upload_file"))
    markup.add(InlineKeyboardButton("ℹ️ معلومات", callback_data="info"))
    return markup


# ==================== الأوامر ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    user_name = message.from_user.first_name or message.from_user.username or "صديقي"
    
    # رسالة واحدة فقط
    bot.send_message(
        message.chat.id,
        f"✨ أهلاً بك يا `{user_name}` ✨\n\n📤 أرسل ملف `.txt` لبدء التوليد",
        parse_mode='Markdown',
        reply_markup=main_menu()
    )

@bot.callback_query_handler(func=lambda call: call.data == "upload_file")
def upload_hint(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "📤 أرسل ملف `.txt` الآن")

@bot.callback_query_handler(func=lambda call: call.data == "info")
def info_callback(call):
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"📌 **معلومات البوت**\n\n"
        f"🔹 يستخرج أول 12 رقم + التاريخ من كل بطاقة\n"
        f"🔹 يولد 10 بطاقات جديدة من كل بطاقة\n"
        f"🔹 التاريخ ثابت كما هو\n"
        f"🔹 آخر 4 أرقام و CVV عشوائية\n\n"
        f"🔹 {BOT_USERNAME} | V{VERSION}",
        parse_mode='Markdown'
    )


# ==================== معالجة الملفات ====================

@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    
    if not message.document.file_name.endswith('.txt'):
        bot.reply_to(message, "❌ يرجى إرسال ملف `.txt` فقط")
        return
    
    status_msg = bot.reply_to(message, "🔄 **جاري المعالجة...**", parse_mode='Markdown')
    
    # تحميل الملف
    file_info = bot.get_file(message.document.file_id)
    downloaded = bot.download_file(file_info.file_path)
    
    input_path = os.path.join(TEMP_DIR, f"{user_id}_input.txt")
    with open(input_path, 'wb') as f:
        f.write(downloaded)
    
    # قراءة البطاقات
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
    
    # المعالجة
    seen_bins = set()
    all_generated = []
    processed = 0
    skipped = 0
    
    for card in original_cards:
        first6, first12, month, year, cvv_original = extract_bin_and_date(card)
        
        if not first6 or not month or not year:
            skipped += 1
            continue
        
        if first6 in seen_bins:
            skipped += 1
            continue
        seen_bins.add(first6)
        
        new_cards = generate_cards_from_bin(first6, first12, month, year, count=10)
        all_generated.extend(new_cards)
        processed += 1
    
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
    
    # إرسال النتيجة
    with open(output_path, 'rb') as f:
        bot.send_document(
            message.chat.id,
            f,
            caption=(
                f"✅ **تم التوليد بنجاح**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📁 الأصلي: `{len(original_cards)}`\n"
                f"✅ المعالجة: `{processed}`\n"
                f"⏭️ المتخطية: `{skipped}`\n"
                f"🆕 الجديدة: `{len(all_generated)}`\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔹 {BOT_USERNAME}"
            ),
            parse_mode='Markdown'
        )
    
    os.remove(output_path)
    
    bot.edit_message_text(
        f"✅ تم توليد `{len(all_generated)}` بطاقة جديدة",
        message.chat.id,
        status_msg.message_id,
        parse_mode='Markdown'
    )


# ==================== أمر /gen يدوي ====================

@bot.message_handler(commands=['gen'])
def gen_command(message):
    text = message.text.strip()
    parts = text.split()
    
    if len(parts) < 2:
        bot.reply_to(
            message,
            "❌ `/gen 464005776057|08|2026|`\nأو\n`/gen 464005`",
            parse_mode='Markdown'
        )
        return
    
    card_input = parts[1]
    
    if '|' in card_input:
        bin_part = card_input.split('|')[0]
        month = card_input.split('|')[1] if len(card_input.split('|')) > 1 else "08"
        year = card_input.split('|')[2] if len(card_input.split('|')) > 2 else "26"
        if len(year) == 4:
            year = year[-2:]
    else:
        bin_part = card_input
        month = "08"
        year = "26"
    
    first6 = bin_part[:6] if len(bin_part) >= 6 else bin_part
    first12 = bin_part[:12] if len(bin_part) >= 12 else bin_part.ljust(12, '0')
    
    cards = generate_cards_from_bin(first6, first12, month, year, count=10)
    
    response = f"✨ **BIN {first6}** ✨\n━━━━━━━━━━━━━━━━━━\n"
    for card in cards:
        response += f"`{card}`\n"
    response += f"━━━━━━━━━━━━━━━━━━\n🔹 {BOT_USERNAME}"
    
    bot.reply_to(message, response, parse_mode='Markdown')


# ==================== التشغيل ====================

if __name__ == "__main__":
    print(f"✅ بوت {BOT_USERNAME} شغال...")
    
    while True:
        try:
            bot.infinity_polling(timeout=30, skip_pending=True)
        except Exception as e:
            print(f"❌ خطأ: {e}")
            time.sleep(5)
