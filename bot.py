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
# تنظیمات اصلی
# ────────────────────────────────────────────────
TOKEN = os.getenv("TOKEN")
MAIN_GROUP_LINK = "https://t.me/+kCh_9St0vVdhNGJk"
ADMIN_GROUP_ID = -1003703559282                 # ایدی گروه ادمین‌ها
ADMIN_ID = 7940304990                           # ← ایدی عددی ادمین اصلی (رئیس ربات) رو اینجا وارد کن

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
# منوی اصلی برای کاربران عادی
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
# منوی ادمین اصلی (پنل مدیریتی)
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
            InlineKeyboardButton("🔄 ریست تایمر کاربر", callback_data="admin_reset_timer")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ────────────────────────────────────────────────
# شروع
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
        f"📸 لطفاً <b>عکس چاپ انتخاب واحد</b> ترم جاری رو همین الان برام بفرست\n"
        f"تا بعد از تایید، لینک گروه اصلی رو برات ارسال کنم 🚀\n\n"
        f"⏰ فقط <b>{TIME_LIMIT_MINUTES}</b> دقیقه از همین الان فرصت داری!\n\n"
        "عکس رو بفرست ↓"
    )

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_MENU)

# ────────────────────────────────────────────────
# دستور /admin برای ادمین اصلی
# ────────────────────────────────────────────────
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ شما دسترسی به پنل ادمین ندارید.")
        return

    await update.message.reply_text(
        "👤 پنل مدیریتی رئیس ربات\n\n"
        "گزینه مورد نظر را انتخاب کنید:",
        reply_markup=get_admin_panel()
    )

# ────────────────────────────────────────────────
# هندلر callback برای پنل ادمین
# ────────────────────────────────────────────────
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id
    if user_id != ADMIN_ID:
        await query.edit_message_text("❌ دسترسی ندارید.")
        return

    if data == "admin_stats":
        # آمار کاربران
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'approved'")
        approved = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'rejected'")
        rejected = cursor.fetchone()[0]

        text = (
            f"📊 آمار کلی:\n\n"
            f"کل کاربران: {total_users}\n"
            f"تایید شده: {approved}\n"
            f"رد شده: {rejected}"
        )
        await query.edit_message_text(text, reply_markup=get_admin_panel())

    elif data == "admin_broadcast":
        # شروع پخش پیام همگانی
        await query.edit_message_text(
            "📢 لطفاً متن پیام همگانی را بنویسید و ارسال کنید."
        )
        context.user_data["admin_mode"] = "broadcast"

    elif data == "admin_search_user":
        await query.edit_message_text(
            "🔍 آیدی عددی یا یوزرنیم کاربر را وارد کنید."
        )
        context.user_data["admin_mode"] = "search_user"

    elif data == "admin_rejected_list":
        # لیست رد شده‌ها
        cursor.execute("SELECT user_id, full_name, username, reject_until FROM users WHERE status = 'rejected'")
        rejected_users = cursor.fetchall()

        text = "🚫 لیست کاربران رد شده:\n\n"
        for u in rejected_users:
            text += f"ID: {u[0]} | نام: {u[1]} | @{u[2] or 'ندارد'} | تا: {u[3] or 'نامحدود'}\n"

        if not rejected_users:
            text += "هیچ کاربری رد نشده."

        await query.edit_message_text(text, reply_markup=get_admin_panel())

    elif data == "admin_delete_user":
        await query.edit_message_text(
            "🗑 آیدی عددی کاربر را برای پاک کردن وارد کنید."
        )
        context.user_data["admin_mode"] = "delete_user"

    elif data == "admin_reset_timer":
        await query.edit_message_text(
            "🔄 آیدی عددی کاربر را برای ریست تایمر وارد کنید."
        )
        context.user_data["admin_mode"] = "reset_timer"

# ────────────────────────────────────────────────
# هندلر متن برای حالت‌های ادمین
# ────────────────────────────────────────────────
async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID or "admin_mode" not in context.user_data:
        return

    mode = context.user_data["admin_mode"]
    text = update.message.text.strip()

    if mode == "broadcast":
        # ارسال پیام همگانی به همه کاربران تایید شده
        cursor.execute("SELECT user_id FROM users WHERE status = 'approved'")
        users = cursor.fetchall()

        sent = 0
        for u in users:
            try:
                await context.bot.send_message(u[0], text)
                sent += 1
            except:
                pass

        await update.message.reply_text(f"✅ پیام به {sent} کاربر تایید شده ارسال شد.")
        del context.user_data["admin_mode"]

    elif mode == "search_user":
        # جستجوی کاربر
        try:
            uid = int(text)
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
        except:
            cursor.execute("SELECT * FROM users WHERE username = ?", (text,))

        row = cursor.fetchone()
        if row:
            text = (
                f"👤 اطلاعات کاربر:\n\n"
                f"ID: {row[0]}\n"
                f"نام: {row[1]}\n"
                f"@: {row[2]}\n"
                f"وضعیت: {row[3]}\n"
                f"ورود: {row[4]}\n"
                f"ارسال: {row[5]}\n"
                f"رد تا: {row[6]}"
            )
        else:
            text = "❌ کاربر پیدا نشد."

        await update.message.reply_text(text)
        del context.user_data["admin_mode"]

    elif mode == "delete_user":
        try:
            uid = int(text)
            cursor.execute("DELETE FROM users WHERE user_id = ?", (uid,))
            conn.commit()
            await update.message.reply_text(f"✅ کاربر {uid} پاک شد.")
        except:
            await update.message.reply_text("❌ آیدی نامعتبر.")

        del context.user_data["admin_mode"]

    elif mode == "reset_timer":
        try:
            uid = int(text)
            cursor.execute(
                "UPDATE users SET reject_until = NULL, submitted_at = NULL, joined_at = ? WHERE user_id = ?",
                (datetime.now().isoformat(), uid)
            )
            conn.commit()
            await update.message.reply_text(f"✅ تایمر کاربر {uid} ریست شد.")
        except:
            await update.message.reply_text("❌ آیدی نامعتبر.")

        del context.user_data["admin_mode"]

