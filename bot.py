import os
import random
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ==================== إعدادات البوت ====================
TOKEN = os.getenv("BOT_TOKEN")  # متغير البيئة
BOT_NAME = "Mustafa Checker Bot"
BOT_USERNAME = "@o8380"
OWNER_ID = 1013384909  # معرف المطور

TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)

user_data = {}  # {user_id: {"cards": [], "file_path": ""}}

# ==================== دوال مساعدة ====================
def read_cards_from_file(file_path):
    """قراءة البطاقات من الملف - تدعم صيغ متعددة"""
    cards = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    # استخراج الرقم فقط من أي صيغة
                    numbers = re.findall(r'\d+', line)
                    if numbers:
                        card_num = numbers[0].replace(' ', '').replace('-', '')
                        if len(card_num) >= 12:
                            cards.append(card_num)
    except Exception as e:
        print(f"قراءة الملف: {e}")
    return cards

def generate_random_number(length):
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])

def generate_random_date():
    """توليد تاريخ عشوائي MM|YY (سنوات حديثة 2026-2032)"""
    year = random.randint(2026, 2032)
    month = random.randint(1, 12)
    return f"{month:02d}|{str(year)[-2:]}"

def generate_random_cvv():
    return generate_random_number(3)

def generate_cards_from_bin(first_12, count=1, fixed_date=None, fixed_cvv=None):
    """توليد بطاقات جديدة من أول 12 رقم"""
    cards = []
    for _ in range(count):
        remaining = generate_random_number(4)
        full_card = first_12 + remaining
        date = fixed_date if fixed_date else generate_random_date()
        cvv = fixed_cvv if fixed_cvv else generate_random_cvv()
        cards.append(f"{full_card}|{date}|{cvv}")
    return cards

def save_cards_to_file(cards, filename):
    file_path = os.path.join(TEMP_DIR, filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        for card in cards:
            f.write(card + '\n')
    return file_path

# ==================== أوامر البوت ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"✨ أهلاً بك في بوت {BOT_NAME} ✨\n"
        f"📤 أرسل لي ملف `.txt` يحتوي على البطاقات\n"
        f"📌 سيتم معالجة كل بطاقة وأخذ أول 12 رقم منها\n\n"
        f"🔹 البوت من تطوير: {BOT_USERNAME}"
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    document = update.message.document

    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ يرجى إرسال ملف `.txt` فقط")
        return

    # تحميل الملف
    file = await context.bot.get_file(document.file_id)
    file_path = os.path.join(TEMP_DIR, f"{user_id}_input.txt")
    await file.download_to_drive(file_path)

    cards = read_cards_from_file(file_path)
    if not cards:
        await update.message.reply_text("❌ الملف لا يحتوي على بطاقات صالحة (تحتاج 12 رقم على الأقل)")
        return

    user_data[user_id] = {
        "cards": cards,
        "file_path": file_path
    }

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(
            "🟢 CVV+تاريخ عشوائي",
            callback_data="mode_1",
            style="success",
            icon_custom_emoji_id="5992195984623408246"
        ),
        InlineKeyboardButton(
            "🔵 تاريخ ثابت / CVV عشوائي",
            callback_data="mode_2",
            style="primary",
            icon_custom_emoji_id="5992246772611681940"
        )
    )
    keyboard.add(
        InlineKeyboardButton(
            "🔴 CVV ثابت / تاريخ عشوائي",
            callback_data="mode_3",
            style="danger",
            icon_custom_emoji_id="5060247798616687432"
        ),
        InlineKeyboardButton(
            "🟢 إلغاء العملية",
            callback_data="cancel",
            style="success",
            icon_custom_emoji_id="5060115075537306714"
        )
    )

    await update.message.reply_text(
        f"📊 الملف يحتوي على {len(cards)} بطاقة أصلية\n\n"
        f"🎯 اختر طريقة المعالجة:",
        reply_markup=keyboard
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = user_data.get(user_id)

    if not data:
        await query.edit_message_text("❌ جلسة منتهية! أرسل الملف مرة أخرى.")
        return

    if query.data == "cancel":
        await query.edit_message_text("✅ تم إلغاء العملية.")
        return

    original_cards = data["cards"]
    generated_cards = []
    mode_name = ""

    for first_12 in original_cards:
        first_12 = first_12[:12]  # تأكد من أخذ أول 12 رقم فقط

        if query.data == "mode_1":
            # كل شيء عشوائي (CVV + تاريخ)
            cards = generate_cards_from_bin(first_12, 5)
            generated_cards.extend(cards)
            mode_name = "CVV+تاريخ عشوائي"

        elif query.data == "mode_2":
            # تاريخ ثابت (01|26) و CVV عشوائي
            cards = generate_cards_from_bin(first_12, 5, fixed_date="01|26")
            generated_cards.extend(cards)
            mode_name = "تاريخ ثابت / CVV عشوائي"

        elif query.data == "mode_3":
            # CVV ثابت (123) وتاريخ عشوائي
            cards = generate_cards_from_bin(first_12, 5, fixed_cvv="123")
            generated_cards.extend(cards)
            mode_name = "CVV ثابت / تاريخ عشوائي"

    output_file = save_cards_to_file(generated_cards, f"{user_id}_output_{query.data}.txt")

    with open(output_file, 'rb') as f:
        await query.message.reply_document(
            document=f,
            filename=f"generated_{mode_name}.txt",
            caption=(
                f"✅ تم التوليد بنجاح!\n"
                f"📁 البطاقات الأصلية: {len(original_cards)}\n"
                f"🆕 البطاقات المُولدة: {len(generated_cards)}\n"
                f"⚙️ الوضع: {mode_name}\n"
                f"🔹 البوت من تطوير: {BOT_USERNAME}"
            )
        )

    # تنظيف
    os.remove(output_file)
    os.remove(data["file_path"])
    del user_data[user_id]

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ أمر غير معروف. أرسل ملف نصي فقط.")

# ==================== تشغيل البوت ====================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    print("🤖 البوت شغال على Railway...")
    app.run_polling()

if __name__ == "__main__":
    main()
