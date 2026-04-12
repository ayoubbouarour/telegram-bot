import os
import json
import time
import asyncio
import logging
import urllib.parse
from threading import Thread

import requests
import pyfiglet
from flask import Flask
from gtts import gTTS
from deep_translator import GoogleTranslator
import wikipediaapi
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# 1. LOGGING (Check Render logs to see what happens)
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. CONFIG
TOKEN = os.environ.get("BOT_TOKEN")

# 3. RENDER WEB SERVER (Crucial for Render.com)
app_web = Flask(__name__)
@app_web.route('/')
def index(): return "Bot is running..."

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port)

# 4. KEYBOARDS
def main_menu():
    keyboard = [
        [InlineKeyboardButton("📹 Downloader", callback_data="set_dl"), InlineKeyboardButton("🎨 AI Image", callback_data="set_ai")],
        [InlineKeyboardButton("🌐 Translate", callback_data="set_tr"), InlineKeyboardButton("📖 Wikipedia", callback_data="set_wk")],
        [InlineKeyboardButton("⛅ Weather", callback_data="set_wt"), InlineKeyboardButton("🅰 ASCII Art", callback_data="set_as")],
        [InlineKeyboardButton("🎲 Dice", callback_data="do_dice"), InlineKeyboardButton("🤣 Joke", callback_data="do_joke")]
    ]
    return InlineKeyboardMarkup(keyboard)

# 5. HANDLERS
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = None # Clear any stuck state
    await update.message.reply_text("🔥 *Super Bot Started!*\nSelect a tool:", 
                                  reply_markup=main_menu(), parse_mode="Markdown")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("set_"):
        state = data.replace("set_", "")
        context.user_data["state"] = state
        await query.message.reply_text(f"👉 Send input for {state.upper()}:")
    
    elif data == "do_dice":
        await query.message.reply_dice()
    
    elif data == "do_joke":
        res = requests.get("https://official-joke-api.appspot.com/random_joke").json()
        await query.message.reply_text(f"{res['setup']}\n\n{res['punchline']}")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    text = update.message.text
    
    if not state:
        await update.message.reply_text("Please select a tool first:", reply_markup=main_menu())
        return

    # Tool Logic
    try:
        if state == "dl":
            m = await update.message.reply_text("Downloading... ⏳")
            r = requests.post("https://api.cobalt.tools", json={"url": text}, headers={"Accept": "application/json", "Content-Type": "application/json"})
            url = r.json().get("url")
            if url: await update.message.reply_video(url)
            else: await m.edit_text("❌ Link Error.")
            
        elif state == "ai":
            await update.message.reply_photo(f"https://image.pollinations.ai/prompt/{urllib.parse.quote(text)}?nologo=true")

        elif state == "tr":
            res = GoogleTranslator(source='auto', target='en').translate(text)
            await update.message.reply_text(f"🌐 English: {res}")

        elif state == "wk":
            wiki = wikipediaapi.Wikipedia(user_agent='MyBot/1.0', language='en')
            page = wiki.page(text)
            await update.message.reply_text(page.summary[:500] if page.exists() else "Not found.")

        elif state == "as":
            art = pyfiglet.figlet_format(text)
            await update.message.reply_text(f"`{art}`", parse_mode="Markdown")

        elif state == "wt":
            r = requests.get(f"https://wttr.in/{text}?format=3")
            await update.message.reply_text(r.text)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    
    context.user_data["state"] = None # Reset after use

# 6. MAIN
if __name__ == '__main__':
    if not TOKEN:
        print("ERROR: BOT_TOKEN environment variable not found!")
    else:
        # Start Web Server
        Thread(target=run_server, daemon=True).start()

        # Start Bot
        application = Application.builder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(callback_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

        print("Bot is polling...")
        application.run_polling(drop_pending_updates=True)
