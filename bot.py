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
    ConversationHandler,
    filters,
    ContextTypes,
)

# ────────────────────────────────────────────────
# تنظیمات اصلی
# ────────────────────────────────────────────────
TOKEN = os.getenv("TOKEN")
MAIN_GROUP_LINK = "https://t.me/+kCh_9St0vVdhNGJk"
ADMIN_GROUP_ID = -1003703559282                 # ایدی گروه ادمین‌ها
ADMIN_ID = 123456789                           # ← ایدی عددی ادمین اصلی (رئیس ربات) رو اینجا وارد کن

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
            InlineKeyboardButton("🔄 ریست وضعیت کاربر", callback_data="admin_reset_user")
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
        f"📸 لطفاً <b>عکس چاپ انتخاب واحد</b> ترم جاری رو برام بفرست\n"
        f"تا بعد از تایید، لینک گروه اصلی رو برات ارسال کنم 🚀\n\n"
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
# هندلر callback پنل ادمین
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
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'approved'")
        approved = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'rejected'")
        rejected = cursor.fetchone()[0]

        text = (
            f"📊 آمار کاربران:\n\n"
            f"کل کاربران: {total}\n"
            f"تایید شده: {approved}\n"
            f"رد شده: {rejected}"
        )
        await query.edit_message_text(text, reply_markup=get_admin_panel())

    elif data == "admin_broadcast":
        await query.edit_message_text("📢 متن پیام همگانی را بنویس و ارسال کن.")
        context.user_data["admin_mode"] = "broadcast"

    elif data == "admin_search_user":
        await query.edit_message_text("🔍 آیدی عددی یا یوزرنیم کاربر را وارد کن.")
        context.user_data["admin_mode"] = "search_user"

    elif data == "admin_rejected_list":
        cursor.execute("SELECT user_id, full_name, username, reject_until FROM users WHERE status = 'rejected'")
        rows = cursor.fetchall()
        if not rows:
            text = "هیچ کاربری رد نشده است."
        else:
            text = "🚫 کاربران رد شده:\n\n"
            for r in rows:
                text += f"ID: {r[0]} | {r[1]} | @{r[2] or 'ندارد'} | تا: {r[3] or '-'}\n"
        await query.edit_message_text(text, reply_markup=get_admin_panel())

    elif data == "admin_delete_user":
        await query.edit_message_text("🗑 آیدی عددی کاربر را برای حذف وارد کن.")
        context.user_data["admin_mode"] = "delete_user"

    elif data == "admin_reset_user":
        await query.edit_message_text("🔄 آیدی عددی کاربر را برای ریست وضعیت وارد کن.")
        context.user_data["admin_mode"] = "reset_user"

# ────────────────────────────────────────────────
# هندلر متن‌های ادمین
# ────────────────────────────────────────────────
async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if "admin_mode" not in context.user_data:
        return

    mode = context.user_data["admin_mode"]
    text = update.message.text.strip()

    if mode == "broadcast":
        cursor.execute("SELECT user_id FROM users WHERE status = 'approved'")
        users = [row[0] for row in cursor.fetchall()]
        sent = 0
        for uid in users:
            try:
                await context.bot.send_message(uid, text)
                sent += 1
            except:
                pass
        await update.message.reply_text(f"پیام به {sent} نفر ارسال شد.")
        context.user_data.pop("admin_mode", None)

    elif mode == "search_user":
        try:
            uid = int(text)
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
        except ValueError:
            cursor.execute("SELECT * FROM users WHERE username = ?", (text.lstrip('@'),))

        row = cursor.fetchone()
        if row:
            reply = (
                f"ID: {row[0]}\n"
                f"نام: {row[1]}\n"
                f"یوزرنیم: @{row[2] or 'ندارد'}\n"
                f"وضعیت: {row[3]}\n"
                f"ورود: {row[4]}\n"
                f"ارسال عکس: {row[5] or '-'}\n"
                f"رد تا: {row[6] or '-'}"
            )
        else:
            reply = "کاربر پیدا نشد."
        await update.message.reply_text(reply)
        context.user_data.pop("admin_mode", None)

    elif mode == "delete_user":
        try:
            uid = int(text)
            cursor.execute("DELETE FROM users WHERE user_id = ?", (uid,))
            conn.commit()
            await update.message.reply_text(f"کاربر {uid} حذف شد.")
        except:
            await update.message.reply_text("آیدی نامعتبر.")
        context.user_data.pop("admin_mode", None)

    elif mode == "reset_user":
        try:
            uid = int(text)
            cursor.execute(
                "UPDATE users SET status = 'joined', submitted_at = NULL, reject_until = NULL WHERE user_id = ?",
                (uid,)
            )
            conn.commit()
            await update.message.reply_text(f"وضعیت کاربر {uid} ریست شد.")
        except:
            await update.message.reply_text("آیدی نامعتبر.")
        context.user_data.pop("admin_mode", None)