# ────────────────────────────────────────────────
# راهنما
# ────────────────────────────────────────────────
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ <b>راهنما</b>\n\n"
        f"📸 عکس چاپ انتخاب واحد رو تا {TIME_LIMIT_MINUTES} دقیقه بعد از استارت می‌تونی بفرستی\n"
        "فقط یک بار فرصت ارسال داری\n\n"
        "🎫 هر سوال یا مشکلی داشتی تیکت بزن\n"
        "ادمین‌ها سریع جواب می‌دن\n\n"
        "❌ اگر عکست رد بشه ۲۴ ساعت نمی‌تونی دوباره ارسال کنی\n\n"
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

    if text == "🎫 ثبت تیکت":
        await update.message.reply_text(
            "لطفاً مشکل یا سوالت رو واضح بنویس و ارسال کن\n"
            "ادمین‌ها زود جواب می‌دن 😊",
            reply_markup=MAIN_MENU
        )
        context.user_data["awaiting_ticket"] = True
        return

    if text in ["ℹ️ راهنما", "ℹ راهنما"]:
        await cmd_help(update, context)

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

    joined_at = datetime.fromisoformat(joined_at_str)
    if (now - joined_at).total_seconds() > TIME_LIMIT_MINUTES * 60:
        await update.message.reply_text(
            f"⌛ مهلت {TIME_LIMIT_MINUTES} دقیقه‌ای تموم شد.\nفردا دوباره /start بزن",
            reply_markup=MAIN_MENU
        )
        return

    if submitted_at is not None:
        await update.message.reply_text(
            "⚠️ قبلاً عکس فرستادی و در حال بررسیه.\nلطفاً صبر کن یا تیکت بزن",
            reply_markup=MAIN_MENU
        )
        return

    forwarded = await context.bot.forward_message(
        ADMIN_GROUP_ID, update.effective_chat.id, update.message.message_id
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
# تایید / رد عکس
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
# دریافت تیکت از دانشجو
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
# پاسخ ادمین به تیکت (Reply در گروه ادمین)
# ────────────────────────────────────────────────
async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if message.chat.id != ADMIN_GROUP_ID:
        return

    if not message.reply_to_message:
        return

    replied = message.reply_to_message
    if not replied.text or "تیکت جدید" not in replied.text:
        return

    # استخراج user_id
    user_id = None
    for line in replied.text.split("\n"):
        if "آیدی:" in line or "🆔" in line:
            try:
                part = line.split(":", 1)[1].strip()
                part = part.replace("<code>", "").replace("</code>", "")
                user_id = int(part)
                break
            except:
                pass

    if not user_id:
        await message.reply_text("⚠️ آیدی دانشجو پیدا نشد", quote=True)
        return

    reply_text = message.text.strip()
    if not reply_text:
        await message.reply_text("متن پاسخ خالیه!", quote=True)
        return

    try:
        await context.bot.send_message(
            user_id,
            "📩 پاسخ ادمین به تیکت شما:\n\n"
            f"{reply_text}\n\n"
            "───────────────────\n"
            "اگر نیاز به ادامه گفتگو داری، دوباره تیکت بزن 🎫"
        )

        await message.reply_text(f"✅ پاسخ برای {user_id} ارسال شد", quote=True)

    except Exception as e:
        await message.reply_text(
            f"❌ خطا در ارسال پاسخ:\n{str(e)}\n\n"
            "ممکن است دانشجو ربات رو بلاک کرده یا /start نزده باشه.",
            quote=True
        )

# ────────────────────────────────────────────────
# اجرا
# ────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("admin", admin_panel))  # جدید: پنل ادمین

    app.add_handler(MessageHandler(
        filters.Regex(r"^(📸 ارسال عکس تاییدیه|🎫 ثبت تیکت|ℹ️ راهنما|ℹ راهنما)$"),
        handle_menu
    ))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex(r"^(📸 ارسال عکس تاییدیه|🎫 ثبت تیکت|ℹ️ راهنما|ℹ راهنما)$"),
        ticket_handler
    ))

    app.add_handler(MessageHandler(
        filters.Chat(ADMIN_GROUP_ID) & filters.TEXT & ~filters.COMMAND,
        handle_admin_reply
    ))

    # جدید: متن ادمین + callback
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_handler))

    print("ربات شروع به کار کرد...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
