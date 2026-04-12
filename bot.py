import os, json, time, asyncio, logging, urllib.parse, secrets, string
from threading import Thread
import requests, img2pdf, pyfiglet, wikipediaapi
from flask import Flask
from gtts import gTTS
from deep_translator import GoogleTranslator
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ══════════════════════════════════════════════════════════
# 1. CORE CONFIG & LOGGING
# ══════════════════════════════════════════════════════════
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN")

# Flask Server for Render (Prevents sleeping and port errors)
app_web = Flask(__name__)
@app_web.route('/')
def index(): return "Brick Kick Supreme Bot is Online!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port)

# ══════════════════════════════════════════════════════════
# 2. THE SUPREME INTERFACE
# ══════════════════════════════════════════════════════════

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📽 Downloader (All)", callback_data="set_dl"), InlineKeyboardButton("🤖 AI Chat", callback_data="set_ai")],
        [InlineKeyboardButton("🎨 AI Image Maker", callback_data="set_img"), InlineKeyboardButton("🔍 IP Tracker", callback_data="set_ip")],
        [InlineKeyboardButton("🛡 Link Scanner", callback_data="set_scan"), InlineKeyboardButton("🌐 Website Whois", callback_data="set_whois")],
        [InlineKeyboardButton("🔳 QR Code Maker", callback_data="set_qr"), InlineKeyboardButton("🗣 Text to Voice", callback_data="set_tts")],
        [InlineKeyboardButton("📖 Wikipedia", callback_data="set_wiki"), InlineKeyboardButton("🌐 Translator", callback_data="set_trans")],
        [InlineKeyboardButton("⛅ Weather", callback_data="set_weather"), InlineKeyboardButton("💱 Currency", callback_data="set_curr")],
        [InlineKeyboardButton("🔑 Password Gen", callback_data="set_pass"), InlineKeyboardButton("📄 Img to PDF", callback_data="set_pdf")],
        [InlineKeyboardButton("🗿 Name Decorator", callback_data="set_name"), InlineKeyboardButton("🅰 ASCII Art", callback_data="set_ascii")],
        [InlineKeyboardButton("🤣 Random Joke", callback_data="do_joke"), InlineKeyboardButton("💬 Daily Quote", callback_data="do_quote")],
        [InlineKeyboardButton("📉 Crypto Price", callback_data="set_crypto"), InlineKeyboardButton("🔗 URL Shortener", callback_data="set_short")],
        [InlineKeyboardButton("🎲 Dice Roll", callback_data="do_dice"), InlineKeyboardButton("📱 Device Info", callback_data="do_info")],
        [InlineKeyboardButton("🧪 System Ping", callback_data="do_ping"), InlineKeyboardButton("🧹 Clear State", callback_data="home")],
        [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/brick_kick")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ══════════════════════════════════════════════════════════
# 3. HANDLERS
# ══════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Reset any active states
    context.user_data.clear()
    await update.message.reply_text(
        "🔥 *BRICK KICK SUPREME TOOLS* 🔥\nChoose a working tool from the list below:", 
        reply_markup=main_menu(), parse_mode="Markdown"
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("set_"):
        state = data.replace("set_", "")
        context.user_data["state"] = state
        
        # Immediate logic for specific tools
        if state == "pass":
            pw = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
            await query.message.reply_text(f"🔑 *Generated Password:* `{pw}`", parse_mode="Markdown")
            context.user_data["state"] = None
        elif state == "pdf":
            context.user_data["pdf_files"] = []
            await query.message.reply_text("📄 Send photos one by one. When finished, type /done")
        else:
            await query.message.reply_text(f"📥 Send input for *{state.upper()}*:", parse_mode="Markdown")
    
    elif data == "home":
        context.user_data.clear()
        await query.edit_message_text("Select an option:", reply_markup=main_menu())
    
    elif data == "do_joke":
        r = requests.get("https://official-joke-api.appspot.com/random_joke").json()
        await query.message.reply_text(f"🤣 {r['setup']}\n\n✨ {r['punchline']}")
    
    elif data == "do_ping":
        s = time.time()
        msg = await query.message.reply_text("🏓 Pinging...")
        await msg.edit_text(f"🚀 *Pong!* {round((time.time() - s) * 1000)}ms", parse_mode="Markdown")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    text = update.message.text
    if not state: return

    load_msg = await update.message.reply_text("⚙️ *Processing...*", parse_mode="Markdown")

    try:
        # Downloader
        if state == "dl":
            r = requests.post("https://api.cobalt.tools", json={"url": text}, headers={"Accept": "application/json", "Content-Type": "application/json"})
            url = r.json().get("url")
            if url: await update.message.reply_video(url)
            else: await load_msg.edit_text("❌ Error: Unsupported link or server busy.")

        # IP Tracker
        elif state == "ip":
            r = requests.get(f"http://ip-api.com/json/{text}").json()
            if r['status'] == 'success':
                res = f"📍 *IP INFO:* {text}\n🌍 Country: {r['country']}\n🏙 City: {r['city']}\n🏢 ISP: {r['isp']}"
                await update.message.reply_text(res, parse_mode="Markdown")
            else: await load_msg.edit_text("❌ Invalid IP address.")

        # AI Image
        elif state == "img":
            await update.message.reply_photo(f"https://image.pollinations.ai/prompt/{urllib.parse.quote(text)}?nologo=true", caption=f"🎨: {text}")

        # QR Code
        elif state == "qr":
            await update.message.reply_photo(f"https://api.qrserver.com/v1/create-qr-code/?data={urllib.parse.quote(text)}", caption="✅ QR Code")

        # Wikipedia
        elif state == "wiki":
            wiki = wikipediaapi.Wikipedia(user_agent='BrickKickBot/1.0', language='en')
            p = wiki.page(text)
            await update.message.reply_text(p.summary[:800] if p.exists() else "❌ No information found.")

        # ASCII Art
        elif state == "ascii":
            art = pyfiglet.figlet_format(text)
            await update.message.reply_text(f"```\n{art}\n```", parse_mode="MarkdownV2")

        # TTS Voice
        elif state == "tts":
            uid = update.effective_user.id
            gTTS(text=text, lang='en').save(f"{uid}.mp3")
            await update.message.reply_voice(open(f"{uid}.mp3", "rb"))
            os.remove(f"{uid}.mp3")

        # Whois Website
        elif state == "whois":
            await update.message.reply_text(f"🌐 [Whois lookup for {text}](https://www.whois.com/whois/{text})", parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    
    await load_msg.delete()
    context.user_data["state"] = None

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") == "pdf":
        file = await update.message.photo[-1].get_file()
        path = f"img_{len(context.user_data['pdf_files'])}.jpg"
        await file.download_to_drive(path)
        context.user_data["pdf_files"].append(path)
        await update.message.reply_text(f"📸 Image {len(context.user_data['pdf_files'])} added. Type /done when finished.")

async def done_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    files = context.user_data.get("pdf_files", [])
    if not files: return
    out = "Generated.pdf"
    with open(out, "wb") as f: f.write(img2pdf.convert(files))
    await update.message.reply_document(open(out, "rb"), caption="✅ Your PDF is ready.")
    for f in files: os.remove(f)
    os.remove(out)
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

    print("Brick Kick Supreme Bot is Live!")
    app.run_polling(drop_pending_updates=True)
