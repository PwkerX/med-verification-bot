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
ADMIN_GROUP_ID = -1003703559282                 # ← اینجا را درست کن

TIME_LIMIT_MINUTES = 15
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
# منوی اصلی
# ────────────────────────────────────────────────
MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("📸 ارسال عکس تاییدیه")],
        [KeyboardButton("🎫 ثبت تیکت")],
        [KeyboardButton("ℹ️ راهنما")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# ────────────────────────────────────────────────
# شروع
# ────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    now = datetime.now()

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user.id,))
    record = cursor.fetchone()

    if not record:
        cursor.execute("""
        INSERT INTO users
        (user_id, full_name, username, joined_at)
        VALUES (?, ?, ?, ?)
        """, (user.id, user.full_name, user.username, now.isoformat()))
        conn.commit()

    text = (
        f"سلام {user.first_name} 👋\n\n"
        f"به ربات رسمی <b>ورودی بهمن</b> خوش اومدی 🎓✨\n\n"
        f"📸 لطفاً <b>عکس چاپ انتخاب واحد</b> ترم جاری رو همین الان برام بفرست\n"
        f"تا بعد از تایید، لینک گروه اصلی رو برات ارسال کنم 🚀\n\n"
        f"⏰ فقط <b>{TIME_LIMIT_MINUTES}</b> دقیقه از همین الان فرصت داری!\n\n"
        "عکس رو بفرست ↓"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=MAIN_MENU
    )

# ────────────────────────────────────────────────
# راهنما
# ────────────────────────────────────────────────
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ <b>راهنما</b>\n\n"
        f"📸 عکس چاپ انتخاب واحد رو می‌تونی تا {TIME_LIMIT_MINUTES} دقیقه بعد از استارت فرستادن\n"
        "فقط یک بار می‌تونی ارسال کنی\n\n"
        "🎫 هر سوال یا مشکلی داشتی تیکت بزن\n"
        "ادمین‌ها سریع جواب می‌دن\n\n"
        "❌ اگه عکست رد بشه ۲۴ ساعت نمی‌تونی دوباره بفرستی\n\n"
        "موفق باشی 🌟"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_MENU)

# ────────────────────────────────────────────────
# دکمه‌های منو
# ────────────────────────────────────────────────
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📸 ارسال عکس تاییدیه":
        await update.message.reply_text(
            f"عکس چاپ انتخاب واحد رو برام بفرست 📷\n"
            f"⏳ فقط {TIME_LIMIT_MINUTES} دقیقه فرصت داری!",
            reply_markup=MAIN_MENU
        )
        return

    elif text == "🎫 ثبت تیکت":
        await update.message.reply_text(
            "لطفاً مشکل یا سوالت رو واضح بنویس و ارسال کن\n"
            "ادمین‌ها زود جواب می‌دن 😊",
            reply_markup=MAIN_MENU
        )
        context.user_data["awaiting_ticket"] = True
        return

    elif text in ["ℹ️ راهنما", "ℹ راهنما"]:
        await cmd_help(update, context)
        return

