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

# --- 2. LANGUAGE SYSTEM & TEXTS ---
user_languages = {}

TEXTS = {
    'en': {
        'main_menu': "🤖 **Welcome to the Downloader Bot!**\n\n🔗 Send me a YouTube, TikTok, or Instagram link to download.\n\n👇 Use the buttons below for settings and instructions.",
        'help_text': (
            "📖 **How to use me:**\n\n"
            "1️⃣ Copy a video link from YouTube, TikTok, or Instagram.\n"
            "2️⃣ Paste and send the link to me in this chat.\n"
            "3️⃣ Click the button for the format you want (Video or MP3).\n"
            "4️⃣ Wait a moment, and I will send you the file!\n\n"
            "👇 *Send me your first link to get started!*"
        ),
        'choose_lang': "🌐 Please choose your language:",
        'lang_set': "✅ Language set to English!\n\n",
        'choose_format': "🔗 Link detected! Choose your format:",
        'downloading': "Downloading... please wait ⏳ (This might take a minute)",
        'error': "❌ Error:",
        'btn_help': "Help ℹ️",
        'btn_lang': "Language 🌐",
        'btn_back': "Back 🔙"
    },
    'es': {
        'main_menu': "🤖 **¡Bienvenido al Bot de Descargas!**\n\n🔗 Envíame un enlace de YouTube, TikTok o Instagram para descargar.\n\n👇 Usa los botones de abajo para ajustes e instrucciones.",
        'help_text': (
            "📖 **Cómo usarme:**\n\n"
            "1️⃣ Copia un enlace de video de YouTube, TikTok o Instagram.\n"
            "2️⃣ Pega y envíame el enlace en este chat.\n"
            "3️⃣ Haz clic en el botón del formato que deseas (Video o MP3).\n"
            "4️⃣ ¡Espera un momento y te enviaré el archivo!\n\n"
            "👇 *¡Envíame tu primer enlace para comenzar!*"
        ),
        'choose_lang': "🌐 Por favor, elige tu idioma:",
        'lang_set': "✅ ¡Idioma cambiado a Español!\n\n",
        'choose_format': "🔗 ¡Enlace detectado! Elige el formato:",
        'downloading': "Descargando... por favor espera ⏳ (Puede tardar)",
        'error': "❌ Error:",
        'btn_help': "Ayuda ℹ️",
        'btn_lang': "Idioma 🌐",
        'btn_back': "Volver 🔙"
    }
}

def get_text(user_id, key):
    lang = user_languages.get(user_id, 'en')
    return TEXTS[lang][key]

# --- 3. MENU GENERATORS ---
def main_menu_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text(user_id, 'btn_help'), callback_data='show_help')],
        [InlineKeyboardButton(get_text(user_id, 'btn_lang'), callback_data='show_lang')]
    ])

def back_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text(user_id, 'btn_back'), callback_data='show_main')]
    ])

# --- 4. BOT COMMANDS & HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await update.message.reply_text(get_text(user_id, 'main_menu'), reply_markup=main_menu_keyboard(user_id))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # If the user sends a link
    if "http://" in text or "https://" in text:
        context.user_data['last_link'] = text 
        keyboard = [
            [InlineKeyboardButton("🎬 Video (Best Quality + Sound)", callback_data='dl_mp4_best')],
            [InlineKeyboardButton("📱 Video (Low Quality)", callback_data='dl_mp4_low')],
            [InlineKeyboardButton("🎵 Audio Only (MP3)", callback_data='dl_mp3')],
            [InlineKeyboardButton(get_text(user_id, 'btn_back'), callback_data='show_main')]
        ]
        await update.message.reply_text(get_text(user_id, 'choose_format'), reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        # If they type random text, show the main menu
        await update.message.reply_text(get_text(user_id, 'main_menu'), reply_markup=main_menu_keyboard(user_id))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # --- Menu Navigation Buttons ---
    if query.data == 'show_main':
        await query.edit_message_text(get_text(user_id, 'main_menu'), reply_markup=main_menu_keyboard(user_id))
        
    elif query.data == 'show_help':
        await query.edit_message_text(get_text(user_id, 'help_text'), reply_markup=back_keyboard(user_id))
        
    elif query.data == 'show_lang':
        keyboard = [
            [InlineKeyboardButton("English 🇬🇧", callback_data='lang_en')],
            [InlineKeyboardButton("Español 🇪🇸", callback_data='lang_es')],
            [InlineKeyboardButton(get_text(user_id, 'btn_back'), callback_data='show_main')]
        ]
        await query.edit_message_text(get_text(user_id, 'choose_lang'), reply_markup=InlineKeyboardMarkup(keyboard))

    # --- Language Selection Buttons ---
    elif query.data in ['lang_en', 'lang_es']:
        user_languages[user_id] = query.data.split('_')[1] # extracts 'en' or 'es'
        
        # After choosing language, send them back to the Main Menu automatically
        new_text = get_text(user_id, 'lang_set') + get_text(user_id, 'main_menu')
        await query.edit_message_text(new_text, reply_markup=main_menu_keyboard(user_id))

    # --- Download Buttons ---
    elif query.data.startswith('dl_'):
        link = context.user_data.get('last_link')
        if not link: return
            
        await query.edit_message_text(get_text(user_id, 'downloading'))
        
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

# --- 5. START THE BOT ---
if __name__ == '__main__':
    keep_alive()
    
    # Your Token
    TOKEN = "8590047923:AAGMOfoDGuVotkf2zYp6kaChXKpRWOLph1w" 
    
    bot_app = Application.builder().token(TOKEN).build()
    
    bot_app.add_handler(CommandHandler('start', start_command))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot is running...")
    bot_app.run_polling()
