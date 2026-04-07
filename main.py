import os
import re
import time
import logging
import yt_dlp
import asyncio
from threading import Thread
from flask import Flask
from tinydb import TinyDB, Query
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6663149518
CHANNEL_ID = -1003785644571
CHANNEL_URL = "https://t.me/instasaverb"

# --- DB ---
db = TinyDB('users_db.json')
User = Query()

# --- WEB SERVER (Render needs this) ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "✅ INSTASAVER BOT RUNNING!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)

# --- UTILS ---
async def is_subscribed(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def download_video(url):
    ydl_opts = {
        'format': 'best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not db.search(User.id == user.id):
        db.insert({'id': user.id, 'username': user.username, 'date': time.ctime()})

    if not await is_subscribed(user.id, context):
        keyboard = [
            [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL)],
            [InlineKeyboardButton("🔄 Verify", callback_data="verify")]
        ]
        return await update.message.reply_text(
            f"👋 Hi {user.first_name}!\n\n⚠️ Join channel first to use bot.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    await update.message.reply_text(
        "🔥 Send any video link:\n\n"
        "✅ Instagram\n✅ YouTube\n✅ TikTok\n✅ Facebook\n\n"
        "⚡ Just paste link!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Profile", callback_data="stats")]
        ])
    )

# --- ADMIN ---
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    total = len(db.all())

    await update.message.reply_text(
        f"👑 ADMIN PANEL\n\n👥 Users: {total}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Broadcast", callback_data="bc")]
        ])
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        return await update.message.reply_text("Use: /broadcast message")

    msg = " ".join(context.args)
    users = db.all()
    sent = 0

    for u in users:
        try:
            await context.bot.send_message(u['id'], f"📢 {msg}")
            sent += 1
        except:
            pass

    await update.message.reply_text(f"✅ Sent to {sent} users")

# --- DOWNLOAD ---
async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await is_subscribed(user_id, context):
        return await start(update, context)

    url = update.message.text

    if not re.match(r'https?://', url):
        return

    msg = await update.message.reply_text("⏳ Processing...")

    try:
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        file_path = download_video(url)

        await msg.edit_text("📤 Uploading...")

        with open(file_path, 'rb') as video:
            await context.bot.send_video(
                chat_id=user_id,
                video=video,
                caption=f"✅ Downloaded\n\nJoin: {CHANNEL_URL}"
            )

        os.remove(file_path)
        await msg.delete()

    except Exception as e:
        logging.error(e)
        await msg.edit_text("❌ Failed. Try another link.")

# --- CALLBACK ---
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "verify":
        if await is_subscribed(query.from_user.id, context):
            await query.message.edit_text("✅ Verified! Send link.")
        else:
            await query.answer("❌ Join channel first!", show_alert=True)

    elif query.data == "stats":
        u = db.search(User.id == query.from_user.id)[0]
        await query.message.reply_text(
            f"👤 {query.from_user.first_name}\n📅 {u['date']}"
        )

# --- MAIN ---
if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())

    Thread(target=run_web).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_download))
    app.add_handler(CallbackQueryHandler(callbacks))

    print("🚀 Bot Running on Render")
    app.run_polling()
