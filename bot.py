import os
import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, ChatMemberHandler, filters, ContextTypes

# -----------------------
# تنظیمات
# -----------------------
TOKEN = os.getenv("TOKEN")
PRE_GROUP_ID = -1003755161770
ADMIN_GROUP_ID = -1003703559282
MAIN_GROUP_ID = -1001234567890
MAIN_GROUP_LINK = "https://t.me/+kCh_9St0vVdhNGJk"
TIME_LIMIT = 15  # دقیقه

logging.basicConfig(level=logging.INFO)

# -----------------------
# دیتابیس
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
    reject_until TEXT,
    entered_main_group INTEGER
)
""")
conn.commit()

# -----------------------
# عضو جدید در گروه پیش‌ورود
# -----------------------
async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.chat_member.chat.id != PRE_GROUP_ID:
        return

    member = update.chat_member.new_member
    if not member or not member.user:
        return
    user = member.user

    cursor.execute("""
    INSERT OR REPLACE INTO users
    (user_id, full_name, status, joined_at, submitted, reject_until, entered_main_group)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user.id,
        user.full_name or "نام نامشخص",
        "joined",
        datetime.now().isoformat(),
        0,
        None,
        0
    ))
    conn.commit()

    try:
        await context.bot.send_message(
            chat_id=user.id,
            text=f"👋 سلام {user.full_name} عزیز!\n"
                 f"🎓 خوش اومدی به گروه پیش‌ورود ورودی بهمن!\n\n"
                 f"📌 لطفاً تا {TIME_LIMIT} دقیقه آینده عکس تاییدیه انتخاب واحدت رو بفرست 📝\n"
                 f"⚠ فقط یک بار می‌تونی ارسال کنی.\n"
                 f"⏰ وقت محدوده، پس سریع باش! /start رو اگر نزدی بزن."
        )
    except Exception as e:
        logging.error(f"خطا در ارسال پیام خوش‌آمد: {e}")

# -----------------------
# دریافت عکس
# -----------------------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.id != PRE_GROUP_ID:
        return

    user = update.message.from_user
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user.id,))
    data = cursor.fetchone()
    if not data:
        return

    reject_until = data[5]
    if reject_until and datetime.now() < datetime.fromisoformat(reject_until):
        await update.message.reply_text("⛔ فعلاً اجازه ارسال ندارید. ۲۴ ساعت بعد دوباره تلاش کنید 😅")
        return

    joined_at = datetime.fromisoformat(data[3])
    if datetime.now() - joined_at > timedelta(minutes=TIME_LIMIT):
        await update.message.reply_text("⌛ زمان ارسال عکس تموم شد. ۲۴ ساعت بعد دوباره تلاش کنید 🕒")
        return

    if data[4] == 1:
        await update.message.reply_text("⚠ قبلاً ارسال کرده‌اید. لطفاً ۲۴ ساعت دیگر صبر کنید ⏳")
        return

    forwarded = await context.bot.forward_message(
        chat_id=ADMIN_GROUP_ID,
        from_chat_id=update.message.chat.id,
        message_id=update.message.message_id
    )

    cursor.execute("SELECT COUNT(*) FROM users WHERE submitted=1 AND status='joined'")
    waiting_count = cursor.fetchone()[0]

    await context.bot.send_message(
        chat_id=ADMIN_GROUP_ID,
        text=f"📩 درخواست جدید وارد شد!\n👤 {user.full_name}\n🆔 ID: {user.id}\n"
             f"📸 عکس دریافت شد.\n🔔 تعداد کاربران منتظر بررسی: {waiting_count}",
        reply_to_message_id=forwarded.message_id,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton("❌ Deny", callback_data=f"deny_{user.id}")
        ]])
    )

    cursor.execute("UPDATE users SET submitted=1 WHERE user_id=?", (user.id,))
    conn.commit()

    await update.message.reply_text("📨 عکس شما دریافت شد! کمی صبر کنید، ادمین‌ها بررسی می‌کنند 👀")

# -----------------------
# Approve / Deny
# -----------------------
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split("_")
    user_id = int(user_id)

    if action == "approve":
        cursor.execute("UPDATE users SET status='approved' WHERE user_id=?", (user_id,))
        conn.commit()
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎉 تبریک! تایید شدی 😎\n📌 لینک گروه اصلی:\n{MAIN_GROUP_LINK}\n"
                 f"💡 وقتی وارد گروه اصلی شدی، ربات خودکار تو رو از گروه پیش‌ورود kick می‌کنه!"
        )
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=f"✅ {user_id} تایید شد و لینک گروه اصلی ارسال شد."
        )
    elif action == "deny":
        reject_time = datetime.now() + timedelta(hours=24)
        cursor.execute("UPDATE users SET status='rejected', reject_until=? WHERE user_id=?",
                       (reject_time.isoformat(), user_id))
        conn.commit()
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ متاسفم، رد شدی 😅\n۲۴ ساعت بعد دوباره تلاش کن 💪"
        )
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=f"❌ {user_id} رد شد. تا ۲۴ ساعت امکان ارسال دوباره ندارد."
        )
    await context.bot.delete_message(ADMIN_GROUP_ID, query.message.message_id)

# -----------------------
# حذف پیام‌های غیرعکس
# -----------------------
async def delete_non_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.id == PRE_GROUP_ID and not update.message.photo:
        await update.message.delete()

# -----------------------
# مانیتورینگ ورود گروه اصلی
# -----------------------
async def monitor_main_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.chat_member.chat.id != MAIN_GROUP_ID:
        return

    member = update.chat_member.new_member
    if not member or not member.user:
        return
    user = member.user

    cursor.execute("SELECT status, entered_main_group FROM users WHERE user_id=?", (user.id,))
    data = cursor.fetchone()
    if data and data[0] == 'approved' and data[1] == 0:
        try:
            await context.bot.ban_chat_member(PRE_GROUP_ID, user.id)
            await context.bot.unban_chat_member(PRE_GROUP_ID, user.id)
            cursor.execute("UPDATE users SET entered_main_group=1 WHERE user_id=?", (user.id,))
            conn.commit()

            await context.bot.send_message(
                chat_id=user.id,
                text="🎊 خوش اومدی به گروه اصلی 🥳\n📚 می‌تونی با دوستان و کلاس‌ها ارتباط برقرار کنی 👨‍🎓👩‍🎓"
            )

            await context.bot.send_message(
                ADMIN_GROUP_ID,
                f"🚀 {user.id} وارد گروه اصلی شد و از پیش‌ورود kick شد."
            )
        except Exception as e:
            logging.error(f"خطا در Kick از پیش‌ورود: {e}")

# -----------------------
# اجرای ربات
# -----------------------
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(ChatMemberHandler(new_member, ChatMemberHandler.CHAT_MEMBER))
app.add_handler(ChatMemberHandler(monitor_main_group, ChatMemberHandler.CHAT_MEMBER))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(~filters.PHOTO, delete_non_photo))
app.add_handler(CallbackQueryHandler(button))

app.run_polling()
