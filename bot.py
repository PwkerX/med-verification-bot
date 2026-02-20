import os
import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, filters, ContextTypes, CommandHandler

# -----------------------
# توکن ربات
# -----------------------
TOKEN = os.getenv("TOKEN")

# -----------------------
# تنظیمات گروه و لینک
# -----------------------
ADMIN_GROUP_ID = -1003703559282  # 👈 بعداً با ID گروه ادمین‌ها جایگذاری کن
MAIN_GROUP_LINK = "https://t.me/+xmOYLM5N0z4wY2E0"  # 👈 لینک گروه اصلی

# محدودیت زمان ارسال عکس
TIME_LIMIT = 15  # دقیقه

# -----------------------
# Logging
# -----------------------
logging.basicConfig(level=logging.INFO)

# -----------------------
# Database setup
# -----------------------
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    full_name TEXT,
    status TEXT,
    joined_at TEXT,
    submitted INTEGER,
    reject_until TEXT
)
""")
conn.commit()

# -----------------------
# Start command
# -----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user.id,))
    data = cursor.fetchone()

    if not data:
        cursor.execute("""
        INSERT OR REPLACE INTO users 
        (user_id, full_name, status, joined_at, submitted, reject_until)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user.id,
            user.full_name or "نام نامشخص",
            "joined",
            datetime.now().isoformat(),
            0,
            None
        ))
        conn.commit()

    await update.message.reply_text(
        f"👋 سلام {user.full_name} عزیز!\n\n"
        "🎓 خوش آمدی!\n\n"
        f"📌 لطفاً **عکس چاپ تاییدیه انتخاب واحدت** رو در همین چت ارسال کن.\n"
        f"⏰ فرصت ارسال: {TIME_LIMIT} دقیقه\n"
        "⚠ فقط یک بار می‌تونی ارسال کنی.\n\n"
        "💡 پس از ارسال و تایید، لینک گروه اصلی برایت ارسال خواهد شد."
    )

# -----------------------
# Handle photo
# -----------------------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user.id,))
    data = cursor.fetchone()
    if not data:
        await update.message.reply_text("⚠ لطفاً ابتدا /start را بزنید.")
        return

    # بررسی رد قبلی
    reject_until = data[5]
    if reject_until and datetime.now() < datetime.fromisoformat(reject_until):
        await update.message.reply_text("⛔ فعلاً اجازه ارسال ندارید. ۲۴ ساعت دیگر دوباره تلاش کنید 😅")
        return

    # بررسی زمان محدود
    joined_at = datetime.fromisoformat(data[3])
    if datetime.now() - joined_at > timedelta(minutes=TIME_LIMIT):
        await update.message.reply_text("⌛ زمان ارسال عکس شما تموم شد. ۲۴ ساعت دیگر دوباره تلاش کنید 🕒")
        return

    # بررسی ارسال قبلی
    if data[4] == 1:
        await update.message.reply_text("⚠ قبلاً ارسال کرده‌اید. لطفاً ۲۴ ساعت دیگر صبر کنید ⏳")
        return

    # فورارد عکس به گروه ادمین‌ها
    forwarded = await context.bot.forward_message(
        chat_id=ADMIN_GROUP_ID,
        from_chat_id=update.message.chat.id,
        message_id=update.message.message_id
    )

    # شمارش کاربران منتظر بررسی
    cursor.execute("SELECT COUNT(*) FROM users WHERE submitted=1 AND status='joined'")
    waiting_count = cursor.fetchone()[0]

    # پیام اعلان به گروه ادمین‌ها
    keyboard = [[
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
        InlineKeyboardButton("❌ Deny", callback_data=f"deny_{user.id}")
    ]]
    await context.bot.send_message(
        chat_id=ADMIN_GROUP_ID,
        text=f"📩 درخواست جدید وارد شد!\n"
             f"👤 نام: {user.full_name}\n"
             f"🆔 ID: {user.id}\n"
             f"📸 عکس انتخاب واحد دریافت شد.\n"
             f"🔔 تعداد کاربران منتظر بررسی: {waiting_count}\n"
             f"✅ لطفاً Approve یا Deny بزنید.",
        reply_to_message_id=forwarded.message_id,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    cursor.execute("UPDATE users SET submitted=1 WHERE user_id=?", (user.id,))
    conn.commit()

    # پیام دلنشین به کاربر
    await update.message.reply_text(
        "📨 عکس شما دریافت شد! لطفاً کمی صبر کنید، ادمین‌ها درخواستت رو بررسی می‌کنند 👀"
    )

# -----------------------
# Approve / Deny
# -----------------------
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split("_")
    user_id = int(user_id)

    if action == "approve":
        # پیام خصوصی تشویقی + لینک گروه اصلی
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎉 تبریک {user_id}! تایید شدی 😎\n"
                 f"📌 لینک گروه اصلی:\n{MAIN_GROUP_LINK}\n\n"
                 f"💡 بعد از ورود به گروه اصلی، می‌تونی با دوستانت در ارتباط باشی."
        )

        cursor.execute("UPDATE users SET status='approved' WHERE user_id=?", (user_id,))
        conn.commit()

        # لاگ ورود در گروه ادمین‌ها
        await context.bot.send_message(
            ADMIN_GROUP_ID,
            f"✅ {user_id} تایید شد و لینک گروه اصلی برایش ارسال شد."
        )

    elif action == "deny":
        reject_time = datetime.now() + timedelta(hours=24)
        cursor.execute("UPDATE users SET status='rejected', reject_until=? WHERE user_id=?",
                       (reject_time.isoformat(), user_id))
        conn.commit()

        # پیام خصوصی انگیزشی
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ متاسفم، این بار رد شدی 😅\n"
                 "💪 ۲۴ ساعت دیگر دوباره تلاش کن، موفق می‌شی!"
        )

        await context.bot.send_message(
            ADMIN_GROUP_ID,
            f"❌ {user_id} رد شد. تا ۲۴ ساعت امکان ارسال دوباره ندارد."
        )

    # حذف پیام دکمه بعد از تصمیم
    await context.bot.delete_message(ADMIN_GROUP_ID, query.message.message_id)

# -----------------------
# Delete non-photo messages
# -----------------------
async def delete_non_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.delete()

# -----------------------
# اجرای ربات
# -----------------------
app = ApplicationBuilder().token(TOKEN).build()

# Handlerها
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(~filters.PHOTO, delete_non_photo))
app.add_handler(CallbackQueryHandler(button))

# اجرای Polling
app.run_polling()
