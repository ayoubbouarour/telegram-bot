import os
import re
import json
import glob
import time
import asyncio
import logging
import urllib.parse
import secrets
import string
from threading import Thread
from collections import defaultdict

import requests
import img2pdf
from PIL import Image
from flask import Flask
from gtts import gTTS
from deep_translator import GoogleTranslator
import wikipediaapi
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ══════════════════════════════════════════════════════════
# 1. CONFIG & LOGGING
# ══════════════════════════════════════════════════════════
logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()}
DB_FILE = "bot_database.json"
MAX_FILE_MB = 50

db = {"users": {}}

def load_db():
    global db
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                db = json.load(f)
        except: pass

def save_db():
    with open(DB_FILE, "w") as f:
        json.dump(db, f)

def register_user(uid: int):
    uid_str = str(uid)
    if uid_str not in db["users"]:
        db["users"][uid_str] = {"lang": "en", "joined": time.time()}
        save_db()

# ══════════════════════════════════════════════════════════
# 2. RENDER KEEP-ALIVE (Fixes "Port" errors)
# ══════════════════════════════════════════════════════════
_flask = Flask(__name__)
@_flask.route("/")
def _home(): return "Bot is Alive!"

def run_keep_alive():
    port = int(os.environ.get("PORT", 8080))
    _flask.run(host="0.0.0.0", port=port)

# ══════════════════════════════════════════════════════════
# 3. COBALT DOWNLOADER ENGINE
# ══════════════════════════════════════════════════════════
def get_cobalt_url(url: str, audio_only: bool = False):
    instances = ["https://api.cobalt.tools", "https://co.wuk.sh"]
    payload = {
        "url": url,
        "videoQuality": "720",
        "audioFormat": "mp3",
        "downloadMode": "audio" if audio_only else "auto"
    }
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    for base in instances:
        try:
            r = requests.post(base, json=payload, headers=headers, timeout=15)
            if r.status_code == 200:
                return r.json().get("url")
        except: continue
    return None

# ══════════════════════════════════════════════════════════
# 4. KEYBOARDS
# ══════════════════════════════════════════════════════════
def main_menu(uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Media Downloader 📥", callback_data="cat_media")],
        [InlineKeyboardButton("Utility Tools 🛠", callback_data="cat_tools")],
        [InlineKeyboardButton("AI & Magic ✨", callback_data="cat_ai")]
    ])

def media_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("YouTube 🔴", callback_data="ask_dl"), InlineKeyboardButton("Instagram 📸", callback_data="ask_dl")],
        [InlineKeyboardButton("TikTok 🎵", callback_data="ask_dl"), InlineKeyboardButton("Twitter/X 🐦", callback_data="ask_dl")],
        [InlineKeyboardButton("◀ Back", callback_data="show_main")]
    ])

def tools_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Wikipedia 📖", callback_data="ask_wiki"), InlineKeyboardButton("Translate 🌐", callback_data="ask_trans")],
        [InlineKeyboardButton("Password 🔑", callback_data="ask_pass"), InlineKeyboardButton("Img to PDF 📄", callback_data="ask_pdf")],
        [InlineKeyboardButton("Extract Text 👁", callback_data="ask_ocr"), InlineKeyboardButton("Weather ⛅", callback_data="ask_weather")],
        [InlineKeyboardButton("◀ Back", callback_data="show_main")]
    ])

# ══════════════════════════════════════════════════════════
# 5. HANDLERS
# ══════════════════════════════════════════════════════════
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    register_user(uid)
    await update.message.reply_text("🤖 *Super Bot v2*\nSelect a category:", reply_markup=main_menu(uid), parse_mode="Markdown")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    data = query.data
    await query.answer()

    if data == "show_main":
        await query.edit_message_text("Select category:", reply_markup=main_menu(uid))
    elif data == "cat_media":
        await query.edit_message_text("📥 *Media Downloader*\nSelect platform or paste link:", reply_markup=media_menu(), parse_mode="Markdown")
    elif data == "cat_tools":
        await query.edit_message_text("🛠 *Utilities*", reply_markup=tools_menu(), parse_mode="Markdown")
    
    elif data == "ask_dl":
        context.user_data["state"] = "waiting_for_link"
        await query.message.reply_text("🔗 Paste your link (YouTube, IG, TikTok, etc):")
    
    elif data == "ask_wiki":
        context.user_data["state"] = "waiting_for_wiki"
        await query.message.reply_text("📖 What do you want to search on Wikipedia?")

    elif data == "ask_pass":
        pw = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        await query.message.reply_text(f"🔑 *Generated Password:* `{pw}`", parse_mode="Markdown")

    elif data == "ask_pdf":
        context.user_data["state"] = "waiting_for_pdf"
        context.user_data["pdf_files"] = []
        await query.message.reply_text("📄 Send me photos one by one. When done, click /done_pdf")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    state = context.user_data.get("state")

    if state == "waiting_for_link":
        msg = await update.message.reply_text("Processing link... ⏳")
        dl_url = await asyncio.to_thread(get_cobalt_url, text)
        if dl_url:
            await update.message.reply_video(dl_url, caption="✅ Success!")
            await msg.delete()
        else:
            await msg.edit_text("❌ Could not process link.")
        context.user_data["state"] = None

    elif state == "waiting_for_wiki":
        wiki = wikipediaapi.Wikipedia('SuperBot/1.0', 'en')
        page = wiki.page(text)
        if page.exists():
            await update.message.reply_text(f"📚 *{page.title}*\n\n{page.summary[:500]}...", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Not found.")
        context.user_data["state"] = None

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if context.user_data.get("state") == "waiting_for_pdf" and update.message.photo:
        file = await update.message.photo[-1].get_file()
        path = f"tmp_{uid}_{len(context.user_data['pdf_files'])}.jpg"
        await file.download_to_drive(path)
        context.user_data["pdf_files"].append(path)
        await update.message.reply_text(f"✅ Added image {len(context.user_data['pdf_files'])}. Type /done_pdf to finish.")

async def done_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    files = context.user_data.get("pdf_files", [])
    if not files: return
    out = f"result_{update.effective_user.id}.pdf"
    with open(out, "wb") as f:
        f.write(img2pdf.convert(files))
    await update.message.reply_document(open(out, "rb"))
    for f in files: os.remove(f)
    os.remove(out)
    context.user_data["state"] = None

# ══════════════════════════════════════════════════════════
# 6. MAIN EXECUTION
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    load_db()
    # Run Flask in background for Render
    Thread(target=run_keep_alive, daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("done_pdf", done_pdf))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_docs))

    print("Bot is starting...")
    # drop_pending_updates=True is the FIX for the Conflict Error
    app.run_polling(drop_pending_updates=True)
