import os
import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
    ContextTypes,
)

# ────────────────────────────────────────────────
TOKEN = os.getenv("TOKEN")
MAIN_GROUP_LINK = "https://t.me/+kCh_9St0vVdhNGJk"
ADMIN_GROUP_ID = -1003703559282                 # ایدی گروه ادمین‌ها
ADMIN_ID = 7940304990                           # ایدی عددی رئیس ربات

REJECT_BAN_HOURS = 24

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ────────────────────────────────────────────────
# دیتابیس
# ────────────────────────────────────────────────
conn = sqlite3.connect("students.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id          INTEGER PRIMARY KEY,
    full_name        TEXT,
    username         TEXT,
    status           TEXT DEFAULT 'joined',
    joined_at        TEXT,
    submitted_at     TEXT,
    reject_until     TEXT
)
""")
conn.commit()

# ────────────────────────────────────────────────
# منوی اصلی کاربران
# ────────────────────────────────────────────────
MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📸 ارسال عکس تاییدیه")],
        [KeyboardButton("🎫 ثبت تیکت")],
        [KeyboardButton("ℹ️ راهنما")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# ────────────────────────────────────────────────
# پنل ادمین اصلی
# ────────────────────────────────────────────────
def get_admin_panel():
    keyboard = [
        [
            InlineKeyboardButton("📊 آمار کاربران", callback_data="admin_stats"),
            InlineKeyboardButton("📢 پخش پیام همگانی", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="admin_search_user"),
            InlineKeyboardButton("🚫 لیست رد شده‌ها", callback_data="admin_rejected_list")
        ],
        [
            InlineKeyboardButton("🗑 پاک کردن کاربر", callback_data="admin_delete_user"),
            InlineKeyboardButton("🔄 ریست وضعیت کاربر", callback_data="admin_reset_user")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ────────────────────────────────────────────────
#	start
# ────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    now = datetime.now()

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user.id,))
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO users (user_id, full_name, username, joined_at)
        VALUES (?, ?, ?, ?)
        """, (user.id, user.full_name, user.username, now.isoformat()))
        conn.commit()

    text = (
        f"سلام {user.first_name} 👋\n\n"
        f"به ربات رسمی <b>ورودی بهمن</b> خوش اومدی 🎓✨\n\n"
        f"📸 لطفاً <b>عکس چاپ انتخاب واحد</b> ترم جاری رو برام بفرست\n"
        f"تا بعد از تایید، لینک گروه اصلی رو برات ارسال کنم 🚀\n\n"
        "عکس رو بفرست ↓"
    )

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_MENU)

# ────────────────────────────────────────────────
# /admin پنل رئیس
# ────────────────────────────────────────────────
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ دسترسی ندارید.")
        return

    await update.message.reply_text(
        "👤 پنل مدیریتی رئیس ربات\n\nگزینه را انتخاب کن:",
        reply_markup=get_admin_panel()
    )

# ────────────────────────────────────────────────
# Callback پنل ادمین
# ────────────────────────────────────────────────
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ دسترسی ندارید.")
        return

    # ... (بقیه کد پنل همان قبلی، برای اختصار حذف کردم، اما در کد کامل نگه دار)

# ────────────────────────────────────────────────
# هندلر متن پنل ادمین
# ────────────────────────────────────────────────
async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or "admin_mode" not in context.user_data:
        return

    # ... (بقیه کد همان قبلی)

# ────────────────────────────────────────────────
# راهنما
# ────────────────────────────────────────────────
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (همان قبلی)

# ────────────────────────────────────────────────
# منو هندلر
# ────────────────────────────────────────────────
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (همان قبلی)

# ────────────────────────────────────────────────
# دریافت عکس
# ────────────────────────────────────────────────
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (همان قبلی)

