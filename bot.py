import os
import sqlite3
import logging
import re
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
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
ADMIN_GROUP_ID = -1003703559282          # گروه ادمین‌ها (بررسی عکس و تیکت)
MAIN_STUDENTS_GROUP_ID = -1003754380100  # گروه اصلی دانشجویان (ورود نهایی)
ADMIN_ID = 7940304990                    # ایدی رئیس ربات
REJECT_BAN_HOURS = 24

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ────────────────────────────────────────────────
# دیتابیس SQLite
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
# پنل رئیس ربات (/admin)
# ────────────────────────────────────────────────
def get_admin_panel():
    keyboard = [
        [InlineKeyboardButton("📊 آمار کاربران", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 پخش همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="admin_search_user")],
        [InlineKeyboardButton("🚫 لیست ردشده‌ها", callback_data="admin_rejected_list")],
        [InlineKeyboardButton("🗑 حذف کاربر", callback_data="admin_delete_user")],
        [InlineKeyboardButton("🔄 ریست وضعیت کاربر", callback_data="admin_reset_user")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ────────────────────────────────────────────────
# تمام توابع (قبل از main تعریف شده‌اند)
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
        f"به ربات رسمی ورودی بهمن خوش اومدی 🎓\n\n"
        f"📸 لطفاً عکس چاپ انتخاب واحد ترم جاری رو برام بفرست\n"
        f"تا بعد از تایید، لینک **اختصاصی** گروه اصلی برات ارسال بشه\n\n"
        "عکس رو بفرست ↓"
    )

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_MENU)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ راهنما\n\n"
        "📸 عکس چاپ انتخاب واحد را ارسال کنید (یک بار)\n"
        "🎫 برای سوال یا مشکل تیکت بزنید\n"
        "❌ در صورت رد شدن عکس، ۲۴ ساعت نمی‌توانید دوباره ارسال کنید\n\n"
        "موفق باشید 🌟"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_MENU)

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📸 ارسال عکس تاییدیه":
        await update.message.reply_text("عکس چاپ انتخاب واحد را ارسال کنید 📷", reply_markup=MAIN_MENU)
        return

    if text == "🎫 ثبت تیکت":
        await update.message.reply_text("مشکل یا سوال خود را بنویسید:", reply_markup=MAIN_MENU)
        context.user_data["awaiting_ticket"] = True
        return

    if text in ["ℹ️ راهنما", "ℹ راهنما"]:
        await cmd_help(update, context)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    now = datetime.now()

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user.id,))
    row = cursor.fetchone()

    if not row:
        await update.message.reply_text("لطفاً ابتدا /start بزنید", reply_markup=MAIN_MENU)
        return

    _, _, submitted_at, reject_until_str = row[3], row[4], row[5], row[6]

    if reject_until_str and now < datetime.fromisoformat(reject_until_str):
        await update.message.reply_text("⛔ فعلاً نمی‌توانید عکس بفرستید (۲۴ ساعت محدودیت)", reply_markup=MAIN_MENU)
        return

    if submitted_at:
        await update.message.reply_text("⚠️ قبلاً عکس ارسال کرده‌اید. منتظر بررسی باشید.", reply_markup=MAIN_MENU)
        return

    forwarded = await context.bot.forward_message(
        ADMIN_GROUP_ID, update.effective_chat.id, update.message.message_id
    )

    keyboard = [
        [InlineKeyboardButton("✅ تایید", callback_data=f"approve_{user.id}"),
         InlineKeyboardButton("❌ رد", callback_data=f"deny_{user.id}")]
    ]

    caption = (
        f"🆕 درخواست عکس\n\n"
        f"نام: {user.full_name}\n"
        f"آیدی: <code>{user.id}</code>\n"
        f"یوزرنیم: @{user.username or 'ندارد'}"
    )

    await context.bot.send_message(
        ADMIN_GROUP_ID, caption, reply_to_message_id=forwarded.message_id,
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
    )

    cursor.execute("UPDATE users SET submitted_at = ?, status = 'submitted' WHERE user_id = ?",
                   (now.isoformat(), user.id))
    conn.commit()

    await update.message.reply_text("عکس دریافت شد. منتظر بررسی باشید.", reply_markup=MAIN_MENU)

