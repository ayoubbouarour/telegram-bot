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
from youtubesearchpython import VideosSearch
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
# 1. SETUP & DB
# ══════════════════════════════════════════════════════════
logging.basicConfig(format="%(asctime)s | %(message)s", level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")
DB_FILE = "bot_database.json"
db = {"users": {}}

def save_db():
    with open(DB_FILE, "w") as f: json.dump(db, f)

# ══════════════════════════════════════════════════════════
# 2. RENDER KEEP-ALIVE
# ══════════════════════════════════════════════════════════
_flask = Flask(__name__)
@_flask.route("/")
def _home(): return "Mega Bot is Online!"

def run_keep_alive():
    _flask.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# ══════════════════════════════════════════════════════════
# 3. TOOL LOGIC
# ══════════════════════════════════════════════════════════

def get_media(url):
    try:
        r = requests.post("https://api.cobalt.tools", json={"url": url}, headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=10)
        return r.json().get("url")
    except: return None

def search_yt(query):
    search = VideosSearch(query, limit=3)
    results = search.result()['result']
    return "\n\n".join([f"🎬 {v['title']}\n🔗 {v['link']}" for v in results])

def get_joke():
    r = requests.get("https://official-joke-api.appspot.com/random_joke").json()
    return f"🤣 {r['setup']}\n\n✨ {r['punchline']}"

def get_quote():
    r = requests.get("https://zenquotes.io/api/random").json()
    return f"💬 \"{r[0]['q']}\"\n— {r[0]['a']}"

# ══════════════════════════════════════════════════════════
# 4. KEYBOARDS (Categorized)
# ══════════════════════════════════════════════════════════

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Media", callback_data="cat_media"), InlineKeyboardButton("🛠 Utility", callback_data="cat_util")],
        [InlineKeyboardButton("📚 Knowledge", callback_data="cat_know"), InlineKeyboardButton("🎉 Fun", callback_data="cat_fun")],
        [InlineKeyboardButton("👤 My Info", callback_data="tool_info")]
    ])

def cat_media():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📹 Downloader", callback_data="set_dl"), InlineKeyboardButton("🔍 YT Search", callback_data="set_yts")],
        [InlineKeyboardButton("◀ Back", callback_data="home")]
    ])

def cat_util():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Translate", callback_data="set_trans"), InlineKeyboardButton("🗣 TTS", callback_data="set_tts")],
        [InlineKeyboardButton("🔗 Shorten", callback_data="set_short"), InlineKeyboardButton("🔑 Password", callback_data="set_pass")],
        [InlineKeyboardButton("🔳 QR Code", callback_data="set_qr"), InlineKeyboardButton("📄 Img to PDF", callback_data="set_pdf")],
        [InlineKeyboardButton("◀ Back", callback_data="home")]
    ])

def cat_know():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Wikipedia", callback_data="set_wiki"), InlineKeyboardButton("⛅ Weather", callback_data="set_weather")],
        [InlineKeyboardButton("💱 Currency", callback_data="set_curr"), InlineKeyboardButton("⚖ Units", callback_data="set_unit")],
        [InlineKeyboardButton("◀ Back", callback_data="home")]
    ])

def cat_fun():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 AI Image", callback_data="set_ai"), InlineKeyboardButton("🤣 Joke", callback_data="tool_joke")],
        [InlineKeyboardButton("💬 Quote", callback_data="tool_quote"), InlineKeyboardButton("🔮 Horoscope", callback_data="set_horo")],
        [InlineKeyboardButton("🅰 ASCII Art", callback_data="set_ascii")],
        [InlineKeyboardButton("◀ Back", callback_data="home")]
    ])

# ══════════════════════════════════════════════════════════
# 5. HANDLERS
# ══════════════════════════════════════════════════════════

async def start(update, context):
    await update.message.reply_text("🔥 *Mega Bot v4* - 20 Tools Ready\nSelect a category:", 
                                  reply_markup=main_menu(), parse_mode="Markdown")

async def callback_handler(update, context):
    query = update.callback_query
    await query.answer()
    d = query.data

    if d == "home": await query.edit_message_text("Select a category:", reply_markup=main_menu())
    elif d == "cat_media": await query.edit_message_text("📥 *Media Tools*", reply_markup=cat_media(), parse_mode="Markdown")
    elif d == "cat_util": await query.edit_message_text("🛠 *Utility Tools*", reply_markup=cat_util(), parse_mode="Markdown")
    elif d == "cat_know": await query.edit_message_text("📚 *Knowledge Tools*", reply_markup=cat_know(), parse_mode="Markdown")
    elif d == "cat_fun": await query.edit_message_text("🎉 *Fun Tools*", reply_markup=cat_fun(), parse_mode="Markdown")

    # Simple Direct Tools
    elif d == "tool_joke": await query.message.reply_text(get_joke())
    elif d == "tool_quote": await query.message.reply_text(get_quote())
    elif d == "tool_info": 
        await query.message.reply_text(f"👤 *Your Info*\nName: {query.from_user.first_name}\nID: `{query.from_user.id}`", parse_mode="Markdown")
    
    # State-based Tools
    elif d.startswith("set_"):
        context.user_data["state"] = d.replace("set_", "")
        prompts = {
            "dl": "Paste link to download:", "yts": "What video to search?", "ai": "Describe image:",
            "wiki": "Search Wiki:", "trans": "Text to translate:", "weather": "City name:",
            "curr": "Format: 100 USD to EUR", "unit": "Format: 10 km to miles", "tts": "Text to speak:",
            "short": "Link to shorten:", "qr": "Text for QR:", "horo": "Your sign (Aries, etc):",
            "ascii": "Text for ASCII art:", "pdf": "Send photos, then /done"
        }
        await query.message.reply_text(f"👉 {prompts.get(context.user_data['state'], 'Send input:')}")

async def message_handler(update, context):
    state = context.user_data.get("state")
    text = update.message.text
    if not state: return

    try:
        if state == "dl":
            url = await asyncio.to_thread(get_media, text)
            if url: await update.message.reply_video(url)
            else: await update.message.reply_text("❌ Failed.")
        
        elif state == "yts":
            res = await asyncio.to_thread(search_yt, text)
            await update.message.reply_text(res)

        elif state == "ai":
            await update.message.reply_photo(f"https://image.pollinations.ai/prompt/{urllib.parse.quote(text)}?nologo=true")

        elif state == "qr":
            await update.message.reply_photo(f"https://api.qrserver.com/v1/create-qr-code/?data={urllib.parse.quote(text)}")

        elif state == "wiki":
            wiki = wikipediaapi.Wikipedia('MegaBot/1.0', 'en')
            p = wiki.page(text)
            await update.message.reply_text(p.summary[:500] if p.exists() else "❌ No info.")

        elif state == "weather":
            r = requests.get(f"https://wttr.in/{text}?format=3")
            await update.message.reply_text(r.text)

        elif state == "ascii":
            r = requests.get(f"http://artii.herokuapp.com/make?text={urllib.parse.quote(text)}")
            await update.message.reply_text(f"`{r.text}`", parse_mode="Markdown")

        elif state == "tts":
            gTTS(text=text, lang='en').save("s.mp3")
            await update.message.reply_voice(open("s.mp3", "rb"))
            os.remove("s.mp3")

        elif state == "trans":
            res = GoogleTranslator(source='auto', target='en').translate(text)
            await update.message.reply_text(f"🌐 {res}")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ══════════════════════════════════════════════════════════
# 6. RUN
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    Thread(target=run_keep_alive, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling(drop_pending_updates=True)
