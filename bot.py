import os
import requests
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
# This dictionary remembers the user's language (Default is English)
user_languages = {}

# Dictionary containing translations
TEXTS = {
    'en': {
        'welcome': "Hello! Send me a YouTube or TikTok link to download.",
        'choose_lang': "Please choose your language:",
        'lang_set': "Language set to English! 🇬🇧",
        'choose_format': "Link detected! Choose your format & quality:",
        'downloading': "Downloading... please wait ⏳ (This might take a minute)",
        'error': "Sorry, an error occurred or the file is larger than 50MB.",
    },
    'es': {
        'welcome': "¡Hola! Envíame un enlace de YouTube o TikTok para descargar.",
        'choose_lang': "Por favor, elige tu idioma:",
        'lang_set': "¡Idioma cambiado a Español! 🇪🇸",
        'choose_format': "¡Enlace detectado! Elige el formato y la calidad:",
        'downloading': "Descargando... por favor espera ⏳ (Esto puede tardar)",
        'error': "Lo siento, ocurrió un error o el archivo pesa más de 50MB.",
    }
}

# Helper function to get the correct text based on user ID
def get_text(user_id, key):
    lang = user_languages.get(user_id, 'en') # Default is 'en'
    return TEXTS[lang][key]

# --- 3. BOT COMMANDS & HANDLERS ---

# /start command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await update.message.reply_text(get_text(user_id, 'welcome'))

# /language command
async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    keyboard = [
        [InlineKeyboardButton("English 🇬🇧", callback_data='lang_en')],
        [InlineKeyboardButton("Español 🇪🇸", callback_data='lang_es')]
    ]
    await update.message.reply_text(get_text(user_id, 'choose_lang'), reply_markup=InlineKeyboardMarkup(keyboard))

# Listen for normal text messages (Links!)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # If the user sends a link
    if "http://" in text or "https://" in text:
        # Save the link temporarily so the bot remembers it when a button is clicked
        context.user_data['last_link'] = text 
        
        # Create Format/Quality buttons
        keyboard = [
            [InlineKeyboardButton("Video (MP4 - Best Quality)", callback_data='dl_mp4_best')],
            [InlineKeyboardButton("Video (MP4 - Low Quality)", callback_data='dl_mp4_low')],
            [InlineKeyboardButton("Audio only (MP3)", callback_data='dl_mp3')]
        ]
        await update.message.reply_text(get_text(user_id, 'choose_format'), reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        # If it's not a link, just remind them what to do
        await update.message.reply_text(get_text(user_id, 'welcome'))

# Handle all button clicks
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
        
        # Configure yt-dlp based on the button they clicked
        ydl_opts = {}
        
        if query.data == 'dl_mp4_best':
            # Gets video + audio merged (limited to 720p so it doesn't break the 50MB limit easily)
            ydl_opts = {'format': 'best[ext=mp4]', 'outtmpl': 'video.%(ext)s'}
        elif query.data == 'dl_mp4_low':
            # Gets worst quality to save space
            ydl_opts = {'format': 'worst[ext=mp4]', 'outtmpl': 'video.%(ext)s'}
        elif query.data == 'dl_mp3':
            # Extracts audio
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}],
                'outtmpl': 'audio.%(ext)s'
            }

        try:
            # Tell yt_dlp to download the file to the server
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
                filename = ydl.prepare_filename(info)
                
                # If MP3 was chosen, yt-dlp changes the extension
                if query.data == 'dl_mp3':
                    filename = filename.replace('.webm', '.mp3').replace('.m4a', '.mp3')

            # Send the file to the user
            if query.data == 'dl_mp3':
                with open(filename, 'rb') as audio:
                    await context.bot.send_audio(chat_id=user_id, audio=audio)
            else:
                with open(filename, 'rb') as video:
                    await context.bot.send_video(chat_id=user_id, video=video)
            
            # Delete the file from the server to save space!
            os.remove(filename)

        except Exception as e:
            print(f"Error: {e}")
            await context.bot.send_message(chat_id=user_id, text=get_text(user_id, 'error'))

# --- 4. START THE BOT ---
if __name__ == '__main__':
    keep_alive()
    
    # YOUR TOKEN HERE
    TOKEN = "8590047923:AAGMOfoDGuVotkf2zYp6kaChXKpRWOLph1w" 
    bot_app = Application.builder().token(TOKEN).build()
    
    bot_app.add_handler(CommandHandler('start', start_command))
    bot_app.add_handler(CommandHandler('language', language_command))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot is running...")
    bot_app.run_polling()