# ────────────────────────────────────────────────
# راهنما
# ────────────────────────────────────────────────
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ <b>راهنما</b>\n\n"
        "📸 عکس چاپ انتخاب واحد رو برام بفرست\n"
        "فقط یک بار می‌تونی ارسال کنی\n\n"
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
            "عکس چاپ انتخاب واحد رو برام بفرست 📷",
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

    elif action == "reply_ticket":
        await query.edit_message_text(query.message.text + "\n\n📝 منتظر پاسخ ادمین...")
        context.user_data["replying_to_user"] = user_id
        context.user_data["replying_message_id"] = query.message.message_id
        await context.bot.send_message(
            query.from_user.id,
            "لطفاً متن پاسخ به تیکت رو بنویس و ارسال کن 😊"
        )
        return "WAITING_REPLY"

# ────────────────────────────────────────────────
# دریافت تیکت (با دکمه پاسخ)
# ────────────────────────────────────────────────
async def ticket_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_ticket"):
        return

    user = update.effective_user
    text = update.message.text.strip()

    if not text:
        await update.message.reply_text("لطفاً چیزی بنویس 😅", reply_markup=MAIN_MENU)
        return

    keyboard = [[InlineKeyboardButton("📩 پاسخ بده", callback_data=f"reply_ticket_{user.id}")]]

    admin_msg = (
        f"🎫 تیکت جدید\n\n"
        f"نام: {user.full_name}\n"
        f"آیدی: <code>{user.id}</code>\n"
        f"یوزرنیم: @{user.username or 'ندارد'}\n\n"
        f"متن:\n{text}"
    )

    sent_msg = await context.bot.send_message(
        ADMIN_GROUP_ID, admin_msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text(
        "✅ تیکت ثبت شد!\nبه‌زودی جواب می‌دن. ممنون از صبرت 💙",
        reply_markup=MAIN_MENU
    )

    context.user_data.pop("awaiting_ticket", None)

# ────────────────────────────────────────────────
# دریافت متن پاسخ از ادمین (حالت مکالمه)
# ────────────────────────────────────────────────
async def receive_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_text = update.message.text.strip()
    user_id = context.user_data.get("replying_to_user")
    message_id = context.user_data.get("replying_message_id")

    if not user_id or not reply_text:
        await update.message.reply_text("⚠️ مشکلی پیش اومد. دوباره امتحان کن.")
        return ConversationHandler.END

    try:
        await context.bot.send_message(
            user_id,
            f"📩 پاسخ ادمین به تیکت شما:\n\n{reply_text}\n\n───────────────────\nاگر نیاز به ادامه داری، دوباره تیکت بزن 🎫"
        )
        await context.bot.edit_message_text(
            chat_id=ADMIN_GROUP_ID,
            message_id=message_id,
            text=await context.bot.get_message(ADMIN_GROUP_ID, message_id).text + "\n\n✅ پاسخ داده شد"
        )
        await update.message.reply_text("✅ پاسخ ارسال شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {str(e)}")

    context.user_data.pop("replying_to_user", None)
    context.user_data.pop("replying_message_id", None)
    return ConversationHandler.END

# ────────────────────────────────────────────────
# لغو پاسخ
# ────────────────────────────────────────────────
async def cancel_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("replying_to_user", None)
    context.user_data.pop("replying_message_id", None)
    await update.message.reply_text("پاسخ‌دهی لغو شد.")
    return ConversationHandler.END

# ────────────────────────────────────────────────
# اجرا
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

    # جدید: مکالمه برای پاسخ تیکت
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button, pattern="^reply_ticket_")],
        states={"WAITING_REPLY": [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_reply)]},
        fallbacks=[CommandHandler("cancel", cancel_reply)]
    )
    app.add_handler(conv_handler)

    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(button))  # برای approve/deny
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_handler))

    print("ربات شروع به کار کرد...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
