import os
import logging
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
MAIN_GROUP_LINK = "https://t.me/+kCh_9St0vVdhNGJk"
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "-1003703559282"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "7940304990"))
REJECT_BAN_HOURS = 24

MONGODB_URI = os.getenv("MONGODB_URI")

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
        total = users_collection.count_documents({})
        approved = users_collection.count_documents({"status": "approved"})
        rejected = users_collection.count_documents({"status": "rejected"})

        text = f"📊 آمار کاربران:\n\nکل: {total}\nتایید شده: {approved}\nرد شده: {rejected}"
        await query.edit_message_text(text, reply_markup=get_admin_panel())

    elif data == "admin_broadcast":
        await query.edit_message_text("📢 متن پیام همگانی را بنویسید و ارسال کنید.")
        context.user_data["admin_mode"] = "broadcast"

    elif data == "admin_search_user":
        await query.edit_message_text("🔍 آیدی عددی یا یوزرنیم کاربر را وارد کنید.")
        context.user_data["admin_mode"] = "search_user"

    elif data == "admin_rejected_list":
        rejected = list(users_collection.find({"status": "rejected"}))
        text = "هیچ کاربری رد نشده است." if not rejected else "🚫 کاربران رد شده:\n\n"
        for u in rejected:
            text += f"ID: {u['user_id']} | {u['full_name']} | @{u.get('username', 'ندارد')} | تا: {u.get('reject_until', '-')}\n"
        await query.edit_message_text(text, reply_markup=get_admin_panel())

    elif data == "admin_delete_user":
        await query.edit_message_text("🗑 آیدی عددی کاربر را وارد کنید.")
        context.user_data["admin_mode"] = "delete_user"

    elif data == "admin_reset_user":
        await query.edit_message_text("🔄 آیدی عددی کاربر را وارد کنید.")
        context.user_data["admin_mode"] = "reset_user"

async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or "admin_mode" not in context.user_data:
        return

    mode = context.user_data["admin_mode"]
    text = update.message.text.strip()

    if mode == "broadcast":
        approved_users = users_collection.find({"status": "approved"})
        sent = 0
        for u in approved_users:
            try:
                await context.bot.send_message(u["user_id"], text)
                sent += 1
            except:
                pass
        await update.message.reply_text(f"پیام به {sent} کاربر تاییدشده ارسال شد.")
        context.user_data.pop("admin_mode", None)

    elif mode == "search_user":
        try:
            uid = int(text)
            user = users_collection.find_one({"user_id": uid})
        except ValueError:
            user = users_collection.find_one({"username": text.lstrip('@')})

        if user:
            reply = (
                f"ID: {user['user_id']}\n"
                f"نام: {user['full_name']}\n"
                f"یوزرنیم: @{user.get('username', 'ندارد')}\n"
                f"وضعیت: {user['status']}\n"
                f"ورود: {user.get('joined_at', '-')}\n"
                f"ارسال عکس: {user.get('submitted_at', '-')}\n"
                f"رد تا: {user.get('reject_until', '-')}"
            )
        else:
            reply = "کاربر پیدا نشد."
        await update.message.reply_text(reply)
        context.user_data.pop("admin_mode", None)

    elif mode == "delete_user":
        try:
            uid = int(text)
            result = users_collection.delete_one({"user_id": uid})
            if result.deleted_count > 0:
                await update.message.reply_text(f"کاربر {uid} حذف شد.")
            else:
                await update.message.reply_text("کاربر پیدا نشد.")
        except:
            await update.message.reply_text("آیدی نامعتبر.")
        context.user_data.pop("admin_mode", None)

    elif mode == "reset_user":
        try:
            uid = int(text)
            users_collection.update_one(
                {"user_id": uid},
                {"$set": {"status": "joined", "submitted_at": None, "reject_until": None}}
            )
            await update.message.reply_text(f"وضعیت کاربر {uid} ریست شد.")
        except:
            await update.message.reply_text("آیدی نامعتبر.")
        context.user_data.pop("admin_mode", None)

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
        users_collection.insert_one({
            "user_id": user.id,
            "full_name": user.full_name,
            "username": user.username,
            "status": "joined",
            "joined_at": now.isoformat()
        })
        user_data = users_collection.find_one({"user_id": user.id})

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

    # هندلر گروه ادمین (اول اضافه شده تا reply رو بگیره)
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
