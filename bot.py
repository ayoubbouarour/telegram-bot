import os
import yt_dlp
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- 1. KEEP-ALIVE WEBSITE ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is awake!"
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
def keep_alive(): Thread(target=run_flask).start()

# --- 2. LANGUAGE SYSTEM ---
user_languages = {}

TEXTS = {
    'en': {
        'welcome': "Hello! Send me a YouTube, Instagram, or TikTok link to download.",
        'choose_lang': "Please choose your language:",
        'lang_set': "Language set to English! 🇬🇧",
        'choose_format': "Link detected! Choose your format:",
        'downloading': "Downloading... please wait ⏳",
    },
    'es': {
        'welcome': "¡Hola! Envíame un enlace de YouTube, Instagram o TikTok para descargar.",
        'choose_lang': "Por favor, elige tu idioma:",
        'lang_set': "¡Idioma cambiado a Español! 🇪🇸",
        'choose_format': "¡Enlace detectado! Elige el formato:",
        'downloading': "Descargando... por favor espera ⏳",
    }
}

def get_text(user_id, key):
    lang = user_languages.get(user_id, 'en')
    return TEXTS[lang][key]

# --- 3. BOT COMMANDS & HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    if "http://" in text or "https://" in text:
        context.user_data['last_link'] = text 
        keyboard = [
            [InlineKeyboardButton("Video (Best Quality with Sound)", callback_data='dl_mp4_best')],
            [InlineKeyboardButton("Video (Low Quality)", callback_data='dl_mp4_low')],
            [InlineKeyboardButton("Audio Only", callback_data='dl_mp3')]
        ]
        await update.message.reply_text(get_text(user_id, 'choose_format'), reply_markup=InlineKeyboardMarkup(keyboard))
    else:
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
        if not link:
            return
            
        await query.edit_message_text(get_text(user_id, 'downloading'))
        
        # MAGIC FIX FOR SOUND AND NO CONVERTER ERRORS:
        if query.data == 'dl_mp4_best':
            # 'best' gets a file that ALREADY has video and audio combined
            ydl_opts = {'format': 'best', 'outtmpl': f'{user_id}_video.%(ext)s'}
        elif query.data == 'dl_mp4_low':
            # 'worst' gets the smallest combined file
            ydl_opts = {'format': 'worst', 'outtmpl': f'{user_id}_video.%(ext)s'}
        elif query.data == 'dl_mp3':
            # 'bestaudio' gets the raw audio file (usually .m4a or .webm). 
            # We don't force .mp3 because that requires ffmpeg! Telegram plays .m4a perfectly.
            ydl_opts = {'format': 'bestaudio', 'outtmpl': f'{user_id}_audio.%(ext)s'}

        filename = None
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
                filename = ydl.prepare_filename(info)

            # Send the file
            if query.data == 'dl_mp3':
                with open(filename, 'rb') as audio:
                    await context.bot.send_audio(chat_id=user_id, audio=audio)
            else:
                with open(filename, 'rb') as video:
                    await context.bot.send_video(chat_id=user_id, video=video)
            
        except Exception as e:
            error_msg = f"❌ Error:\n{str(e)}"
            print(error_msg)
            await context.bot.send_message(chat_id=user_id, text=error_msg)
            
        finally:
            # Always delete the file from the server when done, even if it crashes!
            if filename and os.path.exists(filename):
                os.remove(filename)

# --- 4. START THE BOT ---
if __name__ == '__main__':
    keep_alive()
    
    # PUT YOUR TOKEN HERE
    TOKEN = "8590047923:AAGMOfoDGuVotkf2zYp6kaChXKpRWOLph1w" 
    
    bot_app = Application.builder().token(TOKEN).build()
    
    bot_app.add_handler(CommandHandler('start', start_command))
    bot_app.add_handler(CommandHandler('language', language_command))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot is running...")
    bot_app.run_polling()
