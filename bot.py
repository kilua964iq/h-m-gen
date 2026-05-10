"""
╔══════════════════════════════════════════════════════════════╗
║          🔥 Card Generator Pro  — by @o8380                 ║
║  متغيرات البيئة المطلوبة:                                   ║
║    BOT_TOKEN      – توكن البوت من @BotFather               ║
║    OWNER_ID       – معرف المالك (رقم)                       ║
║    OPENAI_API_KEY – مفتاح OpenAI                            ║
╚══════════════════════════════════════════════════════════════╝
"""

import os, json, random, time, re, asyncio, logging, datetime
from pathlib import Path
from typing import Optional

import requests
from openai import OpenAI

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters,
)

# ══════════════════════════════════════════════════════════════
# السجلات
# ══════════════════════════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# الثوابت
# ══════════════════════════════════════════════════════════════
BOT_TOKEN      = os.environ["BOT_TOKEN"]
OWNER_ID       = int(os.environ.get("OWNER_ID", "6285783725"))
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
BOT_TAG        = "@o8380"
VERSION        = "3.0 Pro"

# ══════════════════════════════════════════════════════════════
# المسارات
# ══════════════════════════════════════════════════════════════
DATA_DIR       = Path("data")
USER_DATA_DIR  = DATA_DIR / "user_data"
TEMP_DIR       = Path("temp_files")
PRIVATE_BINS_F = DATA_DIR / "private_bins.json"
STATS_F        = DATA_DIR / "stats.json"

