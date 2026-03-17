"""
Super Bot — Telegram multi-tool bot (Cobalt API + Randytbot Features)
"""

import os
import re
import glob
import time
import asyncio
import logging
import urllib.parse
from threading import Thread
from collections import defaultdict

import requests
from flask import Flask
from gtts import gTTS
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
# 1.  LOGGING & CONFIG
# ══════════════════════════════════════════════════════════
logging.basicConfig(format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN       = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")
ADMIN_IDS   = {int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()}
MAX_FILE_MB = 50

# FIX: Drastically increased rate limit so you don't get blocked while testing!
RATE_LIMIT  = 30 
RATE_WINDOW = 10

# ══════════════════════════════════════════════════════════
# 2.  KEEP-ALIVE
# ══════════════════════════════════════════════════════════
_flask = Flask(__name__)
@_flask.route("/")
def _home(): return "Bot is awake!"
def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    Thread(target=lambda: _flask.run(host="0.0.0.0", port=port), daemon=True).start()

# ══════════════════════════════════════════════════════════
# 3.  IN-MEMORY STATE
# ══════════════════════════════════════════════════════════
user_languages: dict[int, str]         = {}
user_states:    dict[int, str | None]  = {}
_rate_buckets:  dict[int, list[float]] = defaultdict(list)

def is_rate_limited(uid: int) -> bool:
    now = time.monotonic()
    _rate_buckets[uid] = [ts for ts in _rate_buckets[uid] if now - ts < RATE_WINDOW]
    if len(_rate_buckets[uid]) >= RATE_LIMIT: return True
    _rate_buckets[uid].append(now)
    return False

# ══════════════════════════════════════════════════════════
# 4.  TRANSLATIONS
# ══════════════════════════════════════════════════════════
TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "main_menu": "🤖 *Super Bot*\n\nJust paste a link, or choose a tool below:",
        "tools_menu": "🛠 *More Tools*\n\nChoose a tool:",
        "help_text": "📖 *How to use me:*\n\n📥 *Download:* Just paste a video link in the chat!\n🎨 *AI Image:* Describe what to draw.\n🔳 *QR Code:* Text or link → QR image.\n🗣️ *Voice:* Text → audio message.",
        "choose_lang": "🌐 Choose your language:", "lang_set": "✅ Language set to English!\n\n",
        "auto_detect": "🔗 *Link Detected!* Processing video...",
        "ask_prompt": "🎨 *AI Image Maker*\n\nDescribe what you want drawn.",
        "generating": "🎨 Generating image… please wait",
        "ask_qr": "🔳 *QR Generator*\n\nSend any text or link:",
        "ask_tts": "🗣️ *Voice Maker*\n\nSend any text to read aloud:",
        "ask_shorten": "🔗 *URL Shortener*\n\nPaste the link you want shortened:",
        "ask_weather": "⛅ *Weather*\n\nType a city name (e.g. `London`):",
        "ask_currency": "💱 *Currency Converter*\n\nType like: `100 USD to EUR`",
        "error": "❌ Error:", "file_too_large": "❌ File is larger than Telegram's 50MB limit.",
        "rate_limited": "⏳ Please wait a second.", "not_admin": "🚫 Admins only.",
        "btn_help": "Help ℹ️", "btn_lang": "Language 🌐", "btn_image": "AI Image 🎨",
        "btn_qr": "QR Code 🔳", "btn_tts": "Voice 🗣️", "btn_back": "◀ Back", "btn_tools": "More Tools 🛠",
        "btn_shorten": "Short URL 🔗", "btn_weather": "Weather ⛅", "btn_currency": "Currency 💱",
    },
    # (Spanish, French, Portuguese, Arabic defaults fallback to English keys if missing)
}

def t(uid: int, key: str) -> str:
    lang = user_languages.get(uid, "en")
    return TEXTS.get(lang, TEXTS["en"]).get(key, TEXTS["en"].get(key, key))

