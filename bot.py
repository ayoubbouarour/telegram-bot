import os, re, json, time, asyncio, logging, secrets, string, urllib.parse
from threading import Thread
import requests, img2pdf, wikipediaapi, pyfiglet
from flask import Flask
from gtts import gTTS
from deep_translator import GoogleTranslator
from youtubesearchpython import VideosSearch
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ══════════════════════════════════════════════════════════
# 1. CORE SETUP
# ══════════════════════════════════════════════════════════
logging.basicConfig(format="%(asctime)s | %(message)s", level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")

_flask = Flask(__name__)
@_flask.route("/")
def _home(): return "Infinite Bot Online!"

def run_keep_alive():
    _flask.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# ══════════════════════════════════════════════════════════
# 2. MENU HELPERS
# ══════════════════════════════════════════════════════════

def main_menu():
    keys = [
        [InlineKeyboardButton("📹 Media & DL", callback_data="cat_media"), InlineKeyboardButton("🛠 Utility Tools", callback_data="cat_util")],
        [InlineKeyboardButton("🧠 AI & Graphics", callback_data="cat_ai"), InlineKeyboardButton("📚 Knowledge", callback_data="cat_know")],
        [InlineKeyboardButton("💹 Money & Crypto", callback_data="cat_fin"), InlineKeyboardButton("🎉 Fun & Games", callback_data="cat_fun")],
        [InlineKeyboardButton("👨‍💻 Developer", callback_data="cat_dev"), InlineKeyboardButton("🌍 Search", callback_data="cat_search")]
    ]
    return InlineKeyboardMarkup(keys)

def sub_menu(category):
    menus = {
        "media": [["📹 Downloader (All)", "dl"], ["🎬 YT Search", "yts"], ["🎵 Get Lyrics", "lyrics"], ["🎧 Audio Conv", "tts"]],
        "util": [["🌐 Translate", "trans"], ["🔗 Shorten Link", "short"], ["🔳 QR Code", "qr"], ["🔑 Password", "pass"], ["📄 Img to PDF", "pdf"]],
        "ai": [["🤖 AI Chat", "chat"], ["🎨 AI Image", "ai"], ["🖼 BG Remover", "bg"], ["✨ Upscaler", "up"]],
        "know": [["📖 Wikipedia", "wiki"], ["⛅ Weather", "weather"], ["💱 Currency", "curr"], ["📖 Dictionary", "dict"]],
        "fin": [["💰 Crypto Price", "crypto"], ["📉 Stock Price", "stock"], ["🏦 Tax Calc", "tax"]],
        "fun": [["🤣 Jokes", "joke"], ["💬 Quotes", "quote"], ["🔮 Horoscope", "horo"], ["🅰 ASCII Art", "ascii"], ["🎲 Dice", "dice"]],
        "search": [["🔍 Google Search", "google"], ["🖼 Image Search", "imgsearch"], ["👤 User Info", "info"]]
    }
    buttons = [[InlineKeyboardButton(item[0], callback_data=f"set_{item[1]}")] for item in menus.get(category, [])]
    buttons.append([InlineKeyboardButton("◀ Back to Menu", callback_data="home")])
    return InlineKeyboardMarkup(buttons)

# ══════════════════════════════════════════════════════════
# 3. HANDLERS
# ══════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # CRITICAL: Reset state on /start
    context.user_data["state"] = None
    await update.message.reply_text(
        "🔥 *Infinite Multi-Tool Bot*\nEverything you need in one place\.\n\nChoose a category:", 
        reply_markup=main_menu(), parse_mode="MarkdownV2"
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = query.data

    if d == "home":
        context.user_data["state"] = None
        await query.edit_message_text("Choose a category:", reply_markup=main_menu())
    elif d.startswith("cat_"):
        await query.edit_message_text(f"🛠 *{d[4:].upper()} CATEGORY*", reply_markup=sub_menu(d[4:]), parse_mode="Markdown")
    elif d.startswith("set_"):
        state = d.replace("set_", "")
        context.user_data["state"] = state
        
        # Immediate tools that don't need text input
        if state == "dice":
            await query.message.reply_dice()
            context.user_data["state"] = None
        elif state == "joke":
            r = requests.get("https://official-joke-api.appspot.com/random_joke").json()
            await query.message.reply_text(f"🤣 {r['setup']}\n\n✨ {r['punchline']}")
            context.user_data["state"] = None
        else:
            await query.message.reply_text(f"📥 Send me the input for *{state.upper()}*:\n(Or type /start to cancel)")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    text = update.message.text
    if not state: return

    m = await update.message.reply_text("Processing... ⏳")
    
    try:
        if state == "dl":
            r = requests.post("https://api.cobalt.tools", json={"url": text}, 
                             headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=15)
            url = r.json().get("url")
            if url: await update.message.reply_video(url)
            else: await m.edit_text("❌ Failed to fetch video.")
        
        elif state == "ai":
            await update.message.reply_photo(f"https://image.pollinations.ai/prompt/{urllib.parse.quote(text)}?nologo=true")
            await m.delete()

        elif state == "wiki":
            wiki = wikipediaapi.Wikipedia('CenturionBot/1.0', 'en')
            p = wiki.page(text)
            await update.message.reply_text(p.summary[:1000] if p.exists() else "❌ No result.")
            await m.delete()

        elif state == "weather":
            r = requests.get(f"https://wttr.in/{text}?format=4")
            await update.message.reply_text(r.text)
            await m.delete()

        elif state == "ascii":
            f = pyfiglet.Figlet(font='slant')
            await update.message.reply_text(f"`{f.renderText(text)}`", parse_mode="MarkdownV2")
            await m.delete()

        elif state == "trans":
            res = GoogleTranslator(source='auto', target='en').translate(text)
            await update.message.reply_text(f"🌐 Translated to English:\n`{res}`", parse_mode="Markdown")
            await m.delete()

    except Exception as e:
        await m.edit_text(f"❌ Error: {str(e)}")
    
    # Optional: Clear state after success
    # context.user_data["state"] = None

# ══════════════════════════════════════════════════════════
# 4. RUN
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    Thread(target=run_keep_alive, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("Infinite Bot Started!")
    app.run_polling(drop_pending_updates=True)