for _d in [DATA_DIR, USER_DATA_DIR, TEMP_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════
# مراحل المحادثة
# ══════════════════════════════════════════════════════════════
ST_IDLE, ST_BIN_TYPE, ST_DIGITS, ST_DATE_MODE, ST_CVV_MODE, ST_COUNT = range(6)

# ══════════════════════════════════════════════════════════════
# OpenAI
# ══════════════════════════════════════════════════════════════
ai_client: Optional[OpenAI] = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ══════════════════════════════════════════════════════════════
# ██  أدوات JSON  ██
# ══════════════════════════════════════════════════════════════

def _jload(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default

def _jsave(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_user(uid: int) -> dict:
    return _jload(USER_DATA_DIR / f"{uid}.json", {})

def save_user(uid: int, data: dict):
    _jsave(USER_DATA_DIR / f"{uid}.json", data)

def load_pbins() -> dict:
    return _jload(PRIVATE_BINS_F, {})

def save_pbins(d: dict):
    _jsave(PRIVATE_BINS_F, d)

def load_stats() -> dict:
    d = _jload(STATS_F, {"total_files": 0, "total_generated": 0, "total_users": [], "sessions": []})
    d["total_users"] = set(d.get("total_users", []))
    return d

def save_stats(d: dict):
    out = dict(d)
    out["total_users"] = list(d["total_users"])
    _jsave(STATS_F, out)

# ══════════════════════════════════════════════════════════════
# ██  Luhn  ██
# ══════════════════════════════════════════════════════════════

def luhn_check(num: str) -> bool:
    digits = [int(c) for c in num if c.isdigit()]
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
    for n in range(10):
        if luhn_check(partial + str(n)):
            return str(n)
    return "0"

# ══════════════════════════════════════════════════════════════
# ██  تحليل البطاقات  ██
# ══════════════════════════════════════════════════════════════

def parse_card(line: str) -> Optional[dict]:
    line = line.strip()
    if not line or line.startswith("#") or "|" not in line:
        return None
    parts = line.split("|")
    if len(parts) < 4:
        return None
    num   = re.sub(r"\D", "", parts[0].strip())
    month = parts[1].strip().zfill(2)
    year  = parts[2].strip()
    cvv   = parts[3].strip()
    if len(num) < 13 or not month.isdigit() or not year.isdigit():
        return None
    if len(year) == 4:
        year = year[-2:]
    return {"num": num, "month": month, "year": year, "cvv": cvv, "bin6": num[:6]}

def is_expired(month: str, year: str) -> bool:
    try:
        now = datetime.datetime.now()
        ey  = int("20" + year) if len(year) == 2 else int(year)
        em  = int(month)
        return datetime.datetime(ey, em, 1) < datetime.datetime(now.year, now.month, 1)
    except Exception:
        return False

def filter_cards(raw: list[str]) -> dict:
    st = {
        "original": len(raw),
        "invalid": 0, "expired": 0,
        "luhn_fail": 0, "dup_card": 0, "dup_bin": 0,
        "valid": [],
    }
    seen_cards: set = set()
    seen_bins:  set = set()
    for line in raw:
        c = parse_card(line)
        if not c:
            st["invalid"] += 1
            continue
        if is_expired(c["month"], c["year"]):
            st["expired"] += 1
            continue
        if not luhn_check(c["num"]):
            st["luhn_fail"] += 1
            continue
        fp = f"{c['num']}|{c['month']}|{c['year']}"
        if fp in seen_cards:
            st["dup_card"] += 1
            continue
        seen_cards.add(fp)
        if c["bin6"] in seen_bins:
            st["dup_bin"] += 1
            continue
        seen_bins.add(c["bin6"])
        st["valid"].append(c)
    return st

# ══════════════════════════════════════════════════════════════
# ██  BIN Analysis  ██
# ══════════════════════════════════════════════════════════════

_BIN_CACHE: dict = {}

def fetch_bin(bin6: str) -> dict:
    if bin6 in _BIN_CACHE:
        return _BIN_CACHE[bin6]
    try:
        r = requests.get(
            f"https://lookup.binlist.net/{bin6}",
            headers={"Accept-Version": "3"},
            timeout=6,
        )
        if r.status_code == 200:
            d = r.json()
            info = {
                "scheme":  d.get("scheme", "?").upper(),
                "type":    d.get("type",   "?").upper(),
                "bank":    d.get("bank",   {}).get("name", "Unknown"),
                "country": d.get("country",{}).get("name", "Unknown"),
                "flag":    d.get("country",{}).get("emoji", "🏳️"),
                "prepaid": d.get("prepaid", False),
            }
            _BIN_CACHE[bin6] = info
            return info
    except Exception:
        pass
    return {}

def classify_bin(info: dict) -> str:
    scheme  = info.get("scheme", "")
    country = info.get("country", "")
    prepaid = info.get("prepaid", False)
    if prepaid or scheme in ("UNIONPAY", "MIR") or country not in ("United States", "United Kingdom", ""):
        return "private"
    if scheme in ("AMEX", "DISCOVER", "DINERS"):
        return "semi"
    return "public"

def store_bin(bin6: str, info: dict, cls: str):
    db = load_pbins()
    if bin6 not in db:
        db[bin6] = {"info": info, "classification": cls,
                    "first_seen": datetime.datetime.now().isoformat(), "usage": 0}
    else:
        db[bin6]["usage"] = db[bin6].get("usage", 0) + 1
    save_pbins(db)

def analyze_bins(cards: list[dict]) -> list[dict]:
    out = []
    for c in cards:
        info = fetch_bin(c["bin6"])
        cls  = classify_bin(info)
        store_bin(c["bin6"], info, cls)
        out.append({**c, "bin_info": info, "cls": cls})
        time.sleep(0.12)
    return out

# ══════════════════════════════════════════════════════════════
# ██  AI  (مخفي عن المستخدم)  ██
# ══════════════════════════════════════════════════════════════

def ai_hidden_note(analyzed: list[dict]) -> str:
    if not ai_client or not analyzed:
        return ""
    try:
        summary = "\n".join(
            f"BIN {c['bin6']}: {c['cls']} | {c['bin_info'].get('scheme','')} | {c['bin_info'].get('country','')}"
            for c in analyzed[:12]
        )
        r = ai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content":
                f"حلل هذه البيانات وأعط توصية مختصرة (جملتان) عن جودتها:\n{summary}"}],
            max_tokens=100,
            temperature=0.3,
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"AI: {e}")
        return ""

# ══════════════════════════════════════════════════════════════
# ██  توليد البطاقات  ██
# ══════════════════════════════════════════════════════════════

