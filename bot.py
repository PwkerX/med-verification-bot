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

TIME_LIMIT = 15

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
# New member handler
# -----------------------
async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.chat_member.new_chat_members:
        if update.chat_member.chat.id == PRE_GROUP_ID:
            cursor.execute("""
            INSERT OR REPLACE INTO users 
            (user_id, full_name, status, joined_at, submitted, reject_until)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                member.id,
                member.full_name,
                "joined",
                datetime.now().isoformat(),
                0,
                None
            ))
            conn.commit()

            try:
                await context.bot.send_message(
                    chat_id=member.id,
                    text="👋 خوش آمدید.\nلطفاً ظرف ۱۵ دقیقه تصویر انتخاب واحد خود را ارسال کنید."
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

    reject_until = data[5]
    if reject_until:
        if datetime.now() < datetime.fromisoformat(reject_until):
            await update.message.reply_text("⛔ فعلاً اجازه ارسال ندارید.")
            return

    joined_at = datetime.fromisoformat(data[3])
    if datetime.now() - joined_at > timedelta(minutes=TIME_LIMIT):
        await update.message.reply_text("⌛ زمان شما تمام شده.")
        return

    if data[4] == 1:
        await update.message.reply_text("⚠ قبلاً ارسال کرده‌اید.")
        return

    photo = update.message.photo[-1].file_id

    keyboard = [[
        InlineKeyboardButton("Approve ✅", callback_data=f"approve_{user.id}"),
        InlineKeyboardButton("Deny ❌", callback_data=f"deny_{user.id}")
    ]]

    sent = await context.bot.send_photo(
        chat_id=ADMIN_GROUP_ID,
        photo=photo,
        caption=f"درخواست جدید\n{user.full_name}\nID: {user.id}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    cursor.execute("UPDATE users SET submitted=1 WHERE user_id=?", (user.id,))
    conn.commit()

    await update.message.reply_text("✅ ارسال شد. منتظر بررسی باشید.")

# -----------------------
# Approve / Deny
# -----------------------
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split("_")
    user_id = int(user_id)

    if action == "approve":
        await context.bot.send_message(user_id, f"🎉 تایید شدید!\n{MAIN_GROUP_LINK}")

        await context.bot.ban_chat_member(PRE_GROUP_ID, user_id)
        await context.bot.unban_chat_member(PRE_GROUP_ID, user_id)

        cursor.execute("UPDATE users SET status='approved' WHERE user_id=?", (user_id,))
        conn.commit()

    elif action == "deny":
        reject_time = datetime.now() + timedelta(hours=24)
        cursor.execute("UPDATE users SET status='rejected', reject_until=? WHERE user_id=?",
                       (reject_time.isoformat(), user_id))
        conn.commit()

        await context.bot.send_message(user_id, "❌ رد شدید. تا ۲۴ ساعت امکان ارسال ندارید.")

    await context.bot.delete_message(ADMIN_GROUP_ID, query.message.message_id)

# -----------------------
# Delete non-photo
# -----------------------
async def delete_non_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.id == PRE_GROUP_ID and not update.message.photo:
        await update.message.delete()

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(ChatMemberHandler(new_member, ChatMemberHandler.CHAT_MEMBER))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(~filters.PHOTO, delete_non_photo))
app.add_handler(CallbackQueryHandler(button))

app.run_polling()
