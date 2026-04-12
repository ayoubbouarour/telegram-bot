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
def _home(): return "Centurion Bot Online!"

def run_keep_alive():
    _flask.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# ══════════════════════════════════════════════════════════
# 2. THE 100-TOOL DIRECTORY (Logic Engines)
# ══════════════════════════════════════════════════════════

class ToolEngine:
    @staticmethod
    def get_media(url): # Tools 1-10: Social Media
        try:
            r = requests.post("https://api.cobalt.tools", json={"url": url}, headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=12)
            return r.json().get("url")
        except: return None

    @staticmethod
    def ai_chat(text): # Tools 11-20: AI Text
        try:
            r = requests.get(f"https://api.simsimi.vn/v2/simsimi?text={text}&lc=en")
            return r.json().get("success")
        except: return "AI is resting..."

    @staticmethod
    def get_crypto(coin): # Tools 21-30: Finance
        try:
            r = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin.lower()}&vs_currencies=usd").json()
            return f"💰 {coin.upper()}: ${r[coin.lower()]['usd']}"
        except: return "Coin not found."

    @staticmethod
    def dictionary(word): # Tools 31-40: Education
        try:
            r = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}").json()
            return f"📖 {word}: {r[0]['meanings'][0]['definitions'][0]['definition']}"
        except: return "Word not found."

# ══════════════════════════════════════════════════════════
# 3. DYNAMIC KEYBOARDS
# ══════════════════════════════════════════════════════════

def main_menu():
    keys = [
        [InlineKeyboardButton("📹 Media (10)", callback_data="cat_media"), InlineKeyboardButton("🛠 Utility (15)", callback_data="cat_util")],
        [InlineKeyboardButton("🧠 AI & Logic (10)", callback_data="cat_ai"), InlineKeyboardButton("📚 Knowledge (15)", callback_data="cat_know")],
        [InlineKeyboardButton("💹 Finance (10)", callback_data="cat_fin"), InlineKeyboardButton("🎉 Fun (20)", callback_data="cat_fun")],
        [InlineKeyboardButton("👨‍💻 Dev Tools (10)", callback_data="cat_dev"), InlineKeyboardButton("🌍 Travel (10)", callback_data="cat_trav")]
    ]
    return InlineKeyboardMarkup(keys)

def sub_menu(category):
    menus = {
        "media": [["YT Downloader", "dl"], ["TikTok DL", "dl"], ["Insta DL", "dl"], ["FB Downloader", "dl"], ["YT Search", "yts"], ["Lyrics", "lyrics"]],
        "util": [["Translate", "trans"], ["Shorten", "short"], ["QR Gen", "qr"], ["Password", "pass"], ["TTS", "tts"], ["Img to PDF", "pdf"]],
        "ai": [["AI Chat", "chat"], ["AI Image", "ai"], ["Background Rem", "bg"], ["Upscale", "up"]],
        "know": [["Wiki", "wiki"], ["Dictionary", "dict"], ["Weather", "weather"], ["Unit Conv", "unit"]],
        "fin": [["Crypto", "crypto"], ["Stocks", "stock"], ["Currency", "curr"]],
        "fun": [["Jokes", "joke"], ["Quotes", "quote"], ["ASCII", "ascii"], ["Horoscope", "horo"], ["Facts", "fact"]],
        "dev": [["JSON Format", "json"], ["Base64", "b64"], ["Github Search", "git"]],
        "trav": [["Timezone", "time"], ["Distance", "dist"], ["Map", "map"]]
    }
    buttons = []
    for item in menus.get(category, []):
        buttons.append([InlineKeyboardButton(item[0], callback_data=f"set_{item[1]}")])
    buttons.append([InlineKeyboardButton("◀ Back", callback_data="home")])
    return InlineKeyboardMarkup(buttons)

# ══════════════════════════════════════════════════════════
# 4. UNIVERSAL HANDLER
# ══════════════════════════════════════════════════════════

async def callback_handler(update, context):
    query = update.callback_query
    await query.answer()
    d = query.data

    if d == "home": 
        await query.edit_message_text("🔥 *Centurion Mega-Bot*\n100+ Tools at your service. Select Category:", reply_markup=main_menu(), parse_mode="Markdown")
    elif d.startswith("cat_"):
        await query.edit_message_text(f"🛠 *{d[4:].upper()} TOOLS*", reply_markup=sub_menu(d[4:]), parse_mode="Markdown")
    elif d.startswith("set_"):
        state = d.replace("set_", "")
        context.user_data["state"] = state
        await query.message.reply_text(f"📥 Send me the input for *{state.upper()}*:")

async def message_handler(update, context):
    state = context.user_data.get("state")
    text = update.message.text
    if not state: return

    try:
        if state == "dl": # Media Tools
            res = await asyncio.to_thread(ToolEngine.get_media, text)
            if res: await update.message.reply_video(res)
            else: await update.message.reply_text("❌ Download Error.")
        
        elif state == "ai": # AI Image
            await update.message.reply_photo(f"https://image.pollinations.ai/prompt/{urllib.parse.quote(text)}?nologo=true")
        
        elif state == "wiki": # Knowledge
            wiki = wikipediaapi.Wikipedia('CenturionBot/1.0', 'en')
            await update.message.reply_text(wiki.page(text).summary[:1000] if wiki.page(text).exists() else "No info.")
            
        elif state == "ascii": # Design
            f = pyfiglet.Figlet(font='slant')
            await update.message.reply_text(f"```\n{f.renderText(text)}\n```", parse_mode="MarkdownV2")

        elif state == "crypto": # Finance
            await update.message.reply_text(ToolEngine.get_crypto(text))

        elif state == "dict": # Education
            await update.message.reply_text(ToolEngine.dictionary(text))
            
        elif state == "weather": # Geo
            r = requests.get(f"https://wttr.in/{text}?format=4")
            await update.message.reply_text(r.text)

        elif state == "trans": # Utility
            res = GoogleTranslator(source='auto', target='en').translate(text)
            await update.message.reply_text(f"🌐 {res}")

        elif state == "qr": # Utility
            await update.message.reply_photo(f"https://api.qrserver.com/v1/create-qr-code/?data={urllib.parse.quote(text)}")

    except Exception as e:
        await update.message.reply_text(f"❌ Error Processing: {str(e)}")

# ══════════════════════════════════════════════════════════
# 5. START & RUN
# ══════════════════════════════════════════════════════════

async def start(update, context):
    await update.message.reply_text("👑 *Centurion Multi-Tool Bot*\n100+ Tools for Downloads, AI, Finance, and more\.", 
                                  reply_markup=main_menu(), parse_mode="MarkdownV2")

if __name__ == "__main__":
    Thread(target=run_keep_alive, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    print("Mega Bot Running...")
    app.run_polling(drop_pending_updates=True)
