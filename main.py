import os
import re
import time
import logging
import yt_dlp
from threading import Thread
from flask import Flask
from tinydb import TinyDB, Query
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ===== CONFIG =====
BOT_TOKEN = "7553132504:AAFbfizSUruFKvaq-jZ-Xkc7ilJWjXpwCos"
ADMIN_ID = 6663149518
CHANNEL_URL = "https://t.me/instasaverb"

USER_LIMIT = 3

db = TinyDB('db.json')
User = Query()

# ===== WEB (KEEP ALIVE) =====
web = Flask(__name__)

@web.route('/')
def home():
    return "Bot Running"

def run_web():
    web.run(host="0.0.0.0", port=8080)

logging.basicConfig(level=logging.INFO)

# ===== USER FUNCTIONS =====
def get_user(uid):
    u = db.search(User.id == uid)
    return u[0] if u else None

def create_user(uid, username):
    if not get_user(uid):
        db.insert({
            "id": uid,
            "username": username,
            "downloads": 0,
            "vip": False,
            "blocked": False,
            "utr": "",
            "date": time.ctime()
        })

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id, user.username)

    keyboard = [
        [InlineKeyboardButton("💎 Buy VIP", callback_data="buy")],
        [InlineKeyboardButton("📊 Status", callback_data="status")]
    ]

    await update.message.reply_text(
        "🔥 INSTASAVER BOT 🔥\n\n"
        "Send any link to download (Insta, YT, FB, etc)\n\n"
        "👤 Free: 3 downloads/day\n"
        "💎 VIP: Unlimited + HD",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ===== DOWNLOAD =====
async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    url = update.message.text

    if not re.match(r'http', url):
        return await update.message.reply_text("❌ Send valid link")

    user = get_user(uid)

    if user['blocked']:
        return await update.message.reply_text("🚫 You are blocked")

    if not user['vip'] and user['downloads'] >= USER_LIMIT:
        return await update.message.reply_text("❌ Limit reached. Buy VIP.")

    msg = await update.message.reply_text("⏳ Processing...")

    try:
        if not os.path.exists("downloads"):
            os.makedirs("downloads")

        fmt = "best" if user['vip'] else "best[height<=720]"
        ydl_opts = {'format': fmt, 'outtmpl': 'downloads/%(title)s.%(ext)s'}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file = ydl.prepare_filename(info)

        await msg.edit_text("📤 Uploading...")

        with open(file, "rb") as f:
            if file.endswith(('.jpg','.png','.jpeg')):
                await context.bot.send_photo(uid, f)
            else:
                await context.bot.send_video(uid, f)

        os.remove(file)

        db.update({'downloads': user['downloads'] + 1}, User.id == uid)

        if not user['vip']:
            await context.bot.send_message(uid, "💰 Ad: https://your-ad-link.com")

        await msg.delete()

    except Exception as e:
        logging.error(e)
        await msg.edit_text("❌ Failed to download")

# ===== BUY VIP =====
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    if q.data == "buy":
        await context.bot.send_photo(
            chat_id=uid,
            photo=open("qr.jpg", "rb"),
            caption="💎 Pay ₹49\n\nSend UTR number after payment"
        )

    elif q.data == "status":
        user = get_user(uid)
        await q.message.reply_text(
            f"📊 Status\nVIP: {user['vip']}\nDownloads: {user['downloads']}"
        )

# ===== UTR SYSTEM =====
async def handle_utr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    # validate UTR
    if not (text.isdigit() and 10 <= len(text) <= 20):
        return

    # check duplicate
    for u in db.all():
        if u.get("utr") == text:
            return await update.message.reply_text("❌ UTR already used")

    db.update({'utr': text}, User.id == uid)

    keyboard = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}")],
        [InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]
    ]

    await context.bot.send_message(
        ADMIN_ID,
        f"💰 Payment Request\nUser: {uid}\nUTR: {text}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text("📩 Sent for verification")

# ===== ADMIN ACTIONS =====
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if update.effective_user.id != ADMIN_ID:
        return

    if q.data.startswith("approve_"):
        uid = int(q.data.split("_")[1])
        db.update({'vip': True}, User.id == uid)

        await context.bot.send_message(uid, "🎉 VIP Activated!")
        await q.message.edit_text("✅ Approved")

    elif q.data.startswith("reject_"):
        uid = int(q.data.split("_")[1])
        db.update({'utr': ""}, User.id == uid)

        await context.bot.send_message(uid, "❌ Payment Rejected")
        await q.message.edit_text("❌ Rejected")

# ===== ADMIN COMMANDS =====
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(f"👥 Total Users: {len(db.all())}")

async def block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    db.update({'blocked': True}, User.id == uid)
    await update.message.reply_text(f"🚫 Blocked {uid}")

async def unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    db.update({'blocked': False}, User.id == uid)
    await update.message.reply_text(f"✅ Unblocked {uid}")

# ===== COMBINED HANDLER (FIXED) =====
async def combined_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # UTR
    if text.isdigit() and 10 <= len(text) <= 20:
        return await handle_utr(update, context)

    # Otherwise download
    return await handle_download(update, context)

# ===== MAIN =====
if __name__ == "__main__":
    Thread(target=run_web).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("block", block))
    app.add_handler(CommandHandler("unblock", unblock))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, combined_handler))

    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(CallbackQueryHandler(admin_callback))

    print("🔥 Instasaver Bot Running")
    app.run_polling()
