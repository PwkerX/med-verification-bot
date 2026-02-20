import os
import logging
import re
from datetime import datetime, timedelta
from pymongo import MongoClient
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
MAIN_GROUP_LINK = os.getenv("MAIN_GROUP_LINK", "https://t.me/+kCh_9St0vVdhNGJk")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "-1003703559282"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "7940304990"))
REJECT_BAN_HOURS = int(os.getenv("REJECT_BAN_HOURS", "24"))

MONGODB_URI = os.getenv("MONGODB_URI")

if not MONGODB_URI:
    raise ValueError("MONGODB_URI تنظیم نشده است.")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# اتصال به MongoDB
client = MongoClient(MONGODB_URI)
db = client["medical_students"]
users_collection = db["users"]

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
# شروع
# ────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    now = datetime.now()

    user_data = users_collection.find_one({"user_id": user.id})
    if not user_data:
        users_collection.insert_one({
            "user_id": user.id,
            "full_name": user.full_name,
            "username": user.username,
            "status": "joined",
            "joined_at": now.isoformat()
        })

    text = (
        f"سلام {user.first_name} 👋\n\n"
        f"به ربات رسمی ورودی بهمن خوش اومدی 🎓\n\n"
        f"📸 لطفاً عکس چاپ انتخاب واحد ترم جاری رو برام بفرست\n"
        f"تا بعد از تایید، لینک گروه اصلی برات ارسال بشه\n\n"
        "عکس رو بفرست ↓"
    )

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_MENU)

# ────────────────────────────────────────────────
# راهنما
# ────────────────────────────────────────────────
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ راهنما\n\n"
        "📸 عکس چاپ انتخاب واحد را ارسال کنید (یک بار)\n"
        "🎫 برای سوال یا مشکل تیکت بزنید\n"
        "❌ در صورت رد شدن عکس، ۲۴ ساعت نمی‌توانید دوباره ارسال کنید\n\n"
        "موفق باشید 🌟"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_MENU)

# ────────────────────────────────────────────────
# دکمه‌های منو
# ────────────────────────────────────────────────
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

# ────────────────────────────────────────────────
# دریافت عکس
# ────────────────────────────────────────────────
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    now = datetime.now()

    user_data = users_collection.find_one({"user_id": user.id})
    if not user_data:
        await update.message.reply_text("لطفاً ابتدا /start بزنید", reply_markup=MAIN_MENU)
        return

    reject_until_str = user_data.get("reject_until")
    submitted_at = user_data.get("submitted_at")

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

    users_collection.update_one(
        {"user_id": user.id},
        {"$set": {"submitted_at": now.isoformat(), "status": "submitted"}}
    )

    await update.message.reply_text("عکس دریافت شد. منتظر بررسی باشید.", reply_markup=MAIN_MENU)

# ────────────────────────────────────────────────
# ثبت تیکت
# ────────────────────────────────────────────────
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

# ────────────────────────────────────────────────
# پاسخ‌دهی با Reply در گروه + دکمه‌های بستن و اسپم
# ────────────────────────────────────────────────
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

# ────────────────────────────────────────────────
# دکمه‌های inline (تایید، رد، بستن، اسپم)
# ────────────────────────────────────────────────
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
        await context.bot.send_message(
            user_id,
            f"🎉 تایید شدید!\n\nلینک گروه:\n{MAIN_GROUP_LINK}\n\nموفق باشید!",
            disable_web_page_preview=True
        )
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"status": "approved", "reject_until": None}}
        )
        await query.edit_message_text("✅ تایید شد – لینک ارسال گردید")

    elif action == "deny":
        ban_until = (datetime.now() + timedelta(hours=REJECT_BAN_HOURS)).isoformat()
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"status": "rejected", "reject_until": ban_until}}
        )
        await context.bot.send_message(user_id, "😔 رد شدید. ۲۴ ساعت دیگر امتحان کنید.")
        await query.edit_message_text("❌ رد شد – ۲۴ ساعت محدودیت")

    elif action == "close":
        await query.edit_message_text(
            query.message.text + "\n\n❌ تیکت بسته شد"
        )
        await query.answer("تیکت بسته شد")

    elif action == "spam":
        ban_until = (datetime.now() + timedelta(hours=REJECT_BAN_HOURS)).isoformat()
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"reject_until": ban_until}}
        )
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
