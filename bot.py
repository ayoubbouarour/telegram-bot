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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
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

# Global Database Structure
db = {"users": {}, "settings": {}}

def load_db():
    global db
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            db = json.load(f)

def save_db():
    with open(DB_FILE, "w") as f:
        json.dump(db, f)

def register_user(uid: int):
    uid_str = str(uid)
    if uid_str not in db["users"]:
        db["users"][uid_str] = {"lang": "en", "joined": time.time()}
        save_db()

# ══════════════════════════════════════════════════════════
# 2. TRANSLATIONS (Expanded)
# ══════════════════════════════════════════════════════════
TEXTS = {
    "en": {
        "main_menu": "🤖 *Super Bot v2*\nSelect a category:",
        "cat_media": "📥 *Media Downloader*",
        "cat_tools": "🛠 *Utility Tools*",
        "cat_ai": "🧠 *AI & Creative*",
        "ask_wiki": "📖 *Wikipedia*\nWhat do you want to search for?",
        "ask_trans": "🌐 *Translator*\nSend text to translate to English:",
        "ask_pass": "🔑 *Password Gen*\nClick button for a secure password.",
        "ask_ocr": "👁 *OCR*\nSend an image containing text:",
        "ask_pdf": "📄 *Image to PDF*\nSend me one or more photos, then click 'Finish'.",
        "btn_media": "Downloads 📥", "btn_tools": "Utilities 🛠", "btn_ai": "AI & Magic ✨",
        "btn_wiki": "Wikipedia 📖", "btn_trans": "Translate 🌐", "btn_pass": "Password 🔑",
        "btn_pdf": "Img to PDF 📄", "btn_ocr": "Extract Text 👁", "btn_back": "◀ Back",
        "btn_finish_pdf": "✅ Generate PDF", "error": "❌ Error occurred.",
    },
    # (Spanish, French etc can be added similarly. Defaulting to English for brevity)
}

def t(uid: int, key: str) -> str:
    lang = db["users"].get(str(uid), {}).get("lang", "en")
    return TEXTS.get(lang, TEXTS["en"]).get(key, TEXTS["en"].get(key, key))

# ══════════════════════════════════════════════════════════
# 3. KEYBOARDS
# ══════════════════════════════════════════════════════════
def main_category_keyboard(uid: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(uid, "btn_media"), callback_data="cat_media")],
        [InlineKeyboardButton(t(uid, "btn_tools"), callback_data="cat_tools")],
        [InlineKeyboardButton(t(uid, "btn_ai"), callback_data="cat_ai")],
    ])

def media_keyboard(uid: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("YouTube 🔴", callback_data="ask_yt"), InlineKeyboardButton("Instagram 📸", callback_data="ask_ig")],
        [InlineKeyboardButton("TikTok 🎵", callback_data="ask_tt"), InlineKeyboardButton("Twitter/X 🐦", callback_data="ask_tw")],
        [InlineKeyboardButton(t(uid, "btn_back"), callback_data="show_main")]
    ])

def tools_keyboard(uid: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(uid, "btn_wiki"), callback_data="ask_wiki"), InlineKeyboardButton(t(uid, "btn_trans"), callback_data="ask_trans")],
        [InlineKeyboardButton(t(uid, "btn_pass"), callback_data="ask_pass"), InlineKeyboardButton(t(uid, "btn_pdf"), callback_data="ask_pdf")],
        [InlineKeyboardButton(t(uid, "btn_ocr"), callback_data="ask_ocr"), InlineKeyboardButton("Weather ⛅", callback_data="ask_weather")],
        [InlineKeyboardButton(t(uid, "btn_back"), callback_data="show_main")]
    ])

# ══════════════════════════════════════════════════════════
# 4. TOOL LOGIC (NEW TOOLS)
# ══════════════════════════════════════════════════════════

def fetch_wiki(query: str):
    wiki = wikipediaapi.Wikipedia('SuperBot/1.0 (contact@example.com)', 'en')
    page = wiki.page(query)
    if page.exists():
        return f"📚 *{page.title}*\n\n{page.summary[:800]}..."
    return "❌ Topic not found."