# ────────────────────────────────────────────────
# دریافت عکس
# ────────────────────────────────────────────────
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    now = datetime.now()

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user.id,))
    row = cursor.fetchone()

    if not row:
        await update.message.reply_text("اول /start رو بزن لطفاً 😊", reply_markup=MAIN_MENU)
        return

    status, joined_at_str, submitted_at, reject_until_str = row[3], row[4], row[5], row[6]

    # محرومیت ۲۴ ساعته
    if reject_until_str:
        reject_until = datetime.fromisoformat(reject_until_str)
        if now < reject_until:
            remaining = reject_until - now
            h = remaining.seconds // 3600
            m = (remaining.seconds % 3600) // 60
            await update.message.reply_text(
                f"⛔ تا {h} ساعت و {m} دقیقه دیگه نمی‌تونی عکس بفرستی.\nفردا دوباره امتحان کن",
                reply_markup=MAIN_MENU
            )
            return

    # مهلت زمانی
    joined_at = datetime.fromisoformat(joined_at_str)
    if (now - joined_at).total_seconds() > TIME_LIMIT_MINUTES * 60:
        await update.message.reply_text(
            f"⌛ مهلت {TIME_LIMIT_MINUTES} دقیقه‌ای تموم شد.\nفردا دوباره /start بزن",
            reply_markup=MAIN_MENU
        )
        return

    # قبلاً ارسال کرده؟
    if submitted_at is not None:
        await update.message.reply_text(
            "⚠️ قبلاً عکس فرستادی و در حال بررسیه.\nلطفاً صبر کن یا تیکت بزن",
            reply_markup=MAIN_MENU
        )
        return

    # فوروارد به ادمین‌ها
    forwarded = await context.bot.forward_message(
        ADMIN_GROUP_ID,
        update.effective_chat.id,
        update.message.message_id
    )

    keyboard = [[
        InlineKeyboardButton("✅ تایید", callback_data=f"approve_{user.id}"),
        InlineKeyboardButton("❌ رد", callback_data=f"deny_{user.id}")
    ]]

    caption = (
        f"🆕 درخواست جدید\n\n"
        f"نام: {user.full_name}\n"
        f"آیدی: <code>{user.id}</code>\n"
        f"یوزرنیم: @{user.username or 'ندارد'}"
    )

    await context.bot.send_message(
        ADMIN_GROUP_ID,
        caption,
        reply_to_message_id=forwarded.message_id,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

    cursor.execute(
        "UPDATE users SET submitted_at = ?, status = 'submitted' WHERE user_id = ?",
        (now.isoformat(), user.id)
    )
    conn.commit()

    await update.message.reply_text(
        "📤 عکس دریافت شد!\nلطفاً کمی صبر کن تا بررسی بشه 🚀",
        reply_markup=MAIN_MENU
    )

# ────────────────────────────────────────────────
# تایید / رد
# ────────────────────────────────────────────────
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, uid_str = query.data.split("_")
    user_id = int(uid_str)

    if action == "approve":
        await context.bot.send_message(
            user_id,
            f"🎉 تبریک! انتخاب واحدت تایید شد 🌟\n\n"
            f"لینک گروه اصلی:\n{MAIN_GROUP_LINK}\n\n"
            "موفق باشی ستاره! 🚀",
            disable_web_page_preview=True
        )

        cursor.execute("UPDATE users SET status = 'approved', reject_until = NULL WHERE user_id = ?", (user_id,))
        conn.commit()

        await query.edit_message_text("✅ تایید شد – لینک ارسال گردید")

    elif action == "deny":
        ban_until = (datetime.now() + timedelta(hours=REJECT_BAN_HOURS)).isoformat()

        cursor.execute(
            "UPDATE users SET status = 'rejected', reject_until = ? WHERE user_id = ?",
            (ban_until, user_id)
        )
        conn.commit()

        await context.bot.send_message(
            user_id,
            f"😔 این بار تایید نشد...\n\n"
            f"۲۴ ساعت دیگه دوباره امتحان کن.\n"
            "مطمئن شو عکس واضح و درست باشه 😉",
            reply_markup=MAIN_MENU
        )

        await query.edit_message_text("❌ رد شد – ۲۴ ساعت محرومیت")

# ────────────────────────────────────────────────
# دریافت تیکت
# ────────────────────────────────────────────────
async def ticket_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_ticket"):
        return

    user = update.effective_user
    text = update.message.text.strip()

    if not text:
        await update.message.reply_text("لطفاً چیزی بنویس 😅", reply_markup=MAIN_MENU)
        return

    admin_msg = (
        f"🎫 تیکت جدید\n\n"
        f"نام: {user.full_name}\n"
        f"آیدی: <code>{user.id}</code>\n"
        f"یوزرنیم: @{user.username or 'ندارد'}\n\n"
        f"متن:\n{text}"
    )

    await context.bot.send_message(ADMIN_GROUP_ID, admin_msg, parse_mode="HTML")

    await update.message.reply_text(
        "✅ تیکت ثبت شد!\nبه‌زودی جواب می‌دن. ممنون از صبرت 💙",
        reply_markup=MAIN_MENU
    )

    context.user_data.pop("awaiting_ticket", None)

# ────────────────────────────────────────────────
# اجرا
# ────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", cmd_help))

    app.add_handler(MessageHandler(
        filters.Regex(r"^(📸 ارسال عکس تاییدیه|🎫 ثبت تیکت|ℹ️ راهنما|ℹ راهنما)$"),
        handle_menu
    ))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex(r"^(📸 ارسال عکس تاییدیه|🎫 ثبت تیکت|ℹ️ راهنما|ℹ راهنما)$"),
        ticket_handler
    ))

    app.add_handler(CallbackQueryHandler(button))

    print("ربات شروع شد ...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
