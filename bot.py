import os
import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, ChatMemberHandler, filters, ContextTypes

TOKEN = os.getenv("TOKEN")

PRE_GROUP_ID = -1003755161770
ADMIN_GROUP_ID = -1003703559282
MAIN_GROUP_LINK = "https://t.me/+kCh_9St0vVdhNGJk"
TIME_LIMIT = 15  # دقیقه

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
    reject_until TEXT,
    entered_main_group INTEGER
)
""")
conn.commit()

# -----------------------
# New member handler
# -----------------------
async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.chat_member.new_chat_members:
        if update.chat_member.chat.id == PRE_GROUP_ID:
            cursor.execute("""
            INSERT OR REPLACE INTO users 
            (user_id, full_name, status, joined_at, submitted, reject_until, entered_main_group)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                member.id,
                member.full_name,
                "joined",
                datetime.now().isoformat(),
                0,
                None,
                0
            ))
            conn.commit()

            # پیام خوش‌آمد حرفه‌ای و دلنشین
            try:
                await context.bot.send_message(
                    chat_id=member.id,
                    text=f"👋 سلام {member.full_name} عزیز!\n"
                         f"🎓 خوش اومدی به **گروه پیش‌ورود ورودی بهمن**!\n\n"
                         f"📌 راهنمای گروه پیش‌ورود:\n"
                         f"1️⃣ عکس تاییدیه انتخاب واحدت رو بفرست 📝\n"
                         f"2️⃣ فقط یک بار می‌تونی ارسال کنی ⚠\n"
                         f"3️⃣ تا **{TIME_LIMIT} دقیقه** فرصت داری ⏰\n"
                         f"4️⃣ بعد از تایید، لینک اختصاصی گروه اصلی برات ارسال میشه 🔗\n\n"
                         f"💡 اگر هنوز ربات رو استارت نکردی، /start رو بزن تا پیام‌ها بهت برسن!"
                )
            except:
                pass

# -----------------------
# Handle photo
# -----------------------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.id != PRE_GROUP_ID:
        return

    user = update.message.from_user
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user.id,))
    data = cursor.fetchone()
    if not data:
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

    # پیام اعلان حرفه‌ای به گروه ادمین‌ها
    await context.bot.send_message(
        chat_id=ADMIN_GROUP_ID,
        text=f"📩 درخواست جدید وارد شد!\n"
             f"👤 نام: {user.full_name}\n"
             f"🆔 ID: {user.id}\n"
             f"📸 عکس انتخاب واحد دریافت شد.\n"
             f"🔔 تعداد کاربران منتظر بررسی: {waiting_count}\n"
             f"✅ لطفاً Approve ✅ یا Deny ❌ بزنید.",
        reply_to_message_id=forwarded.message_id
    )

    cursor.execute("UPDATE users SET submitted=1 WHERE user_id=?", (user.id,))
    conn.commit()

    # پیام دلنشین به کاربر
    await update.message.reply_text(
        "📨 عکس شما دریافت شد! لطفاً کمی صبر کنید، ادمین‌ها درخواستت رو بررسی می‌کنن 👀"
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
        # پیام خصوصی جذاب و تشویقی
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎉 تبریک {user_id}! تایید شدی 😎\n"
                 f"📌 لینک گروه اصلی ورودی بهمن – گروه ۱:\n{MAIN_GROUP_LINK}\n\n"
                 f"💡 وقتی وارد گروه اصلی شدی، ربات خودکار تو رو از گروه پیش‌ورود kick می‌کنه! 🚀"
        )

        cursor.execute("UPDATE users SET status='approved' WHERE user_id=?", (user_id,))
        conn.commit()

        # لاگ کوتاه و واضح در گروه ادمین‌ها
        await context.bot.send_message(
            ADMIN_GROUP_ID,
            f"✅ {user_id} تایید شد و لینک گروه اصلی برایش ارسال شد. منتظر ورود به گروه اصلی 🕒"
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
# Delete non-photo
# -----------------------
async def delete_non_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.id == PRE_GROUP_ID and not update.message.photo:
        await update.message.delete()

# -----------------------
# مانیتورینگ ورود به گروه اصلی
# -----------------------
async def monitor_main_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # وقتی کاربر وارد گروه اصلی شد، از گروه پیش‌ورود kick بشه
    user = update.chat_member.new_chat_members[0]
    cursor.execute("SELECT status, entered_main_group FROM users WHERE user_id=?", (user.id,))
    data = cursor.fetchone()
    if data and data[0] == 'approved' and data[1] == 0:
        try:
            await context.bot.ban_chat_member(PRE_GROUP_ID, user.id)
            await context.bot.unban_chat_member(PRE_GROUP_ID, user.id)
            cursor.execute("UPDATE users SET entered_main_group=1 WHERE user_id=?", (user.id,))
            conn.commit()

            # پیام خوش‌آمد حرفه‌ای به کاربر بعد از ورود اصلی
            await context.bot.send_message(
                chat_id=user.id,
                text="🎊 تبریک! وارد گروه اصلی شدی 🥳\n"
                     "📚 از همینجا می‌تونی با دوستان و کلاس‌ها ارتباط برقرار کنی 👨‍🎓👩‍🎓"
            )

            # لاگ ورود در گروه ادمین‌ها
            await context.bot.send_message(
                ADMIN_GROUP_ID,
                f"🚀 {user.id} وارد گروه اصلی شد و از پیش‌ورود kick شد."
            )

        except:
            pass

# -----------------------
# اجرای برنامه
# -----------------------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(ChatMemberHandler(new_member, ChatMemberHandler.CHAT_MEMBER))
app.add_handler(ChatMemberHandler(monitor_main_group, ChatMemberHandler.CHAT_MEMBER))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(~filters.PHOTO, delete_non_photo))
app.add_handler(CallbackQueryHandler(button))

app.run_polling()
