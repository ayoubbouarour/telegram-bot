import os
import re
import json
import time
import asyncio
import logging
import secrets
import string
import urllib.parse
from threading import Thread

import requests
import img2pdf
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
DB_FILE = "bot_database.json"

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

# ══════════════════════════════════════════════════════════
# 2. RENDER KEEP-ALIVE (Critical for Render.com)
# ══════════════════════════════════════════════════════════
_flask = Flask(__name__)
@_flask.route("/")
def _home(): return "Bot is Online and Functional!"

def run_keep_alive():
    port = int(os.environ.get("PORT", 8080))
    _flask.run(host="0.0.0.0", port=port)

# ══════════════════════════════════════════════════════════
# 3. TOOL LOGIC FUNCTIONS
# ══════════════════════════════════════════════════════════

# TOOL 1: Media Downloader (Cobalt)
def get_media(url):
    instances = ["https://api.cobalt.tools", "https://cobalt.canine.tools", "https://api.cobalt.bkc.icu"]
    for base in instances:
        try:
            r = requests.post(base, json={"url": url, "videoQuality": "720"}, 
                             headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=10)
            if r.status_code == 200: return r.json().get("url")
        except: continue
    return None

# TOOL 2: Wikipedia Search
def search_wiki(query):
    wiki = wikipediaapi.Wikipedia('SuperBot/1.0 (contact@example.com)', 'en')
    page = wiki.page(query)
    return f"📚 *{page.title}*\n\n{page.summary[:600]}..." if page.exists() else "❌ Not found."

# TOOL 3: Weather
def get_weather(city):
    try:
        r = requests.get(f"https://wttr.in/{city}?format=%C+%t+%w", timeout=5)
        return f"⛅ Weather in {city.capitalize()}: {r.text}"
    except: return "❌ Weather service unavailable."

# TOOL 4: Currency Converter
def convert_curr(amount, fr, to):
    try:
        r = requests.get(f"https://open.er-api.com/v6/latest/{fr.upper()}")
        rate = r.json()["rates"][to.upper()]
        return f"💱 {amount} {fr.upper()} = {round(amount * rate, 2)} {to.upper()}"
    except: return "❌ Invalid currency codes."

# ══════════════════════════════════════════════════════════
# 4. KEYBOARDS
# ══════════════════════════════════════════════════════════
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Downloader", callback_data="set_dl"), InlineKeyboardButton("🎨 AI Image", callback_data="set_ai")],
        [InlineKeyboardButton("📖 Wikipedia", callback_data="set_wiki"), InlineKeyboardButton("🌐 Translate", callback_data="set_trans")],
        [InlineKeyboardButton("⛅ Weather", callback_data="set_weather"), InlineKeyboardButton("💱 Currency", callback_data="set_curr")],
        [InlineKeyboardButton("🗣️ Text-to-Speech", callback_data="set_tts"), InlineKeyboardButton("🔗 Shorten URL", callback_data="set_short")],
        [InlineKeyboardButton("📄 Img to PDF", callback_data="set_pdf"), InlineKeyboardButton("🔑 Password", callback_data="set_pass")]
    ])

def back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀ Back to Menu", callback_data="home")]])

