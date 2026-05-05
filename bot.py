import telebot
from telebot import types
import os
import random
import re
import time
import threading
from datetime import datetime

# ==================== التوكن والإعدادات ====================
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 1013384909
BOT_NAME = "Mustafa Checker Bot"
BOT_USERNAME = "@o8380"
VERSION = "7.2"

bot = telebot.TeleBot(BOT_TOKEN)

# مجلد للرفع
TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)

user_data = {}  # {user_id: {"cards": [], "file_path": ""}}

# ==================== دوال مساعدة ====================
def read_cards_from_file(file_path):
    """قراءة البطاقات من الملف وأخذ أول 12 رقم فقط"""
    cards = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line:
                    # استخراج أول 12 رقم من أي صيغة
                    numbers = re.findall(r'\d+', line)
                    if numbers:
                        card_num = numbers[0].replace(' ', '').replace('-', '')
                        if len(card_num) >= 12:
                            cards.append(card_num[:12])
    except Exception as e:
        print(f"Error reading: {e}")
    return cards

def generate_random_number(length):
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])

def generate_random_date():
    """تاريخ عشوائي بين 2026-2032"""
    year = random.randint(2026, 2032)
    month = random.randint(1, 12)
    return f"{month:02d}|{str(year)[-2:]}"

def generate_cards(bin_12, count=10, fixed_date=None, fixed_cvv=None):
    """توليد بطاقات جديدة من أول 12 رقم"""
    cards = []
    for _ in range(count):
        remaining = generate_random_number(4)
        full_card = bin_12 + remaining
        date = fixed_date if fixed_date else generate_random_date()
        cvv = fixed_cvv if fixed_cvv else generate_random_number(3)
        cards.append(f"{full_card}|{date}|{cvv}")
    return cards

def save_cards_to_file(cards, filename):
    filepath = os.path.join(TEMP_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(cards))
    return filepath

# ==================== واجهة الأزرار الرئيسية ====================
def create_main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.row(
        types.InlineKeyboardButton("🟢 CVV+تاريخ عشوائي", callback_data="mode_1", style="success", icon_custom_emoji_id="5992195984623408246"),
        types.InlineKeyboardButton("🔵 تاريخ ثابت / CVV عشوائي", callback_data="mode_2", style="primary", icon_custom_emoji_id="5992246772611681940")
    )
    markup.row(
        types.InlineKeyboardButton("🔴 CVV ثابت / تاريخ عشوائي", callback_data="mode_3", style="danger", icon_custom_emoji_id="5060247798616687432"),
        types.InlineKeyboardButton("🟢 إلغاء العملية", callback_data="cancel", style="success", icon_custom_emoji_id="5060115075537306714")
    )
    
    return markup

# ==================== أمر /start ====================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_name = message.from_user.first_name
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📤 إرسال ملف", callback_data="upload_file", style="primary"))
    
    bot.send_message(
        message.chat.id,
        f"✨ **أهلاً بك {user_name} في {BOT_NAME}** ✨\n\n"
        f"📌 **الأداة الاحترافية لتوليد البطاقات**\n"
        f"• يتم أخذ أول 12 رقم من كل بطاقة في ملفك\n"
        f"• توليد 10 بطاقات جديدة من كل رقم\n"
        f"• خيارات متعددة: CVV وتاريخ عشوائي أو ثابت\n\n"
        f"🔹 **المطور:** {BOT_USERNAME}\n"
        f"🔹 **الإصدار:** {VERSION}\n\n"
        f"👇 **أرسل ملف `.txt` أو اضغط الزر بالأسفل**",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "upload_file")
def request_file(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "📤 أرسل لي ملف `.txt` يحتوي على البطاقات")

# ==================== استقبال الملفات ====================
@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    
    if not message.document.file_name.endswith('.txt'):
        bot.reply_to(message, "❌ يرجى إرسال ملف `.txt` فقط")
        return
    
    # تحميل الملف
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    file_path = os.path.join(TEMP_DIR, f"{user_id}_input.txt")
    with open(file_path, 'wb') as f:
        f.write(downloaded_file)
    
    # قراءة البطاقات
    cards = read_cards_from_file(file_path)
    
    if not cards:
        bot.reply_to(message, "❌ الملف لا يحتوي على بطاقات صالحة (الصيغة المطلوبة: أرقام فقط، 12 رقم على الأقل)")
        os.remove(file_path)
        return
    
    user_data[user_id] = {
        "cards": cards,
        "file_path": file_path
    }
    
    bot.send_message(
        message.chat.id,
        f"📊 **تم رفع الملف بنجاح**\n"
        f"• عدد البطاقات الأصلية: `{len(cards)}`\n\n"
        f"🎯 **اختر طريقة المعالجة:**",
        parse_mode="Markdown",
        reply_markup=create_main_menu()
    )

# ==================== معالجة الأزرار ====================
@bot.callback_query_handler(func=lambda call: call.data in ["mode_1", "mode_2", "mode_3", "cancel"])
def process_mode(call):
    user_id = call.from_user.id
    data = user_data.get(user_id)
    
    if not data:
        bot.answer_callback_query(call.id, "❌ جلسة منتهية! أرسل الملف مرة أخرى.", show_alert=True)
        bot.send_message(call.message.chat.id, "📤 أرسل ملف `.txt` جديد")
        return
    
    if call.data == "cancel":
        bot.answer_callback_query(call.id, "✅ تم الإلغاء")
        bot.edit_message_text("✅ تم إلغاء العملية", call.message.chat.id, call.message.message_id)
        return
    
    bot.answer_callback_query(call.id, "🔄 جاري المعالجة...")
    bot.edit_message_text("🔄 جاري توليد البطاقات...", call.message.chat.id, call.message.message_id)
    
    cards_bin = data["cards"]
    generated_cards = []
    mode_name = ""
    
    if call.data == "mode_1":
        mode_name = "CVV+تاريخ عشوائي 🟢"
        for bin12 in cards_bin:
            generated_cards.extend(generate_cards(bin12, count=10))
    elif call.data == "mode_2":
        mode_name = "تاريخ ثابت / CVV عشوائي 🔵"
        for bin12 in cards_bin:
            generated_cards.extend(generate_cards(bin12, count=10, fixed_date="01|26"))
    elif call.data == "mode_3":
        mode_name = "CVV ثابت / تاريخ عشوائي 🔴"
        for bin12 in cards_bin:
            generated_cards.extend(generate_cards(bin12, count=10, fixed_cvv="123"))
    
    # حفظ وإرسال الملف
    output_file = save_cards_to_file(generated_cards, f"{user_id}_output_{call.data}.txt")
    
    with open(output_file, 'rb') as f:
        bot.send_document(
            call.message.chat.id,
            f,
            caption=(
                f"✅ **تم التوليد بنجاح**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📁 البطاقات الأصلية: `{len(cards_bin)}`\n"
                f"🆕 البطاقات المُولدة: `{len(generated_cards)}`\n"
                f"⚙️ **الوضع:** {mode_name}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔹 **المطور:** {BOT_USERNAME}\n"
                f"🔹 **الإصدار:** {VERSION}"
            ),
            parse_mode="Markdown"
        )
    
    # تنظيف
    os.remove(output_file)
    os.remove(data["file_path"])
    del user_data[user_id]

# ==================== تشغيل البوت ====================
if __name__ == "__main__":
    print(f"🚀 {BOT_NAME} V{VERSION} is running...")
    print(f"👤 Developer: {BOT_USERNAME}")
    
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