def gen_cards(card: dict, digits: int, date_mode: str, cvv_mode: str, count: int) -> list[str]:
    base     = card["num"][:digits]
    full_len = 16
    results  = []
    seen:    set = set()
    max_try  = count * 60

    for _ in range(max_try):
        if len(results) >= count:
            break
        remaining = full_len - len(base) - 1
        middle    = "".join(str(random.randint(0, 9)) for _ in range(remaining))
        partial   = base + middle
        check     = luhn_digit(partial)
        num       = partial + check
        if not luhn_check(num):
            continue

        month = card["month"] if date_mode == "fixed" else str(random.randint(1, 12)).zfill(2)
        year  = card["year"]  if date_mode == "fixed" else str(random.randint(26, 30))
        cvv   = card["cvv"]   if cvv_mode  == "fixed" else str(random.randint(100, 999))

        fp = f"{num}|{month}|{year}|{cvv}"
        if fp not in seen:
            seen.add(fp)
            results.append(fp)

    return results

# ══════════════════════════════════════════════════════════════
# ██  لوحات المفاتيح  ██
# ══════════════════════════════════════════════════════════════

def kb_main(owner=False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("📤  رفع ملف بطاقات", callback_data="upload_hint")],
        [
            InlineKeyboardButton("ℹ️  معلومات",  callback_data="cb_info"),
            InlineKeyboardButton("💡  مساعدة",   callback_data="cb_help"),
        ],
    ]
    if owner:
        rows += [
            [
                InlineKeyboardButton("📊  لوحة التحكم",   callback_data="owner_dash"),
                InlineKeyboardButton("🗑  تنظيف BINs",    callback_data="owner_clear"),
            ],
            [InlineKeyboardButton("📤  تصدير BINs", callback_data="owner_export")],
        ]
    return InlineKeyboardMarkup(rows)

def kb_bin_type(pc, sc, pu) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔒  Private فقط  [{pc}]",          callback_data="bt_private")],
        [InlineKeyboardButton(f"🔒+📈  Private + Semi  [{pc+sc}]", callback_data="bt_semi")],
        [InlineKeyboardButton(f"🌐  جميع BINs  [{pc+sc+pu}]",      callback_data="bt_all")],
        [InlineKeyboardButton("❌  إلغاء",                          callback_data="cancel")],
    ])

def kb_digits() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("6",     callback_data="dg_6"),
            InlineKeyboardButton("8",     callback_data="dg_8"),
            InlineKeyboardButton("10",    callback_data="dg_10"),
        ],
        [
            InlineKeyboardButton("12 ✅", callback_data="dg_12"),
            InlineKeyboardButton("14",    callback_data="dg_14"),
            InlineKeyboardButton("16",    callback_data="dg_16"),
        ],
        [InlineKeyboardButton("❌  إلغاء", callback_data="cancel")],
    ])

def kb_date() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅  ثابت",    callback_data="dt_fixed"),
            InlineKeyboardButton("🎲  عشوائي",  callback_data="dt_random"),
        ],
        [InlineKeyboardButton("❌  إلغاء", callback_data="cancel")],
    ])

def kb_cvv() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔐  ثابت",    callback_data="cv_fixed"),
            InlineKeyboardButton("🎲  عشوائي",  callback_data="cv_random"),
        ],
        [InlineKeyboardButton("❌  إلغاء", callback_data="cancel")],
    ])

def kb_count() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("5",   callback_data="cn_5"),
            InlineKeyboardButton("10",  callback_data="cn_10"),
            InlineKeyboardButton("20",  callback_data="cn_20"),
        ],
        [
            InlineKeyboardButton("50",  callback_data="cn_50"),
            InlineKeyboardButton("100", callback_data="cn_100"),
            InlineKeyboardButton("200", callback_data="cn_200"),
        ],
        [InlineKeyboardButton("❌  إلغاء", callback_data="cancel")],
    ])

def kb_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠  الرئيسية", callback_data="home")]
    ])

# ══════════════════════════════════════════════════════════════
# ██  نصوص ثابتة  ██
# ══════════════════════════════════════════════════════════════