# ══════════════════════════════════════════════════════════
# 5. HANDLERS
# ══════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in db["users"]:
        db["users"][uid] = {"joined": time.time()}
        save_db()
    await update.message.reply_text("🚀 *Super Bot v3 - 10 Tools Loaded*\nChoose a tool below:", 
                                  reply_markup=main_menu(), parse_mode="Markdown")

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "home":
        context.user_data["state"] = None
        await query.edit_message_text("Choose a tool below:", reply_markup=main_menu())
    
    elif data == "set_dl": 
        context.user_data["state"] = "dl"
        await query.edit_message_text("📥 *Downloader*\nPaste any link (YouTube, TikTok, IG, FB):", parse_mode="Markdown", reply_markup=back_btn())
    
    elif data == "set_ai":
        context.user_data["state"] = "ai"
        await query.edit_message_text("🎨 *AI Image Generator*\nDescribe the image you want to create:", parse_mode="Markdown", reply_markup=back_btn())

    elif data == "set_wiki":
        context.user_data["state"] = "wiki"
        await query.edit_message_text("📖 *Wikipedia*\nWhat do you want to search for?", parse_mode="Markdown", reply_markup=back_btn())

    elif data == "set_trans":
        context.user_data["state"] = "trans"
        await query.edit_message_text("🌐 *Translator*\nSend text to translate to English:", parse_mode="Markdown", reply_markup=back_btn())

    elif data == "set_weather":
        context.user_data["state"] = "weather"
        await query.edit_message_text("⛅ *Weather*\nSend a city name (e.g., London):", parse_mode="Markdown", reply_markup=back_btn())

    elif data == "set_curr":
        context.user_data["state"] = "curr"
        await query.edit_message_text("💱 *Currency*\nFormat: `100 USD to EUR`", parse_mode="Markdown", reply_markup=back_btn())

    elif data == "set_tts":
        context.user_data["state"] = "tts"
        await query.edit_message_text("🗣️ *Text to Speech*\nSend text to convert to voice:", parse_mode="Markdown", reply_markup=back_btn())

    elif data == "set_short":
        context.user_data["state"] = "short"
        await query.edit_message_text("🔗 *URL Shortener*\nPaste your long link:", parse_mode="Markdown", reply_markup=back_btn())

    elif data == "set_pdf":
        context.user_data["state"] = "pdf"
        context.user_data["pdf_files"] = []
        await query.edit_message_text("📄 *Image to PDF*\nSend images one by one. When finished, type /done", parse_mode="Markdown", reply_markup=back_btn())

    elif data == "set_pass":
        pw = "".join(secrets.choice(string.ascii_letters + string.digits + "@#") for _ in range(16))
        await query.message.reply_text(f"🔑 *Secure Password:* `{pw}`", parse_mode="Markdown", reply_markup=back_btn())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    text = update.message.text
    uid = update.effective_user.id

    if not state: return

    # TOOL 1: Downloader logic
    if state == "dl":
        m = await update.message.reply_text("Downloading... ⏳")
        file_url = await asyncio.to_thread(get_media, text)
        if file_url:
            await update.message.reply_video(file_url)
            await m.delete()
        else: await m.edit_text("❌ Failed. Ensure the link is public.")

    # TOOL 2: AI Image
    elif state == "ai":
        m = await update.message.reply_text("Generating... 🎨")
        prompt = urllib.parse.quote(text)
        img_url = f"https://image.pollinations.ai/prompt/{prompt}?width=1024&height=1024&nologo=true"
        await update.message.reply_photo(img_url, caption=f"🎨: {text}")
        await m.delete()

    # TOOL 3: Wikipedia
    elif state == "wiki":
        res = await asyncio.to_thread(search_wiki, text)
        await update.message.reply_text(res, parse_mode="Markdown")

    # TOOL 4: Weather
    elif state == "weather":
        res = await asyncio.to_thread(get_weather, text)
        await update.message.reply_text(res)

    # TOOL 5: Translator
    elif state == "trans":
        res = GoogleTranslator(source='auto', target='en').translate(text)
        await update.message.reply_text(f"🌐 *Translated:* \n`{res}`", parse_mode="Markdown")

    # TOOL 6: Currency
    elif state == "curr":
        try:
            parts = text.split()
            res = convert_curr(float(parts[0]), parts[1], parts[4])
            await update.message.reply_text(res)
        except: await update.message.reply_text("❌ Format: `100 USD to EUR`")

    # TOOL 7: TTS
    elif state == "tts":
        tts = gTTS(text=text, lang='en')
        tts.save(f"{uid}.mp3")
        await update.message.reply_voice(open(f"{uid}.mp3", "rb"))
        os.remove(f"{uid}.mp3")

    # TOOL 8: Shortener
    elif state == "short":
        r = requests.get(f"http://tinyurl.com/api-create.php?url={text}")
        await update.message.reply_text(f"🔗 *Shortened:* {r.text}", parse_mode="Markdown")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") == "pdf":
        file = await update.message.photo[-1].get_file()
        path = f"img_{update.effective_user.id}_{len(context.user_data['pdf_files'])}.jpg"
        await file.download_to_drive(path)
        context.user_data["pdf_files"].append(path)
        await update.message.reply_text(f"📸 Image {len(context.user_data['pdf_files'])} added. Send more or type /done")

async def done_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    files = context.user_data.get("pdf_files", [])
    if not files: return
    out = f"Result_{update.effective_user.id}.pdf"
    with open(out, "wb") as f:
        f.write(img2pdf.convert(files))
    await update.message.reply_document(open(out, "rb"))
    for f in files: os.remove(f)
    os.remove(out)
    context.user_data["state"] = None

# ══════════════════════════════════════════════════════════
# 6. RUN BOT
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    load_db()
    Thread(target=run_keep_alive, daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("done", done_pdf))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("Bot is active!")
    # drop_pending_updates=True prevents the Conflict error
    app.run_polling(drop_pending_updates=True)