async def ticket_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_ticket"):
        return

    user = update.effective_user
    text = update.message.text.strip()

    if not text:
        await update.message.reply_text("لطفاً متن بنویسید", reply_markup=MAIN_MENU)
        return

    keyboard = [
        [
            InlineKeyboardButton("❌ ببند", callback_data=f"close_{user.id}"),
            InlineKeyboardButton("🚫 اسپم", callback_data=f"spam_{user.id}")
        ]
    ]

    msg = (
        f"🎫 تیکت جدید\n\n"
        f"نام: {user.full_name}\n"
        f"آیدی: <code>{user.id}</code>\n"
        f"یوزرنیم: @{user.username or 'ندارد'}\n\n"
        f"متن:\n{text}"
    )

    await context.bot.send_message(
        ADMIN_GROUP_ID,
        msg,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text("تیکت ثبت شد. منتظر پاسخ باشید.", reply_markup=MAIN_MENU)
    context.user_data.pop("awaiting_ticket", None)

async def handle_group_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if message.chat.id != ADMIN_GROUP_ID:
        return

    if message.reply_to_message and "تیکت جدید" in message.reply_to_message.text:
        replied = message.reply_to_message
        reply_text = message.text.strip()

        if not reply_text:
            await message.reply_text("متن پاسخ خالی است", quote=True)
            return

        match = re.search(r"آیدی:\s*(?:<code>)?(\d+)(?:</code>)?", replied.text)
        user_id = int(match.group(1)) if match else None

        if not user_id:
            await message.reply_text("⚠️ آیدی دانشجو پیدا نشد", quote=True)
            return

        try:
            await context.bot.send_message(
                user_id,
                f"📩 پاسخ ادمین:\n\n{reply_text}\n\n────────────────────\nبرای ادامه گفتگو دوباره تیکت بزنید."
            )

            await context.bot.edit_message_text(
                chat_id=ADMIN_GROUP_ID,
                message_id=replied.message_id,
                text=replied.text + "\n\n✅ پاسخ داده شد"
            )

            await message.reply_text("پاسخ با موفقیت ارسال شد.", quote=True)

        except Exception as e:
            await message.reply_text(f"خطا در ارسال پاسخ:\n{str(e)}", quote=True)

        return

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.message.chat.id != ADMIN_GROUP_ID:
        await query.answer("این عملیات فقط در گروه ادمین مجاز است.", show_alert=True)
        return

    data = query.data
    action, uid_str = data.split("_", 1)
    user_id = int(uid_str)

    if action == "approve":
        try:
            invite_link = await context.bot.create_chat_invite_link(
                chat_id=-1003754380100,  # گروه اصلی دانشجویان
                name=f"دعوت {user.full_name} - {datetime.now().strftime('%Y-%m-%d')}",
                member_limit=1,
                expire_date=datetime.now() + timedelta(days=7)
            )
            link = invite_link.invite_link
        except Exception as e:
            logging.error(f"خطا در ساخت لینک دعوت: {str(e)}")
            link = MAIN_GROUP_LINK

        await context.bot.send_message(
            user_id,
            f"🎉 تبریک! انتخاب واحدت تایید شد 🌟\n\n"
            f"لینک اختصاصی گروه اصلی (فقط برای تو):\n{link}\n\n"
            f"این لینک فقط برای ۱ نفر کار می‌کنه و ۷ روز اعتبار داره.\n"
            "موفق باشی ستاره! 🚀",
            disable_web_page_preview=True
        )
        cursor.execute("UPDATE users SET status='approved', reject_until=NULL WHERE user_id=?", (user_id,))
        conn.commit()
        await query.edit_message_text("✅ تایید شد – لینک اختصاصی ارسال گردید")

    elif action == "deny":
        ban_until = (datetime.now() + timedelta(hours=REJECT_BAN_HOURS)).isoformat()
        cursor.execute("UPDATE users SET status='rejected', reject_until=? WHERE user_id=?", (ban_until, user_id))
        conn.commit()
        await context.bot.send_message(user_id, "😔 رد شدید. ۲۴ ساعت دیگر امتحان کنید.")
        await query.edit_message_text("❌ رد شد – ۲۴ ساعت محدودیت")

    elif action == "close":
        await query.edit_message_text(
            query.message.text + "\n\n❌ تیکت بسته شد"
        )
        await query.answer("تیکت بسته شد")

    elif action == "spam":
        ban_until = (datetime.now() + timedelta(hours=REJECT_BAN_HOURS)).isoformat()
        cursor.execute("UPDATE users SET reject_until=? WHERE user_id=?", (ban_until, user_id))
        conn.commit()
        await context.bot.send_message(
            user_id,
            "⛔ تیکت شما اسپم تشخیص داده شد. ۲۴ ساعت محدود شدید."
        )
        await query.edit_message_text(
            query.message.text + "\n\n🚫 اسپم – کاربر محدود شد"
        )
        await query.answer("کاربر محدود شد")

# ────────────────────────────────────────────────
# پنل رئیس ربات (/admin)
# ────────────────────────────────────────────────
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ دسترسی ندارید.")
        return

    await update.message.reply_text(
        "👑 پنل مدیریتی رئیس ربات",
        reply_markup=get_admin_panel()
    )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ دسترسی ندارید.")
        return

    data = query.data

    if data == "admin_stats":
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE status='approved'")
        approved = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE status='rejected'")
        rejected = cursor.fetchone()[0]

        text = f"آمار کاربران:\n\nکل: {total}\nتایید شده: {approved}\nرد شده: {rejected}"
        await query.edit_message_text(text, reply_markup=get_admin_panel())

    elif data == "admin_broadcast":
        await query.edit_message_text("📢 متن پیام همگانی را بنویسید و ارسال کنید.")
        context.user_data["admin_mode"] = "broadcast"

    elif data == "admin_search_user":
        await query.edit_message_text("🔍 آیدی عددی یا یوزرنیم کاربر را وارد کنید.")
        context.user_data["admin_mode"] = "search_user"

    elif data == "admin_rejected_list":
        cursor.execute("SELECT user_id, full_name, username, reject_until FROM users WHERE status = 'rejected'")
        rows = cursor.fetchall()
        text = "هیچ کاربری رد نشده است." if not rows else "🚫 کاربران رد شده:\n\n"
        for r in rows:
            text += f"ID: {r[0]} | {r[1]} | @{r[2] or 'ندارد'} | تا: {r[3] or '-'}\n"
        await query.edit_message_text(text, reply_markup=get_admin_panel())

    elif data == "admin_delete_user":
        await query.edit_message_text("🗑 آیدی عددی کاربر را برای حذف وارد کنید:")
        context.user_data["admin_mode"] = "delete_user"

    elif data == "admin_reset_user":
        await query.edit_message_text("🔄 آیدی عددی کاربر را برای ریست وارد کنید:")
        context.user_data["admin_mode"] = "reset_user"

async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or "admin_mode" not in context.user_data:
        return

    mode = context.user_data["admin_mode"]
    text = update.message.text.strip()

    if mode == "broadcast":
        cursor.execute("SELECT user_id FROM users WHERE status = 'approved'")
        users = [r[0] for r in cursor.fetchall()]
        sent = 0
        for uid in users:
            try:
                await context.bot.send_message(uid, text)
                sent += 1
            except:
                pass
        await update.message.reply_text(f"ارسال شد به {sent} نفر")
        context.user_data.pop("admin_mode", None)

    elif mode == "search_user":
        try:
            uid = int(text)
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
        except ValueError:
            cursor.execute("SELECT * FROM users WHERE username = ?", (text.lstrip('@'),))

        row = cursor.fetchone()
        reply = "کاربر پیدا نشد." if not row else (
            f"ID: {row[0]}\n"
            f"نام: {row[1]}\n"
            f"یوزرنیم: @{row[2] or 'ندارد'}\n"
            f"وضعیت: {row[3]}\n"
            f"ورود: {row[4]}\n"
            f"ارسال عکس: {row[5] or '-'}\n"
            f"رد تا: {row[6] or '-'}"
        )
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
# اجرا
# ────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("admin", admin_panel))

    app.add_handler(MessageHandler(
        filters.Regex("^(📸 ارسال عکس تاییدیه|🎫 ثبت تیکت|ℹ️ راهنما|ℹ راهنما)$"),
        handle_menu
    ))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(📸 ارسال عکس تاییدیه|ℹ️ راهنما|ℹ راهنما)$"),
        ticket_handler
    ))

    app.add_handler(MessageHandler(
        filters.Chat(chat_id=ADMIN_GROUP_ID) & filters.TEXT & ~filters.COMMAND,
        handle_group_reply
    ))

    app.add_handler(CallbackQueryHandler(button))

    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_handler))

    print("ربات شروع شد...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