def generate_password(length=16):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(chars) for _ in range(length))

async def run_ocr(photo_path: str):
    # Using a free public OCR API (OCR.Space)
    # Get a free key at https://ocr.space/ocrapi
    api_key = "helloworld" 
    payload = {
        'apikey': api_key,
        'language': 'eng',
    }
    with open(photo_path, 'rb') as f:
        r = requests.post('https://api.ocr.space/parse/image', files={'image': f}, data=payload)
    
    result = r.json()
    if result.get("OCRExitCode") == 1:
        return result["ParsedResults"][0]["ParsedText"]
    return "❌ Could not read text."

# ══════════════════════════════════════════════════════════
# 5. HANDLERS
# ══════════════════════════════════════════════════════════

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    register_user(uid)
    await update.message.reply_text(t(uid, "main_menu"), reply_markup=main_category_keyboard(uid), parse_mode="Markdown")

async def handle_media_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = context.user_data.get("state")

    # Image to PDF Collector
    if state == "waiting_for_pdf":
        if update.message.photo:
            photo_file = await update.message.photo[-1].get_file()
            f_path = f"pdf_{uid}_{len(context.user_data.get('pdf_files', []))}.jpg"
            await photo_file.download_to_drive(f_path)
            
            if "pdf_files" not in context.user_data: context.user_data["pdf_files"] = []
            context.user_data["pdf_files"].append(f_path)
            
            await update.message.reply_text(f"📸 Image {len(context.user_data['pdf_files'])} added. Send more or click 'Finish'.", 
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(uid, "btn_finish_pdf"), callback_data="finish_pdf")]]))
        return

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    state = context.user_data.get("state")

    if state == "waiting_for_wiki":
        res = await asyncio.to_thread(fetch_wiki, text)
        await update.message.reply_text(res, parse_mode="Markdown")
        context.user_data["state"] = None
    
    elif state == "waiting_for_trans":
        translated = GoogleTranslator(source='auto', target='en').translate(text)
        await update.message.reply_text(f"🌐 *Translated:* \n\n{translated}", parse_mode="Markdown")
        context.user_data["state"] = None

    # Redirect to Main Menu
    if not state:
        await update.message.reply_text("Back to menu:", reply_markup=main_category_keyboard(uid))

async def callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    data = query.data
    await query.answer()

    if data == "show_main":
        await query.edit_message_text(t(uid, "main_menu"), reply_markup=main_category_keyboard(uid), parse_mode="Markdown")
    
    elif data == "cat_media":
        await query.edit_message_text(t(uid, "cat_media"), reply_markup=media_keyboard(uid), parse_mode="Markdown")
    
    elif data == "cat_tools":
        await query.edit_message_text(t(uid, "cat_tools"), reply_markup=tools_keyboard(uid), parse_mode="Markdown")

    elif data == "ask_wiki":
        context.user_data["state"] = "waiting_for_wiki"
        await query.edit_message_text(t(uid, "ask_wiki"))

    elif data == "ask_trans":
        context.user_data["state"] = "waiting_for_trans"
        await query.edit_message_text(t(uid, "ask_trans"))

    elif data == "ask_pass":
        pw = generate_password()
        await query.message.reply_text(f"🔑 *Your Secure Password:* `{pw}`", parse_mode="Markdown")

    elif data == "ask_pdf":
        context.user_data["state"] = "waiting_for_pdf"
        context.user_data["pdf_files"] = []
        await query.edit_message_text(t(uid, "ask_pdf"))

    elif data == "finish_pdf":
        files = context.user_data.get("pdf_files", [])
        if not files: return
        pdf_path = f"converted_{uid}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(files))
        await context.bot.send_document(chat_id=uid, document=open(pdf_path, "rb"), filename="SmartBot_Compiled.pdf")
        # Cleanup
        for f in files: os.remove(f)
        os.remove(pdf_path)
        context.user_data["state"] = None

# ══════════════════════════════════════════════════════════
# 6. MAIN LOOP
# ══════════════════════════════════════════════════════════
def main():
    load_db()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_media_upload))

    print("Bot is flying...")
    app.run_polling()

if __name__ == "__main__":
    main()