def txt_welcome(name: str) -> str:
    return (
        "╔══════════════════════════╗\n"
        "║  🔥  *Card Generator Pro*  ║\n"
        "╚══════════════════════════╝\n\n"
        f"👋 أهلاً *{name}*\n\n"
        "┌─────────────────────────┐\n"
        "│  ⚡ مدعوم بالذكاء الاصطناعي\n"
        "│  ✅ Luhn Algorithm مدمج\n"
        "│  🔍 تحليل BINs تلقائي\n"
        "│  🔒 تصنيف Private / Semi / Public\n"
        "└─────────────────────────┘\n\n"
        "👇 _اختر من القائمة:_\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n🏷 `{BOT_TAG}` · v{VERSION}"
    )

INFO_TXT = (
    "╔═══════════════════════╗\n"
    "║  📋  *معلومات البوت*  ║\n"
    "╚═══════════════════════╝\n\n"
    "🔍 *ما يفعله البوت:*\n"
    "┌──────────────────────┐\n"
    "│ ✅ فحص Luhn لكل بطاقة\n"
    "│ ✅ حذف البطاقات المنتهية\n"
    "│ ✅ حذف التكرارات\n"
    "│ ✅ تحليل BINs تلقائي\n"
    "│ ✅ تصنيف ذكي للبيانات\n"
    "│ ✅ ضمان Luhn في التوليد\n"
    "└──────────────────────┘\n\n"
    "📌 *الصيغة المدعومة:*\n"
    "`NUM|MM|YY|CVV`\n\n"
    f"━━━━━━━━━━━━━━━━━━━━━━━━\n🏷 `{BOT_TAG}` · v{VERSION}"
)

HELP_TXT = (
    "╔═══════════════════════╗\n"
    "║  💡  *دليل الاستخدام*  ║\n"
    "╚═══════════════════════╝\n\n"
    "1️⃣ أرسل ملف `.txt` بالبطاقات\n"
    "2️⃣ انتظر التحليل الذكي\n"
    "3️⃣ اختر نوع BINs\n"
    "4️⃣ اختر عدد الأرقام (6-16)\n"
    "5️⃣ اختر وضع التاريخ والـ CVV\n"
    "6️⃣ اختر عدد البطاقات لكل BIN\n"
    "7️⃣ احصل على ملفك 🎉\n\n"
    f"━━━━━━━━━━━━━━━━━━━━━━━━\n🏷 `{BOT_TAG}` · v{VERSION}"
)

# ══════════════════════════════════════════════════════════════
# ██  معالجات /start و /reset  ██
# ══════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "صديقي"
    st   = load_stats()
    st["total_users"].add(uid)
    save_stats(st)
    ud = load_user(uid)
    ud.setdefault("name", name)
    ud.setdefault("joined", datetime.datetime.now().isoformat())
    save_user(uid, ud)
    await update.message.reply_text(
        txt_welcome(name),
        parse_mode="Markdown",
        reply_markup=kb_main(owner=(uid == OWNER_ID)),
    )
    return ST_IDLE

async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    uid = update.effective_user.id
    for f in TEMP_DIR.glob(f"{uid}_*"):
        f.unlink(missing_ok=True)
    await update.message.reply_text(
        "🔄 *تم إعادة التعيين.*\n\nأرسل /start للبدء.",
        parse_mode="Markdown",
    )
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════════
# ██  معالجات الأزرار العامة  ██
# ══════════════════════════════════════════════════════════════

async def cb_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ctx.user_data.clear()
    uid  = q.from_user.id
    name = q.from_user.first_name or "صديقي"
    await q.message.edit_text(
        txt_welcome(name),
        parse_mode="Markdown",
        reply_markup=kb_main(owner=(uid == OWNER_ID)),
    )
    return ST_IDLE

async def cb_upload_hint(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        "📤 *أرسل ملف `.txt` الآن*\n\n"
        "┌─────────────────────┐\n"
        "│ الصيغة: `NUM|MM|YY|CVV`\n"
        "│ مثال: `4111111111111111|08|26|123`\n"
        "└─────────────────────┘",
        parse_mode="Markdown",
    )
    return ST_IDLE

async def cb_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.edit_text(INFO_TXT, parse_mode="Markdown", reply_markup=kb_home())
    return ST_IDLE

async def cb_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.edit_text(HELP_TXT, parse_mode="Markdown", reply_markup=kb_home())
    return ST_IDLE

