import requests
import time

TOKEN = "8726365736:AAGDQJKNiz0sqpolwGKKXU-Qbox3W6C-xJ4"

# 1. قتل أي ويبوك (webhook) بالقوة
requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")

# 2. إيقاف أي polling نشط (تحديثات) بالإكراه
requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset=-1")

# 3. نطلب من التليجرام يوقف أي شيء متعلق بهذا التوكن
requests.post(f"https://api.telegram.org/bot{TOKEN}/logout")

# 4. نكرر حذف الويبوك للتأكيد
requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")

time.sleep(2)  # نعطي التليجرام فرصة

# ===== بعد القطع الإجباري، نشغل البوت =====
import telebot
from telebot import types

bot = telebot.TeleBot(TOKEN)

# باااقي كود البوت هنا...
import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import random
import re
import time

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing from environment variables")

bot = telebot.TeleBot(BOT_TOKEN)
BOT_USERNAME = "@o8380"
VERSION = "1"

TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)

user_data = {}

# ==================== دوال مساعدة ====================

def read_numbers_from_file(file_path):
    numbers = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line:
                    digits = re.sub(r'\D', '', line)
                    if len(digits) >= 12:
                        numbers.append(digits[:12])
    except Exception as e:
        print(f"Error reading file: {e}")
    return numbers

def random_number(length):
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])

def random_date():
    year = random.randint(26, 32)
    month = random.randint(1, 12)
    return f"{month:02d}|{year:02d}"

def generate_entries(base12, count=10, fixed_date=None, fixed_cvv=None):
    result = []
    for _ in range(count):
        suffix = random_number(4)
        full = base12 + suffix
        date = fixed_date if fixed_date else random_date()
        cvv = fixed_cvv if fixed_cvv else random_number(3)
        result.append(f"{full}|{date}|{cvv}")
    return result

def save_to_file(lines, filename):
    path = os.path.join(TEMP_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return path

# ==================== الأزرار — نفس أرقام mian.py بالضبط ====================

def main_menu():
    markup = InlineKeyboardMarkup(row_width=1)

    # أخضر success — نفس رقم mian.py سطر 190
    markup.row(InlineKeyboardButton(
        "𝐗𝟏 CVV + تاريخ عشوائي",
        callback_data="mode_1",
        style="success",
        icon_custom_emoji_id="5059910390280881178"
    ))
    # أحمر danger — نفس رقم mian.py سطر 203
    markup.row(InlineKeyboardButton(
        "𝐗𝟐 تاريخ ثابت / CVV عشوائي",
        callback_data="mode_2",
        style="danger",
        icon_custom_emoji_id="5060247798616687432"
    ))
    # أزرق primary — نفس رقم mian.py سطر 185
    markup.row(InlineKeyboardButton(
        "𝐗𝟑 CVV ثابت / تاريخ عشوائي",
        callback_data="mode_3",
        style="primary",
        icon_custom_emoji_id="5059798514972754990"
    ))
    # أحمر danger — نفس رقم mian.py سطر 220
    markup.row(InlineKeyboardButton(
        "𝐂𝐚𝐧𝐜𝐞𝐥 إلغاء العملية",
        callback_data="cancel",
        style="danger",
        icon_custom_emoji_id="5060247798616687432"
    ))
    return markup

# ==================== /start ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(
        "𝐔𝐩𝐥𝐨𝐚𝐝 أرسل ملف",
        callback_data="upload_hint",
        style="success",
        icon_custom_emoji_id="5059910390280881178"
    ))
    bot.send_message(
        message.chat.id,
        f"✨ أهلاً بك في بوت توليد الأرقام ✨\n\n"
        f"📌 أرسل ملف .txt يحتوي على أرقام\n"
        f"• يؤخذ أول 12 رقم من كل سطر\n"
        f"• يتم توليد 10 مجموعات من كل رقم\n\n"
        f"🔹 المطور: {BOT_USERNAME}\n"
        f"🔹 الإصدار: {VERSION}",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "upload_hint")
def upload_hint(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "📤 أرسل ملف .txt الآن")

# ==================== استقبال الملف ====================

@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id

    if not message.document.file_name.endswith('.txt'):
        bot.reply_to(message, "❌ يرجى إرسال ملف .txt فقط")
        return

    file_info = bot.get_file(message.document.file_id)
    downloaded = bot.download_file(file_info.file_path)

    input_path = os.path.join(TEMP_DIR, f"{user_id}_input.txt")
    with open(input_path, 'wb') as f:
        f.write(downloaded)

    numbers = read_numbers_from_file(input_path)

    if not numbers:
        bot.reply_to(message, "❌ الملف لا يحتوي على أرقام صالحة (12 رقم على الأقل في كل سطر)")
        os.remove(input_path)
        return

    user_data[user_id] = {"numbers": numbers, "file_path": input_path}

    bot.send_message(
        message.chat.id,
        f"📊 تم رفع الملف بنجاح\n"
        f"• عدد الأسطر الصالحة: {len(numbers)}\n\n"
        f"🎯 اختر طريقة التوليد:",
        reply_markup=main_menu()
    )

# ==================== معالجة الأزرار ====================

@bot.callback_query_handler(func=lambda call: call.data in ["mode_1", "mode_2", "mode_3", "cancel"])
def process_mode(call):
    user_id = call.from_user.id
    data = user_data.get(user_id)

    if not data:
        bot.answer_callback_query(call.id, "❌ الجلسة منتهية! أرسل الملف مرة أخرى.", show_alert=True)
        return

    if call.data == "cancel":
        bot.answer_callback_query(call.id, "تم الإلغاء")
        try:
            bot.edit_message_text("❌ تم إلغاء العملية", call.message.chat.id, call.message.message_id)
        except:
            pass
        try:
            os.remove(data["file_path"])
        except:
            pass
        del user_data[user_id]
        return

    bot.answer_callback_query(call.id, "🔄 جاري المعالجة...")
    try:
        bot.edit_message_text("🔄 جاري توليد البيانات...", call.message.chat.id, call.message.message_id)
    except:
        pass

    numbers = data["numbers"]
    generated = []
    mode_label = ""

    if call.data == "mode_1":
        mode_label = "CVV + تاريخ عشوائي"
        for n in numbers:
            generated.extend(generate_entries(n, count=10))

    elif call.data == "mode_2":
        mode_label = "تاريخ ثابت (01/26) + CVV عشوائي"
        for n in numbers:
            generated.extend(generate_entries(n, count=10, fixed_date="01|26"))

    elif call.data == "mode_3":
        mode_label = "CVV ثابت (123) + تاريخ عشوائي"
        for n in numbers:
            generated.extend(generate_entries(n, count=10, fixed_cvv="123"))

    output_path = save_to_file(generated, f"{user_id}_output.txt")

    with open(output_path, 'rb') as f:
        bot.send_document(
            call.message.chat.id,
            f,
            caption=(
                f"✅ تم التوليد بنجاح\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📁 الأسطر الأصلية : {len(numbers)}\n"
                f"🆕 المولد           : {len(generated)}\n"
                f"⚙️ الوضع           : {mode_label}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔹 {BOT_USERNAME} | V{VERSION}"
            )
        )

    try:
        os.remove(output_path)
        os.remove(data["file_path"])
    except:
        pass
    del user_data[user_id]

# ==================== تشغيل البوت ====================

if __name__ == "__main__":
    print(f"Bot V{VERSION} running...")
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
