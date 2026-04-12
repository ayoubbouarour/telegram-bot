import os
import json
import time
import asyncio
import logging
import urllib.parse
import secrets
import string
from threading import Thread

import requests
import pyfiglet
import img2pdf
from flask import Flask
from gtts import gTTS
from deep_translator import GoogleTranslator
import wikipediaapi
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ══════════════════════════════════════════════════════════
# 1. LOGGING & CONFIG
# ══════════════════════════════════════════════════════════
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN")

# Flask for Render.com
app_web = Flask(__name__)
@app_web.route('/')
def index(): return "Super Bot is Active!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port)

# ══════════════════════════════════════════════════════════
# 2. MENU SYSTEMS
# ══════════════════════════════════════════════════════════

def main_menu():
    keys = [
        [InlineKeyboardButton("📥 Media & DL", callback_data="cat_media"), InlineKeyboardButton("🎨 AI & Design", callback_data="cat_design")],
        [InlineKeyboardButton("🛠 Utilities", callback_data="cat_util"), InlineKeyboardButton("📚 Knowledge", callback_data="cat_know")],
        [InlineKeyboardButton("💰 Money/Crypto", callback_data="cat_fin"), InlineKeyboardButton("🎉 Fun Zone", callback_data="cat_fun")]
    ]
    return InlineKeyboardMarkup(keys)

def sub_menu(category):
    menus = {
        "media": [["📹 Downloader", "dl"], ["🎬 YT Search", "yts"]],
        "design": [["🎨 AI Image", "ai"], ["🔳 QR Code", "qr"], ["🅰 ASCII Art", "ascii"]],
        "util": [["📄 Img to PDF", "pdf"], ["🔗 Shorten URL", "short"], ["🔑 Password", "pass"], ["🗣 TTS Voice", "tts"]],
        "know": [["📖 Wikipedia", "wiki"], ["🌐 Translate", "trans"], ["⛅ Weather", "weather"], ["🧮 Calculator", "calc"]],
        "fin": [["₿ Crypto", "crypto"], ["💱 Currency", "curr"]],
        "fun": [["🤣 Joke", "joke"], ["💬 Quote", "quote"], ["🔮 8-Ball", "ball"], ["🎲 Dice", "dice"]]
    }
    buttons = [[InlineKeyboardButton(i[0], callback_data=f"set_{i[1]}")] for i in menus.get(category, [])]
    buttons.append([InlineKeyboardButton("◀ Back", callback_data="home")])
    return InlineKeyboardMarkup(buttons)

# ══════════════════════════════════════════════════════════
# 3. TOOL HANDLERS
# ══════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear() # Reset everything
    await update.message.reply_text("👑 *SUPER BOT v5 ACTIVATED*\nSelect a category to begin:", 
                                  reply_markup=main_menu(), parse_mode="Markdown")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "home":
        await query.edit_message_text("Select a category:", reply_markup=main_menu())
    elif data.startswith("cat_"):
        await query.edit_message_text(f"🛠 *{data[4:].upper()} TOOLS*", reply_markup=sub_menu(data[4:]), parse_mode="Markdown")
    elif data.startswith("set_"):
        state = data.replace("set_", "")
        context.user_data["state"] = state
        
        # Immediate tools
        if state == "pass":
            pw = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
            await query.message.reply_text(f"🔑 *New Password:* `{pw}`", parse_mode="Markdown")
        elif state == "joke":
            r = requests.get("https://official-joke-api.appspot.com/random_joke").json()
            await query.message.reply_text(f"{r['setup']}\n\n{r['punchline']}")
        elif state == "dice":
            await query.message.reply_dice()
        elif state == "pdf":
            context.user_data["pdf_files"] = []
            await query.message.reply_text("📄 Send photos one by one. When finished, type /done")
        else:
            await query.message.reply_text(f"👉 Send input for {state.upper()}:")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    text = update.message.text
    uid = update.effective_user.id

    if not state: return

    try:
        # 1. Media Downloader
        if state == "dl":
            m = await update.message.reply_text("Downloading... ⏳")
            r = requests.post("https://api.cobalt.tools", json={"url": text}, headers={"Accept": "application/json", "Content-Type": "application/json"})
            if r.json().get("url"): await update.message.reply_video(r.json().get("url"))
            else: await m.edit_text("❌ Link Error.")
        
        # 2. QR Code Maker
        elif state == "qr":
            url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(text)}"
            await update.message.reply_photo(url, caption="✅ Your QR Code")

        # 3. AI Image
        elif state == "ai":
            await update.message.reply_photo(f"https://image.pollinations.ai/prompt/{urllib.parse.quote(text)}?nologo=true")

        # 4. ASCII Art
        elif state == "ascii":
            await update.message.reply_text(f"`{pyfiglet.figlet_format(text)}`", parse_mode="Markdown")

        # 5. Translator
        elif state == "trans":
            res = GoogleTranslator(source='auto', target='en').translate(text)
            await update.message.reply_text(f"🌐 English: {res}")

        # 6. Wikipedia
        elif state == "wiki":
            wiki = wikipediaapi.Wikipedia(user_agent='Bot/1.0', language='en')
            p = wiki.page(text)
            await update.message.reply_text(p.summary[:600] if p.exists() else "Not found.")

        # 7. Weather
        elif state == "weather":
            r = requests.get(f"https://wttr.in/{text}?format=3")
            await update.message.reply_text(r.text)

        # 8. TTS Voice
        elif state == "tts":
            gTTS(text=text, lang='en').save(f"{uid}.mp3")
            await update.message.reply_voice(open(f"{uid}.mp3", "rb"))
            os.remove(f"{uid}.mp3")

        # 9. Shorten URL
        elif state == "short":
            r = requests.get(f"http://tinyurl.com/api-create.php?url={text}")
            await update.message.reply_text(f"🔗 {r.text}")

        # 10. Crypto
        elif state == "crypto":
            r = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={text.lower()}&vs_currencies=usd").json()
            price = r.get(text.lower(), {}).get('usd', 'N/A')
            await update.message.reply_text(f"💰 {text.upper()}: ${price}")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") == "pdf":
        file = await update.message.photo[-1].get_file()
        path = f"/tmp/img_{len(context.user_data['pdf_files'])}.jpg"
        await file.download_to_drive(path)
        context.user_data["pdf_files"].append(path)
        await update.message.reply_text(f"✅ Image {len(context.user_data['pdf_files'])} saved. Type /done to finish.")

async def done_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    files = context.user_data.get("pdf_files", [])
    if not files: return
    out = "/tmp/result.pdf"
    with open(out, "wb") as f: f.write(img2pdf.convert(files))
    await update.message.reply_document(open(out, "rb"), filename="SmartBot.pdf")
    for f in files: os.remove(f)
    context.user_data["state"] = None

# ══════════════════════════════════════════════════════════
# 4. STARTUP
# ══════════════════════════════════════════════════════════
if __name__ == '__main__':
    Thread(target=run_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("done", done_pdf))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("Super Bot Running...")
    app.run_polling(drop_pending_updates=True)
