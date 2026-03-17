import os
import glob
import yt_dlp
import imageio_ffmpeg
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- MAGIC FFMPEG FIX ---
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

# --- 1. KEEP-ALIVE WEBSITE ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is awake!"
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
def keep_alive(): Thread(target=run_flask).start()

# --- 2. LANGUAGE SYSTEM & INSTRUCTIONS ---
user_languages = {}

TEXTS = {
    'en': {
        'welcome': (
            "🤖 **Welcome to the Downloader Bot!**\n\n"
            "Here is how to use me:\n"
            "1️⃣ Copy a video link from YouTube, TikTok, or Instagram.\n"
            "2️⃣ Paste and send the link to me in this chat.\n"
            "3️⃣ Click the button for the format you want (Video or MP3).\n"
            "4️⃣ Wait a moment, and I will send you the file directly!\n\n"
            "⚙️ **Commands:**\n"
            "/language - Change language (English/Español)\n"
            "/help - Show these instructions again\n\n"
            "👇 *Send me your first link to get started!*"
        ),
        'choose_lang': "Please choose your language:",
        'lang_set': "Language set to English! 🇬🇧\nSend me a link to download.",
        'choose_format': "🔗 Link detected! Choose your format:",
        'downloading': "Downloading... please wait ⏳ (This might take a minute)",
        'error': "❌ Error:",
    },
    'es': {
        'welcome': (
            "🤖 **¡Bienvenido al Bot de Descargas!**\n\n"
            "Aquí te explicamos cómo usarme:\n"
            "1️⃣ Copia un enlace de video de YouTube, TikTok o Instagram.\n"
            "2️⃣ Pega y envíame el enlace en este chat.\n"
            "3️⃣ Haz clic en el botón del formato que deseas (Video o MP3).\n"
            "4️⃣ ¡Espera un momento y te enviaré el archivo directamente!\n\n"
            "⚙️ **Comandos:**\n"
            "/language - Cambiar idioma (English/Español)\n"
            "/help - Mostrar estas instrucciones nuevamente\n\n"
            "👇 *¡Envíame tu primer enlace para comenzar!*"
        ),
        'choose_lang': "Por favor, elige tu idioma:",
        'lang_set': "¡Idioma cambiado a Español! 🇪🇸\nEnvíame un enlace para descargar.",
        'choose_format': "🔗 ¡Enlace detectado! Elige el formato:",
        'downloading': "Descargando... por favor espera ⏳ (Puede tardar un minuto)",
        'error': "❌ Error:",
    }
}

def get_text(user_id, key):
    lang = user_languages.get(user_id, 'en')
    return TEXTS[lang][key]

# --- 3. BOT COMMANDS & HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await update.message.reply_text(get_text(user_id, 'welcome'))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await update.message.reply_text(get_text(user_id, 'welcome'))

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    keyboard = [
        [InlineKeyboardButton("English 🇬🇧", callback_data='lang_en')],
        [InlineKeyboardButton("Español 🇪🇸", callback_data='lang_es')]
    ]
    await update.message.reply_text(get_text(user_id, 'choose_lang'), reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # Check if the message contains a link
    if "http://" in text or "https://" in text:
        context.user_data['last_link'] = text 
        keyboard = [
            [InlineKeyboardButton("🎬 Video (Best Quality + Sound)", callback_data='dl_mp4_best')],
            [InlineKeyboardButton("📱 Video (Low Quality / Save Data)", callback_data='dl_mp4_low')],
            [InlineKeyboardButton("🎵 Audio Only (MP3)", callback_data='dl_mp3')]
        ]
        await update.message.reply_text(get_text(user_id, 'choose_format'), reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        # If they type random text, show the instructions again
        await update.message.reply_text(get_text(user_id, 'welcome'))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # --- Language Buttons ---
    if query.data == 'lang_en':
        user_languages[user_id] = 'en'
        await query.edit_message_text(get_text(user_id, 'lang_set'))
    elif query.data == 'lang_es':
        user_languages[user_id] = 'es'
        await query.edit_message_text(get_text(user_id, 'lang_set'))

    # --- Download Buttons ---
    elif query.data.startswith('dl_'):
        link = context.user_data.get('last_link')
        if not link: return
            
        await query.edit_message_text(get_text(user_id, 'downloading'))
        
        # Clean up any old files just in case
        for old_file in glob.glob(f"{user_id}_media*"):
            if os.path.exists(old_file):
                os.remove(old_file)

        ydl_opts = {
            'ffmpeg_location': FFMPEG_PATH, 
            'outtmpl': f'{user_id}_media.%(ext)s',
            'noplaylist': True,
            'quiet': True,
            'extractor_args': {'youtube': ['player_client=ios']}, 
        }
        
        if query.data == 'dl_mp4_best':
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif query.data == 'dl_mp4_low':
            ydl_opts['format'] = 'worst[ext=mp4]/worst'
        elif query.data == 'dl_mp3':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])

            downloaded_files = glob.glob(f"{user_id}_media*")
            
            if downloaded_files:
                final_file = downloaded_files[0]
                
                if query.data == 'dl_mp3':
                    with open(final_file, 'rb') as audio:
                        await context.bot.send_audio(chat_id=user_id, audio=audio)
                else:
                    with open(final_file, 'rb') as video:
                        await context.bot.send_video(chat_id=user_id, video=video)
            else:
                raise Exception("Could not locate the downloaded file.")
            
        except Exception as e:
            error_msg = f"{get_text(user_id, 'error')}\n{str(e)}"
            print(error_msg)
            await context.bot.send_message(chat_id=user_id, text=error_msg)
            
        finally:
            for f in glob.glob(f"{user_id}_media*"):
                if os.path.exists(f):
                    os.remove(f)

# --- 4. START THE BOT ---
if __name__ == '__main__':
    keep_alive()
    
    # I have put your exact Token here!
    TOKEN = "8590047923:AAGMOfoDGuVotkf2zYp6kaChXKpRWOLph1w" 
    
    bot_app = Application.builder().token(TOKEN).build()
    
    # Added /help command so users can read instructions anytime
    bot_app.add_handler(CommandHandler('start', start_command))
    bot_app.add_handler(CommandHandler('help', help_command))
    bot_app.add_handler(CommandHandler('language', language_command))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot is running...")
    bot_app.run_polling()
