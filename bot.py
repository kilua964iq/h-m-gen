import random
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ========== إعدادات البوت ==========
TOKEN = "8726365736:AAGDQJKNiz0sqpolwGKKXU-Qbox3W6C-xJ4"  # ضع توكن البوت هنا

# مجلد مؤقت للملفات
TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)

# تخزين بيانات المستخدم مؤقتاً
user_data = {}

# ========== دوال مساعدة ==========
def read_cards_from_file(file_path):
    """قراءة البطاقات من الملف"""
    cards = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 1:
                        card_num = parts[0].replace(' ', '').replace('-', '')
                        if len(card_num) >= 12:
                            cards.append(line)
    except Exception as e:
        print(f"خطأ في القراءة: {e}")
    return cards

def generate_random_numbers(length):
    """توليد أرقام عشوائية بطول محدد"""
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])

def generate_random_date():
    """توليد تاريخ عشوائي (MM/YY)"""
    year = random.randint(24, 30)
    month = random.randint(1, 12)
    return f"{month:02d}/{year}"

def process_cards_mode1(original_cards):
    """الوضع 1: أول 12 رقم + باقي الأرقام عشوائي + CVV عشوائي"""
    new_cards = []
    for card_line in original_cards:
        parts = card_line.split('|')
        first_12 = parts[0][:12]
        
        for _ in range(10):  # توليد 10 بطاقات من كل أصلية
            remaining_digits = generate_random_numbers(4)  # 4 أرقام عشوائية
            full_card = first_12 + remaining_digits
            cvv = generate_random_numbers(3)
            new_cards.append(f"{full_card}|{cvv}")
    return new_cards

def process_cards_mode2(original_cards):
    """الوضع 2: أول 12 رقم + أرقام عشوائي + CVV ثابت"""
    new_cards = []
    for card_line in original_cards:
        parts = card_line.split('|')
        first_12 = parts[0][:12]
        fixed_cvv = parts[2] if len(parts) > 2 else generate_random_numbers(3)
        
        for _ in range(10):
            remaining_digits = generate_random_numbers(4)
            full_card = first_12 + remaining_digits
            new_cards.append(f"{full_card}|{fixed_cvv}")
    return new_cards

def process_cards_mode3(original_cards):
    """الوضع 3: أول 12 رقم + أرقام عشوائي + تاريخ عشوائي + CVV ثابت"""
    new_cards = []
    for card_line in original_cards:
        parts = card_line.split('|')
        first_12 = parts[0][:12]
        fixed_cvv = parts[2] if len(parts) > 2 else generate_random_numbers(3)
        
        for _ in range(10):
            remaining_digits = generate_random_numbers(4)
            full_card = first_12 + remaining_digits
            random_date = generate_random_date()
            new_cards.append(f"{full_card}|{random_date}|{fixed_cvv}")
    return new_cards

def save_cards_to_file(cards, filename):
    """حفظ البطاقات في ملف"""
    file_path = os.path.join(TEMP_DIR, filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        for card in cards:
            f.write(card + '\n')
    return file_path

# ========== أوامر البوت ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    await update.message.reply_text(
        "✨ أهلاً بك في بوت معالجة البطاقات ✨\n\n"
        "📤 أرسل لي ملف نصي يحتوي على البطاقات\n"
        "📌 صيغة الملف: كل بطاقة في سطر\n"
        "مثال: 1234567890123456|1226|123"
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الملف المرسل"""
    user_id = update.effective_user.id
    document = update.message.document
    
    # تحميل الملف
    file = await context.bot.get_file(document.file_id)
    file_path = os.path.join(TEMP_DIR, f"{user_id}_input.txt")
    await file.download_to_drive(file_path)
    
    # قراءة البطاقات
    cards = read_cards_from_file(file_path)
    
    if not cards:
        await update.message.reply_text("❌ الملف لا يحتوي على بطاقات صالحة!")
        return
    
    # حفظ البيانات مؤقتاً
    user_data[user_id] = {
        "cards": cards,
        "file_path": file_path
    }
    
    # إنشاء الأزرار
    keyboard = [
        [
            InlineKeyboardButton(
                "🔹 أول 12 رقم + أرقام عشوائية + CVV عشوائي",
                callback_data="mode_1",
                style="success",
                icon_custom_emoji_id="5992195984623408246"
            )
        ],
        [
            InlineKeyboardButton(
                "🔸 أول 12 رقم + أرقام عشوائية + CVV ثابت",
                callback_data="mode_2",
                style="primary",
                icon_custom_emoji_id="5992246772611681940"
            )
        ],
        [
            InlineKeyboardButton(
                "🔻 أول 12 رقم + تاريخ عشوائي + CVV ثابت",
                callback_data="mode_3",
                style="danger",
                icon_custom_emoji_id="5060247798616687432"
            )
        ],
        [
            InlineKeyboardButton("❌ إلغاء", callback_data="cancel")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📊 الملف يحتوي على {len(cards)} بطاقة\n\n"
        f"🎯 اختر طريقة المعالجة:",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ضغط الأزرار"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = user_data.get(user_id)
    
    if not data:
        await query.edit_message_text("❌ جلسة منتهية! أرسل الملف مرة أخرى.")
        return
    
    if query.data == "cancel":
        await query.edit_message_text("✅ تم الإلغاء.")
        return
    
    cards = data["cards"]
    
    # معالجة حسب الوضع
    if query.data == "mode_1":
        new_cards = process_cards_mode1(cards)
        mode_name = "الوضع 1"
    elif query.data == "mode_2":
        new_cards = process_cards_mode2(cards)
        mode_name = "الوضع 2"
    elif query.data == "mode_3":
        new_cards = process_cards_mode3(cards)
        mode_name = "الوضع 3"
    else:
        return
    
    # حفظ النتيجة في ملف
    output_filename = f"{user_id}_output_{query.data}.txt"
    output_path = save_cards_to_file(new_cards, output_filename)
    
    # إرسال الملف
    with open(output_path, 'rb') as f:
        await query.message.reply_document(
            document=f,
            filename=f"generated_cards_{mode_name}.txt",
            caption=f"✅ تم التوليد بنجاح!\n"
                   f"📁 البطاقات الأصلية: {len(cards)}\n"
                   f"🆕 البطاقات المُولدة: {len(new_cards)}\n"
                   f"⚙️ طريقة المعالجة: {mode_name}"
        )
    
    # تنظيف الملفات
    os.remove(output_path)
    os.remove(data["file_path"])
    del user_data[user_id]

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة للأوامر غير المعروفة"""
    await update.message.reply_text("❌ أمر غير معروف! أرسل ملف نصي فقط.")

# ========== تشغيل البوت ==========
def main():
    app = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))
    
    print("🤖 البوت يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
