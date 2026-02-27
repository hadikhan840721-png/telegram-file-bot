import sqlite3
import asyncio
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# =======================
# تنظیمات خودت
# =======================
TOKEN = "8650597714:AAFZfNrn11Ew_oFY4eEv27DfjiGL0WeDtiM"
ADMIN_ID = 6893010982
STORAGE_CHANNEL = -1003779730637
# =======================

# دیتابیس
db = sqlite3.connect("data.db", check_same_thread=False)
cur = db.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)")
cur.execute("CREATE TABLE IF NOT EXISTS channels (username TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, msg_id INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT, value TEXT)")
db.commit()


# =======================
# توابع کمکی
# =======================
def add_user(uid):
    cur.execute("INSERT OR IGNORE INTO users VALUES (?)", (uid,))
    db.commit()


def get_setting(key, default=0):
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    return int(row[0]) if row else default


def set_setting(key, value):
    cur.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, str(value)))
    db.commit()


async def check_join(user_id, bot):
    cur.execute("SELECT username FROM channels")
    channels = cur.fetchall()
    not_joined = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch[0], user_id)
            if member.status in ["left", "kicked"]:
                not_joined.append(ch[0])
        except:
            pass
    return not_joined


def join_buttons(channels):
    buttons = [[InlineKeyboardButton(f"عضویت در {ch}", url=f"https://t.me/{ch.replace('@','')}")] for ch in channels]
    buttons.append([InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")])
    return InlineKeyboardMarkup(buttons)


async def auto_delete(msg, delay):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except:
        pass


# =======================
# Start Command
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id)
    args = context.args

    # اگر لینک فایل بود
    if args and args[0].startswith("file_"):
        file_id = args[0].split("_")[1]
        not_joined = await check_join(user.id, context.bot)
        if not_joined:
            await update.message.reply_text(
                "❌ ابتدا عضو کانال‌ها شوید",
                reply_markup=join_buttons(not_joined)
            )
            return
        cur.execute("SELECT msg_id FROM files WHERE id=?", (file_id,))
        row = cur.fetchone()
        if row:
            msg = await context.bot.copy_message(chat_id=user.id, from_chat_id=STORAGE_CHANNEL, message_id=row[0])
            delay = get_setting("delete_time", 0)
            if delay > 0:
                asyncio.create_task(auto_delete(msg, delay))
        return

    # پنل ادمین
    if user.id == ADMIN_ID:
        kb = [["📊 آمار"], ["➕ افزودن کانال", "➖ حذف کانال"], ["⏱ تنظیم حذف خودکار"]]
        await update.message.reply_text("پنل مدیریت", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        not_joined = await check_join(user.id, context.bot)
        if not_joined:
            await update.message.reply_text("❌ لطفاً عضو کانال‌ها شوید", reply_markup=join_buttons(not_joined))
            return
        await update.message.reply_text("سلام 👋 فایل ارسال کنید.")


# =======================
# بررسی عضویت دکمه شیشه‌ای
# =======================
async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    not_joined = await check_join(user.id, context.bot)
    if not_joined:
        await query.answer("هنوز عضو نشدی ❌", show_alert=True)
    else:
        await query.answer("عضویت تایید شد ✅", show_alert=True)
        await query.message.delete()


# =======================
# پنل متن ادمین
# =======================
async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    text = update.message.text
    if text == "📊 آمار":
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        await update.message.reply_text(f"👥 کاربران: {count}")
    elif text == "➕ افزودن کانال":
        await update.message.reply_text("یوزرنیم کانال ارسال کنید:")
        context.user_data["add"] = True
    elif text == "➖ حذف کانال":
        await update.message.reply_text("یوزرنیم کانال حذف:")
        context.user_data["del"] = True
    elif text == "⏱ تنظیم حذف خودکار":
        await update.message.reply_text("زمان (ثانیه) — 0 = خاموش")
        context.user_data["time"] = True
    elif context.user_data.get("add"):
        cur.execute("INSERT INTO channels VALUES (?)", (text,))
        db.commit()
        await update.message.reply_text("✅ اضافه شد")
        context.user_data.clear()
    elif context.user_data.get("del"):
        cur.execute("DELETE FROM channels WHERE username=?", (text,))
        db.commit()
        await update.message.reply_text("✅ حذف شد")
        context.user_data.clear()
    elif context.user_data.get("time"):
        set_setting("delete_time", text)
        await update.message.reply_text("✅ تنظیم شد")
        context.user_data.clear()


# =======================
# دریافت یا فوروارد فایل توسط ادمین
# =======================
async def save_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return
    msg = update.message
    stored = await context.bot.copy_message(chat_id=STORAGE_CHANNEL, from_chat_id=msg.chat_id, message_id=msg.message_id)
    cur.execute("INSERT INTO files (msg_id) VALUES (?)", (stored.message_id,))
    db.commit()
    file_db_id = cur.lastrowid
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=file_{file_db_id}"
    await update.message.reply_text(f"✅ لینک شما:\n{link}")


# =======================
# اجرای ربات
# =======================
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(check_join_callback, pattern="check_join"))
app.add_handler(MessageHandler(filters.TEXT, admin_text))
app.add_handler(MessageHandler(filters.ALL, save_file))

app.run_polling()