# ────────────────────────────────────────────────
# Callback دکمه‌ها (همه در یک تابع)
# ────────────────────────────────────────────────
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    action, user_id_str = data.split("_", 1)
    user_id = int(user_id_str)

    # چک که از گروه ادمین باشه (برای همه ادمین‌ها اجازه بده)
    if query.message.chat.id != ADMIN_GROUP_ID:
        await query.answer("فقط در گروه ادمین‌ها مجاز است.", show_alert=True)
        return

    if action == "approve":
        # ... (همان کد تایید قبلی)

    elif action == "deny":
        # ... (همان کد رد قبلی)

    elif action == "reply_ticket":
        context.user_data["reply_to"] = user_id
        context.user_data["admin_chat"] = query.message.chat_id
        context.user_data["admin_msg"] = query.message.message_id
        context.user_data["waiting_reply"] = True

        await query.edit_message_text(query.message.text + "\n\n📝 در حال پاسخ‌دهی...")

        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="📝 متن پاسخ به تیکت رو بنویس و ارسال کن (در پیوی خودت):"
        )

    elif action == "close_ticket":
        await query.edit_message_text(
            text=query.message.text + "\n\n❌ تیکت بسته شد."
        )
        await query.answer("تیکت بسته شد.")

    elif action == "spam_ticket":
        ban_until = (datetime.now() + timedelta(hours=REJECT_BAN_HOURS)).isoformat()
        cursor.execute("UPDATE users SET reject_until = ? WHERE user_id = ?", (ban_until, user_id))
        conn.commit()
        await context.bot.send_message(
            user_id,
            "⛔ تیکت شما به عنوان اسپم شناسایی شد. ۲۴ ساعت محدود شدید."
        )
        await query.edit_message_text(
            text=query.message.text + "\n\n🚫 اسپم - کاربر محدود شد."
        )
        await query.answer("کاربر محدود شد.")

# ────────────────────────────────────────────────
# دریافت تیکت (با دکمه‌های گسترش‌یافته)
# ────────────────────────────────────────────────
async def ticket_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_ticket"):
        return

    user = update.effective_user
    text = update.message.text.strip()

    if not text:
        await update.message.reply_text("لطفاً چیزی بنویس 😅", reply_markup=MAIN_MENU)
        return

    keyboard = [
        [
            InlineKeyboardButton("📩 پاسخ بده", callback_data=f"reply_ticket_{user.id}"),
            InlineKeyboardButton("❌ بستن تیکت", callback_data=f"close_ticket_{user.id}"),
            InlineKeyboardButton("🚫 اسپم", callback_data=f"spam_ticket_{user.id}")
        ]
    ]

    admin_msg = (
        f"🎫 تیکت جدید\n\n"
        f"نام: {user.full_name}\n"
        f"آیدی: <code>{user.id}</code>\n"
        f"یوزرنیم: @{user.username or 'ندارد'}\n\n"
        f"متن:\n{text}"
    )

    await context.bot.send_message(
        ADMIN_GROUP_ID,
        admin_msg,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text(
        "✅ تیکت ثبت شد!\nبه‌زودی جواب می‌دن. ممنون از صبرت 💙",
        reply_markup=MAIN_MENU
    )

    context.user_data.pop("awaiting_ticket", None)

# ────────────────────────────────────────────────
# هندلر پاسخ ادمین (ساده و بدون Conversation)
# ────────────────────────────────────────────────
async def admin_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_reply"):
        return

    reply_text = update.message.text.strip()
    user_id = context.user_data.get("reply_to")
    admin_chat = context.user_data.get("admin_chat")
    admin_msg = context.user_data.get("admin_msg")

    if not user_id or not reply_text:
        await update.message.reply_text("⚠️ مشکلی پیش اومد.")
        context.user_data.clear()
        return

    try:
        await context.bot.send_message(
            user_id,
            f"📩 پاسخ ادمین به تیکت شما:\n\n{reply_text}\n\n───────────────────\nاگر نیاز به ادامه داری، دوباره تیکت بزن 🎫"
        )
        await context.bot.edit_message_text(
            chat_id=admin_chat,
            message_id=admin_msg,
            text="🎫 این تیکت پاسخ داده شد ✅"
        )
        await update.message.reply_text("✅ پاسخ ارسال شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {str(e)}")

    context.user_data.clear()

# ────────────────────────────────────────────────
# اجرا main (اصلاح ترتیب Handlerها)
# ────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("admin", admin_panel))

    app.add_handler(MessageHandler(
        filters.Regex(r"^(📸 ارسال عکس تاییدیه|🎫 ثبت تیکت|ℹ️ راهنما|ℹ راهنما)$"),
        handle_menu
    ))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex(r"^(📸 ارسال عکس تاییدیه|🎫 ثبت تیکت|ℹ️ راهنما|ℹ راهنما)$"),
        ticket_handler
    ))

    # هندلر پاسخ ادمین (برای همه ادمین‌ها)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_reply_handler))

    # callback عمومی برای همه دکمه‌ها (بدون pattern خاص، اما در تابع چک می‌کنه)
    app.add_handler(CallbackQueryHandler(button))

    # callback پنل ادمین جدا
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))

    # هندلر متن پنل ادمین (برای رئیس)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_handler))  # این آخر باشه تا تداخل نکنه

    print("ربات شروع به کار کرد...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
