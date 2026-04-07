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

# --- CONFIGURATION ---
BOT_TOKEN = "7553132504:AAFbfizSUruFKvaq-jZ-Xkc7ilJWjXpwCos"
ADMIN_ID = 6663149518
CHANNEL_ID = -1003785644571
CHANNEL_URL = "https://t.me/instasaverb"

# Database
db = TinyDB('users_db.json')
User = Query()

# --- WEB SERVER (For 24/7) ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "INSTASAVER Downloader is Online!"
def run_web(): web_app.run(host="0.0.0.0", port=8080)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- UTILS ---
async def is_subscribed(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

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
        keyboard = [[InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL)],
                    [InlineKeyboardButton("🔄 Verify Join", callback_data="verify")]]
        return await update.message.reply_text(
            f"👋 **Hi {user.first_name}!**\n\n⚠️ **ACCESS LOCKED**\n\nIs bot ko use karne ke liye hamara VIP channel join karein.",
            reply_markup=InlineKeyboardMarkup(keyboard))

    await update.message.reply_text(
        "🔥 **INSTASAVER ALL-IN-ONE DOWNLOADER** 🔥\n\n"
        "Bhai, kisi bhi video ka link paste karo:\n"
        "✅ **Instagram Reels**\n"
        "✅ **YouTube Shorts / Video**\n"
        "✅ **TikTok / Facebook / Twitter**\n\n"
        "⚡ *Bas link bhej aur magic dekh!*",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📊 My Profile", callback_data="stats")]])
    )

# --- ADMIN FEATURE ---
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    total_users = len(db.all())
    await update.message.reply_text(
        f"👑 **ADMIN DASHBOARD**\n\n"
        f"👥 Total Users: `{total_users}`\n"
        f"🤖 Status: `Running Smooth`",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Broadcast", callback_data="bc_msg")]])
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: return await update.message.reply_text("Format: `/broadcast Hello Users`")
    
    msg = " ".join(context.args)
    users = db.all()
    sent = 0
    for u in users:
        try:
            await context.bot.send_message(u['id'], f"📢 **ANNOUNCEMENT**\n\n{msg}")
            sent += 1
        except: pass
    await update.message.reply_text(f"✅ Success: {sent} users.")

# --- DOWNLOAD LOGIC ---
async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_subscribed(user_id, context): return await start(update, context)

    url = update.message.text
    if not re.match(r'http', url): return
    
    status_msg = await update.message.reply_text("⏳ **Processing... Please wait.**")
    
    try:
        # Create directory if not exists
        if not os.path.exists('downloads'): os.makedirs('downloads')
        
        file_path = download_video(url)
        await status_msg.edit_text("📤 **Uploading to Telegram...**")
        
        with open(file_path, 'rb') as video:
            await context.bot.send_video(
                chat_id=user_id, 
                video=video, 
                caption=f"✅ **Downloaded by @SepaxYt_Bot**\n\n🔥 Join: {CHANNEL_URL}"
            )
        
        os.remove(file_path) # Clean up
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Error: {e}")
        await status_msg.edit_text("❌ **Sorry!** Video download nahi ho payi. Link check karein ya dusra try karein.")

# --- CALLBACKS ---
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "verify":
        if await is_subscribed(query.from_user.id, context):
            await query.message.edit_text("✅ **Verification Success!** Ab link bhejo.")
        else:
            await query.answer("❌ Abhi tak join nahi kiya!", show_alert=True)
            
    elif query.data == "stats":
        u = db.search(User.id == query.from_user.id)[0]
        await query.message.reply_text(f"👤 **User:** {query.from_user.first_name}\n📅 **Joined:** {u['date']}")

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_web).start()
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_download))
    app.add_handler(CallbackQueryHandler(callbacks))
    
    print("SepaxYt Downloader Started!")
    app.run_polling()