def main_menu_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(uid, "btn_image"), callback_data="ask_image"), InlineKeyboardButton(t(uid, "btn_qr"), callback_data="ask_qr"), InlineKeyboardButton(t(uid, "btn_tts"), callback_data="ask_tts")],
        [InlineKeyboardButton(t(uid, "btn_tools"), callback_data="show_tools"), InlineKeyboardButton(t(uid, "btn_lang"), callback_data="show_lang"), InlineKeyboardButton(t(uid, "btn_help"), callback_data="show_help")]
    ])

def tools_menu_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(uid, "btn_shorten"), callback_data="ask_shorten"), InlineKeyboardButton(t(uid, "btn_weather"), callback_data="ask_weather")],
        [InlineKeyboardButton(t(uid, "btn_currency"), callback_data="ask_currency")],
        [InlineKeyboardButton(t(uid, "btn_back"), callback_data="show_main")]
    ])

def back_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(t(uid, "btn_back"), callback_data="show_main")]])

# ══════════════════════════════════════════════════════════
# 5.  HELPERS & UI PROGRESS BAR
# ══════════════════════════════════════════════════════════
def cleanup(pattern: str) -> None:
    for path in glob.glob(pattern):
        try: os.remove(path)
        except OSError: pass

# PROGRESS BAR ANIMATION
_BARS = [
    "📥 Downloading: [█░░░░░░░░░] 10%",
    "📥 Downloading: [███░░░░░░░] 30%",
    "📥 Downloading: [█████░░░░░] 50%",
    "📥 Downloading: [███████░░░] 70%",
    "📥 Downloading: [█████████░] 90%",
    "✅ Finalizing: [██████████] 100%"
]
async def _animate_progress(msg, stop: asyncio.Event) -> None:
    i = 0
    while not stop.is_set():
        try: await msg.edit_text(_BARS[i], parse_mode="Markdown")
        except Exception: pass
        if i < len(_BARS) - 2: i += 1
        await asyncio.sleep(2.0)