async def cb_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("✅ تم الإلغاء")
    ctx.user_data.clear()
    uid = q.from_user.id
    await q.message.edit_text(
        "❌ *تم الإلغاء.*\n\nاضغط الرئيسية للبدء من جديد.",
        parse_mode="Markdown",
        reply_markup=kb_main(owner=(uid == OWNER_ID)),
    )
    return ST_IDLE

# ── Owner ──────────────────────────────────────────────────

async def cb_owner_dash(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != OWNER_ID:
        await q.answer("🚫 غير مصرح", show_alert=True)
        return ST_IDLE
    st   = load_stats()
    db   = load_pbins()
    pc   = sum(1 for v in db.values() if v.get("classification") == "private")
    sc   = sum(1 for v in db.values() if v.get("classification") == "semi")
    pub  = sum(1 for v in db.values() if v.get("classification") == "public")
    text = (
        "╔══════════════════════════╗\n"
        "║  📊  *لوحة التحكم*  ║\n"
        "╚══════════════════════════╝\n\n"
        f"👥 المستخدمون: `{len(st['total_users'])}`\n"
        f"📁 ملفات محللة: `{st['total_files']}`\n"
        f"🆕 بطاقات مولدة: `{st['total_generated']}`\n\n"
        "🗄 *قاعدة BINs:*\n"
        f"├ 🔒 Private: `{pc}`\n"
        f"├ 📈 Semi: `{sc}`\n"
        f"└ 🌐 Public: `{pub}`\n"
        f"   المجموع: `{len(db)}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n🏷 `{BOT_TAG}` · v{VERSION}"
    )
    await q.message.edit_text(text, parse_mode="Markdown", reply_markup=kb_home())
    return ST_IDLE

async def cb_owner_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != OWNER_ID:
        await q.answer("🚫 غير مصرح", show_alert=True)
        return ST_IDLE
    save_pbins({})
    await q.answer("✅ تم تنظيف قاعدة BINs", show_alert=True)
    return ST_IDLE

async def cb_owner_export(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != OWNER_ID:
        await q.answer("🚫 غير مصرح", show_alert=True)
        return ST_IDLE
    db = load_pbins()
    lines = [
        f"{b} | {v.get('classification','?'):8} | "
        f"{v.get('info',{}).get('scheme',''):8} | "
        f"{v.get('info',{}).get('country',''):20} | "
        f"{v.get('info',{}).get('bank','')}"
        for b, v in db.items()
    ]
    content = "\n".join(lines) if lines else "فارغة"
    path = TEMP_DIR / f"bins_export.txt"
    path.write_text(content, encoding="utf-8")
    with open(path, "rb") as f:
        await q.message.reply_document(
            InputFile(f, filename="private_bins.txt"),
            caption=f"📤 *قاعدة BINs* — {len(db)} BIN",
            parse_mode="Markdown",
        )
    path.unlink(missing_ok=True)
    return ST_IDLE

# ══════════════════════════════════════════════════════════════
# ██  معالج الملف الرئيسي  ██
# ══════════════════════════════════════════════════════════════

async def handle_doc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    doc = update.message.document

    if not doc or not doc.file_name.lower().endswith(".txt"):
        await update.message.reply_text(
            "❌ *يرجى إرسال ملف `.txt` فقط.*",
            parse_mode="Markdown",
        )
        return ST_IDLE

    prog = await update.message.reply_text(
        "╔══════════════════════╗\n"
        "║  🔄  *جاري التحليل...*  ║\n"
        "╚══════════════════════╝\n\n"
        "⏳ قراءة الملف...",
        parse_mode="Markdown",
    )

    # تحميل
    try:
        tg_file = await doc.get_file()
        raw     = await tg_file.download_as_bytearray()
        lines   = raw.decode("utf-8", errors="ignore").splitlines()
    except Exception as e:
        await prog.edit_text(f"❌ فشل التحميل: `{e}`", parse_mode="Markdown")
        return ST_IDLE

    # تنظيف
    await prog.edit_text(
        "╔══════════════════════╗\n"
        "║  🔄  *جاري التحليل...*  ║\n"
        "╚══════════════════════╝\n\n"
        "🧹 فحص Luhn وتنظيف البطاقات...",
        parse_mode="Markdown",
    )
    fr = filter_cards(lines)
    valid = fr["valid"]

    if not valid:
        await prog.edit_text(
            "❌ *لا توجد بطاقات صالحة!*\n\n"
            f"├ الأصلي: `{fr['original']}`\n"
            f"├ غير صالحة: `{fr['invalid']}`\n"
            f"├ منتهية: `{fr['expired']}`\n"
            f"├ فشل Luhn: `{fr['luhn_fail']}`\n"
            f"└ مكررة: `{fr['dup_card'] + fr['dup_bin']}`",
            parse_mode="Markdown",
        )
        return ST_IDLE

    # تحليل BINs
    await prog.edit_text(
        "╔══════════════════════╗\n"
        "║  🔄  *جاري التحليل...*  ║\n"
        "╚══════════════════════╝\n\n"
        f"🔍 تحليل {len(valid)} BIN فريد...\n_(ثوانٍ قليلة)_",
        parse_mode="Markdown",
    )

    loop     = asyncio.get_event_loop()
    analyzed = await loop.run_in_executor(None, analyze_bins, valid)

    # AI مخفي في الـ logs
    ai_note = await loop.run_in_executor(None, ai_hidden_note, analyzed)
    if ai_note:
        logger.info(f"[AI/{uid}] {ai_note}")

    pc  = sum(1 for c in analyzed if c["cls"] == "private")
    sc  = sum(1 for c in analyzed if c["cls"] == "semi")
    pub = sum(1 for c in analyzed if c["cls"] == "public")

    ctx.user_data["analyzed"] = analyzed
    ctx.user_data["fr"]       = fr

    st = load_stats()
    st["total_files"] += 1
    st["total_users"].add(uid)
    save_stats(st)

    summary = (
        "╔══════════════════════════╗\n"
        "║  ✅  *نتائج التحليل*  ║\n"
        "╚══════════════════════════╝\n\n"
        "📁 *إحصائيات الملف:*\n"
        f"┌ الأصلي: `{fr['original']}`\n"
        f"├ ❌ غير صالحة: `{fr['invalid']}`\n"
        f"├ ⏰ منتهية: `{fr['expired']}`\n"
        f"├ 🔢 فشل Luhn: `{fr['luhn_fail']}`\n"
        f"├ 🔁 مكررة: `{fr['dup_card'] + fr['dup_bin']}`\n"
        f"└ ✅ صالحة للتوليد: `{len(valid)}`\n\n"
        "🗂 *تصنيف BINs:*\n"
        f"├ 🔒 Private (نادر): `{pc}`\n"
        f"├ 📈 Semi-Public: `{sc}`\n"
        f"└ 🌐 Public (شائع): `{pub}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👇 *اختر نوع BINs للتوليد:*"
    )
    await prog.edit_text(
        summary,
        parse_mode="Markdown",
        reply_markup=kb_bin_type(pc, sc, pub),
    )
    return ST_BIN_TYPE

# ══════════════════════════════════════════════════════════════
# ██  خطوات الإعداد  ██
# ══════════════════════════════════════════════════════════════

async def cb_bin_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q     = update.callback_query
    await q.answer()
    btype = q.data.replace("bt_", "")
    analyzed = ctx.user_data.get("analyzed", [])

    if btype == "private":
        chosen = [c for c in analyzed if c["cls"] == "private"]
    elif btype == "semi":
        chosen = [c for c in analyzed if c["cls"] in ("private", "semi")]
    else:
        chosen = analyzed

    if not chosen:
        await q.message.edit_text(
            "⚠️ *لا توجد BINs في هذا التصنيف.*\nجرب خياراً آخر.",
            parse_mode="Markdown",
            reply_markup=kb_home(),
        )
        return ST_BIN_TYPE

    ctx.user_data["chosen"] = chosen

    await q.message.edit_text(
        "╔══════════════════════════╗\n"
        "║  📏  *عدد الأرقام*  ║\n"
        "╚══════════════════════════╝\n\n"
        "كم رقماً تأخذ من البطاقة الأصلية؟\n"
        "_(الباقي يُولَّد عشوائياً + Luhn مضمون)_\n\n"
        "✅ الافتراضي الموصى به: `12`",
        parse_mode="Markdown",
        reply_markup=kb_digits(),
    )
    return ST_DIGITS

async def cb_digits(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ctx.user_data["digits"] = int(q.data.replace("dg_", ""))
    await q.message.edit_text(
        "╔══════════════════════════╗\n"
        "║  📅  *وضع التاريخ*  ║\n"
        "╚══════════════════════════╝\n\n"
        "اختر وضع تاريخ انتهاء البطاقة:",
        parse_mode="Markdown",
        reply_markup=kb_date(),
    )
    return ST_DATE_MODE

async def cb_date_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ctx.user_data["date_mode"] = q.data.replace("dt_", "")
    await q.message.edit_text(
        "╔══════════════════════════╗\n"
        "║  🔐  *وضع CVV*  ║\n"
        "╚══════════════════════════╝\n\n"
        "اختر وضع رمز CVV:",
        parse_mode="Markdown",
        reply_markup=kb_cvv(),
    )
    return ST_CVV_MODE

async def cb_cvv_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ctx.user_data["cvv_mode"] = q.data.replace("cv_", "")
    await q.message.edit_text(
        "╔══════════════════════════╗\n"
        "║  🔢  *عدد البطاقات*  ║\n"
        "╚══════════════════════════╝\n\n"
        "كم بطاقة تريد توليدها من *كل BIN*؟",
        parse_mode="Markdown",
        reply_markup=kb_count(),
    )
    return ST_COUNT

# ══════════════════════════════════════════════════════════════
# ██  التوليد النهائي  ██
# ══════════════════════════════════════════════════════════════

async def cb_count(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    await q.answer()
    uid = q.from_user.id

    cpb       = int(q.data.replace("cn_", ""))
    chosen    = ctx.user_data.get("chosen", [])
    digits    = ctx.user_data.get("digits", 12)
    date_mode = ctx.user_data.get("date_mode", "fixed")
    cvv_mode  = ctx.user_data.get("cvv_mode", "random")

    gen_msg = await q.message.reply_text(
        "╔══════════════════════════╗\n"
        "║  ⚙️  *جاري التوليد...*  ║\n"
        "╚══════════════════════════╝\n\n"
        f"🗂 BINs: `{len(chosen)}`\n"
        f"📦 لكل BIN: `{cpb}`\n"
        f"📊 متوقع: `{len(chosen) * cpb}` بطاقة\n\n"
        "⏳ يرجى الانتظار...",
        parse_mode="Markdown",
    )

    all_out: list[str] = []
    seen_fp: set       = set()

    for card in chosen:
        for fp in gen_cards(card, digits, date_mode, cvv_mode, cpb):
            if fp not in seen_fp:
                seen_fp.add(fp)
                all_out.append(fp)

    if not all_out:
        await gen_msg.edit_text(
            "❌ *فشل التوليد.* حاول مجدداً.",
            parse_mode="Markdown",
            reply_markup=kb_home(),
        )
        return ST_IDLE

    # حفظ الملف
    out = TEMP_DIR / f"{uid}_output.txt"
    out.write_text("\n".join(all_out), encoding="utf-8")

    # إحصائيات
    st = load_stats()
    st["total_generated"] += len(all_out)
    st["sessions"].append({
        "uid": uid,
        "time": datetime.datetime.now().isoformat(),
        "generated": len(all_out),
        "bins": len(chosen),
    })
    if len(st["sessions"]) > 500:
        st["sessions"] = st["sessions"][-500:]
    save_stats(st)

    ud = load_user(uid)
    ud["last_gen"] = {
        "time": datetime.datetime.now().isoformat(),
        "cards": len(all_out), "bins": len(chosen),
        "digits": digits, "date_mode": date_mode, "cvv_mode": cvv_mode,
    }
    save_user(uid, ud)

    # إرسال
    caption = (
        "╔══════════════════════════╗\n"
        "║  🎉  *تم التوليد بنجاح!*  ║\n"
        "╚══════════════════════════╝\n\n"
        f"├ 🆕 البطاقات المولدة: `{len(all_out)}`\n"
        f"├ 🗂 عدد BINs: `{len(chosen)}`\n"
        f"├ 📏 أرقام محفوظة: `{digits}`\n"
        f"├ 📅 التاريخ: `{'ثابت' if date_mode=='fixed' else 'عشوائي'}`\n"
        f"├ 🔐 CVV: `{'ثابت' if cvv_mode=='fixed' else 'عشوائي'}`\n"
        f"└ ✅ Luhn: `مضمون 100%`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n🏷 `{BOT_TAG}` · v{VERSION}"
    )

    with open(out, "rb") as f:
        await q.message.reply_document(
            InputFile(f, filename=f"cards_{len(all_out)}.txt"),
            caption=caption,
            parse_mode="Markdown",
        )
    out.unlink(missing_ok=True)

    await gen_msg.edit_text(
        f"✅ *تم توليد `{len(all_out)}` بطاقة بنجاح!*",
        parse_mode="Markdown",
        reply_markup=kb_main(owner=(uid == OWNER_ID)),
    )
    ctx.user_data.clear()
    return ST_IDLE

# ══════════════════════════════════════════════════════════════
# ██  ConversationHandler + main  ██
# ══════════════════════════════════════════════════════════════

def build_app() -> Application:
    try:
        import httpx as _hx, time as _t
        _hx.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook",
            json={"drop_pending_updates": True}, timeout=10,
        )
        _t.sleep(1)
        logger.info("Webhook cleared.")
    except Exception as e:
        logger.warning(f"deleteWebhook: {e}")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(40).write_timeout(40).connect_timeout(40)
        .build()
    )

    # ─── ConversationHandler موحّد ────────────────────────────
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start",  cmd_start),
            MessageHandler(filters.Document.ALL, handle_doc),
        ],
        states={
            ST_IDLE: [
                MessageHandler(filters.Document.ALL,             handle_doc),
                CallbackQueryHandler(cb_upload_hint,  pattern="^upload_hint$"),
                CallbackQueryHandler(cb_info,         pattern="^cb_info$"),
                CallbackQueryHandler(cb_help,         pattern="^cb_help$"),
                CallbackQueryHandler(cb_home,         pattern="^home$"),
                CallbackQueryHandler(cb_cancel,       pattern="^cancel$"),
                CallbackQueryHandler(cb_owner_dash,   pattern="^owner_dash$"),
                CallbackQueryHandler(cb_owner_clear,  pattern="^owner_clear$"),
                CallbackQueryHandler(cb_owner_export, pattern="^owner_export$"),
            ],
            ST_BIN_TYPE: [
                CallbackQueryHandler(cb_bin_type, pattern="^bt_"),
                CallbackQueryHandler(cb_cancel,   pattern="^cancel$"),
                CallbackQueryHandler(cb_home,     pattern="^home$"),
            ],
            ST_DIGITS: [
                CallbackQueryHandler(cb_digits,  pattern="^dg_"),
                CallbackQueryHandler(cb_cancel,  pattern="^cancel$"),
                CallbackQueryHandler(cb_home,    pattern="^home$"),
            ],
            ST_DATE_MODE: [
                CallbackQueryHandler(cb_date_mode, pattern="^dt_"),
                CallbackQueryHandler(cb_cancel,    pattern="^cancel$"),
                CallbackQueryHandler(cb_home,      pattern="^home$"),
            ],
            ST_CVV_MODE: [
                CallbackQueryHandler(cb_cvv_mode, pattern="^cv_"),
                CallbackQueryHandler(cb_cancel,   pattern="^cancel$"),
                CallbackQueryHandler(cb_home,     pattern="^home$"),
            ],
            ST_COUNT: [
                CallbackQueryHandler(cb_count,  pattern="^cn_"),
                CallbackQueryHandler(cb_cancel, pattern="^cancel$"),
                CallbackQueryHandler(cb_home,   pattern="^home$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", cmd_start),
            CommandHandler("reset", cmd_reset),
            CallbackQueryHandler(cb_home, pattern="^home$"),
        ],
        per_message=False,
        allow_reentry=True,
    )

    app.add_handler(conv,                               group=0)
    app.add_handler(CommandHandler("reset", cmd_reset), group=1)
    return app

def main():
    logger.info("═" * 55)
    logger.info(f"  🔥  Card Generator Pro v{VERSION} — {BOT_TAG}")
    logger.info("═" * 55)
    app = build_app()
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