# ══════════════════════════════════════════════════════════
# 6.  COBALT API ENGINE (NO YT-DLP)
# ══════════════════════════════════════════════════════════
def _run_cobalt_download(url: str, fmt_key: str, prefix: str) -> str:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    payload = {"url": url, "vCodec": "h264", "vQuality": "720"}
    
    instances = [
        "https://api.cobalt.tools/api/json",
        "https://co.wuk.sh/api/json",
        "https://cobalt-api.peppe8o.com/api/json"
    ]

    data = None
    last_error = None
    for api_url in instances:
        try:
            r = requests.post(api_url, json=payload, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()
            if data.get("status") != "error": break
        except Exception as e:
            last_error = e

    if not data or data.get("status") == "error":
        raise Exception(data.get("text", "Video API Servers are currently busy. Please try again."))

    download_url = data.get("url") or (data.get("picker") and data["picker"][0]["url"])
    if not download_url: raise Exception("Could not find download link.")

    filename = f"{prefix}.mp4"
    stream_resp = requests.get(download_url, stream=True, headers=headers, timeout=30)
    stream_resp.raise_for_status()

    content_len = stream_resp.headers.get("Content-Length")
    if content_len and int(content_len) > 50 * 1024 * 1024: raise ValueError("FILE_TOO_LARGE")

    with open(filename, 'wb') as f:
        for chunk in stream_resp.iter_content(chunk_size=1024 * 1024):
            if chunk: f.write(chunk)

    if os.path.getsize(filename) > 50 * 1024 * 1024:
        os.remove(filename)
        raise ValueError("FILE_TOO_LARGE")

    return filename

# ══════════════════════════════════════════════════════════
# 7.  CORE COMMANDS
# ══════════════════════════════════════════════════════════
async def process_download(update: Update, context: ContextTypes.DEFAULT_TYPE, uid: int, link: str):
    prefix = f"{uid}_media"
    cleanup(f"{prefix}*")

    msg = await update.message.reply_text(t(uid, "auto_detect"), parse_mode="Markdown")
    stop = asyncio.Event()
    anim = asyncio.create_task(_animate_progress(msg, stop))

    try:
        final_file = await asyncio.to_thread(_run_cobalt_download, link, "mp4_best", prefix)
        stop.set(); anim.cancel()
        
        try: await msg.edit_text("✅ Video Ready! Uploading...", parse_mode="Markdown")
        except: pass

        with open(final_file, "rb") as fh:
            await context.bot.send_video(chat_id=uid, video=fh)
        try: await msg.delete()
        except: pass

    except ValueError as ve:
        stop.set(); anim.cancel()
        if str(ve) == "FILE_TOO_LARGE": await msg.edit_text(t(uid, "file_too_large"))
        else: await msg.edit_text(f"{t(uid, 'error')} `{ve}`")
    except Exception as exc:
        stop.set(); anim.cancel()
        await msg.edit_text(f"{t(uid, 'error')} `{exc}`")
    finally:
        cleanup(f"{prefix}*")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid, text = update.effective_user.id, update.message.text.strip()
    state = user_states.get(uid)
    
    if is_rate_limited(uid): return

    # --- AUTO-DETECT LINKS (The Randytbot magic) ---
    if "http://" in text or "https://" in text:
        user_states[uid] = None 
        await process_download(update, context, uid, text)
        return

    # --- TOOLS ---
    if state == "waiting_for_qr":
        user_states[uid] = None
        safe = urllib.parse.quote(text)
        await context.bot.send_photo(chat_id=uid, photo=f"https://api.qrserver.com/v1/create-qr-code/?size=512x512&data={safe}", caption="✅ QR Code")
        await update.message.reply_text(t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid))

    elif state == "waiting_for_tts":
        user_states[uid] = None
        fname = f"{uid}_voice.mp3"
        try:
            tts = gTTS(text=text, lang=user_languages.get(uid, "en"))
            await asyncio.to_thread(tts.save, fname)
            with open(fname, "rb") as fh: await context.bot.send_voice(chat_id=uid, voice=fh)
        except Exception as exc: await update.message.reply_text(f"{t(uid, 'error')} {exc}")
        finally: cleanup(fname)
        await update.message.reply_text(t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid))

    # --- AI IMAGE FIX ---
    elif state == "waiting_for_image":
        user_states[uid] = None
        msg = await update.message.reply_text(t(uid, "generating"))
        fname = f"{uid}_ai.jpg"
        try:
            # FIX: Added required headers so the AI server doesn't block the bot!
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            img_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(text)}?width=1080&height=1080&nologo=true"
            resp = await asyncio.to_thread(requests.get, img_url, headers=headers, timeout=60)
            resp.raise_for_status()
            
            with open(fname, "wb") as fh: fh.write(resp.content)
            with open(fname, "rb") as fh: await context.bot.send_photo(chat_id=uid, photo=fh, caption=f"🎨 {text}")
            await msg.delete()
        except Exception as exc:
            await msg.edit_text(f"{t(uid, 'error')} {exc}")
        finally:
            cleanup(fname)
            await update.message.reply_text(t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid))

    else:
        await update.message.reply_text(t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    user_states[uid] = None
    await update.message.reply_text(t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query, uid = update.callback_query, update.callback_query.from_user.id
    data = query.data
    await query.answer()

    if data == "show_main":
        user_states[uid] = None
        await query.edit_message_text(t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown")
    elif data == "show_tools":
        await query.edit_message_text(t(uid, "tools_menu"), reply_markup=tools_menu_keyboard(uid), parse_mode="Markdown")
    elif data == "show_help":
        await query.edit_message_text(t(uid, "help_text"), reply_markup=back_keyboard(uid), parse_mode="Markdown")
    elif data.startswith("ask_"):
        user_states[uid] = f"waiting_for_{data[4:]}"
        await query.edit_message_text(t(uid, data), reply_markup=back_keyboard(uid), parse_mode="Markdown")

if __name__ == "__main__":
    keep_alive()
    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    logger.info("Bot is running…")
    bot_app.run_polling(drop_pending_updates=True)
