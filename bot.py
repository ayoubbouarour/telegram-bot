import os
import glob
import yt_dlp
import requests
import imageio_ffmpeg
import urllib.parse
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

# --- 2. DATABASE (Memory & Languages) ---
user_languages = {}
user_states = {} # Remembers if the user is typing an AI prompt or just navigating menus

TEXTS = {
    'en': {
        'main_menu': "🤖 **Welcome to the Media Bot!**\n\n🔗 Send a video link to download, or use the AI Image Maker below.",
        'help_text': (
            "📖 **How to use me:**\n\n"
            "📥 **To Download:** Just paste a YouTube, TikTok, or Instagram link in the chat.\n"
            "🎨 **To Make Art:** Click the AI Image button and tell me what to draw.\n\n"
        ),
        'choose_lang': "🌐 Please choose your language:",
        'lang_set': "✅ Language set to English!\n\n",
        'choose_format': "🔗 Link detected! Choose your format:",
        'downloading': "Downloading... please wait ⏳ (This might take a minute)",
        'ask_prompt': "🎨 **AI 4K Image Maker**\n\nType a description of what you want me to draw (e.g., 'A futuristic city at sunset' or 'A cyberpunk cat').\n\nOr click Back to cancel.",
        'generating': "🎨 Creating your 4K masterpiece... Please wait ⏳",
        'error': "❌ Error:",
        'btn_help': "Help ℹ️",
        'btn_lang': "Language 🌐",
        'btn_image': "AI Image Maker 🎨",
        'btn_back': "Back 🔙"
    },
    'es': {
        'main_menu': "🤖 **¡Bienvenido al Media Bot!**\n\n🔗 Envía un enlace para descargar, o usa el Creador de Imágenes IA abajo.",
        'help_text': (
            "📖 **Cómo usarme:**\n\n"
            "📥 **Para Descargar:** Solo pega un enlace de YouTube, TikTok o Instagram en el chat.\n"
            "🎨 **Para Crear Arte:** Haz clic en el botón de Imagen IA y dime qué dibujar.\n\n"
        ),
        'choose_lang': "🌐 Por favor, elige tu idioma:",
        'lang_set': "✅ ¡Idioma cambiado a Español!\n\n",
        'choose_format': "🔗 ¡Enlace detectado! Elige el formato:",
        'downloading': "Descargando... por favor espera ⏳ (Puede tardar)",
        'ask_prompt': "🎨 **Creador de Imágenes IA 4K**\n\nEscribe una descripción de lo que quieres que dibuje (ej. 'Una ciudad futurista al atardecer' o 'Un gato ciberpunk').\n\nO haz clic en Volver para cancelar.",
        'generating': "🎨 Creando tu obra maestra en 4K... Por favor espera ⏳",
        'error': "❌ Error:",
        'btn_help': "Ayuda ℹ️",
        'btn_lang': "Idioma 🌐",
        'btn_image': "Creador de Imágenes IA 🎨",
        'btn_back': "Volver 🔙"
    }
}

def get_text(user_id, key):
    lang = user_languages.get(user_id, 'en')
    return TEXTS[lang][key]

# --- 3. MENU GENERATORS ---
def main_menu_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text(user_id, 'btn_image'), callback_data='ask_image')],
        [InlineKeyboardButton(get_text(user_id, 'btn_help'), callback_data='show_help'),
         InlineKeyboardButton(get_text(user_id, 'btn_lang'), callback_data='show_lang')]
    ])

def back_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text(user_id, 'btn_back'), callback_data='show_main')]
    ])

# --- 4. BOT COMMANDS & HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_states[user_id] = None # Reset state
    await update.message.reply_text(get_text(user_id, 'main_menu'), reply_markup=main_menu_keyboard(user_id))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    state = user_states.get(user_id)

    # If the bot is waiting for an AI image prompt
    if state == 'waiting_for_image':
        user_states[user_id] = None # Reset state
        await update.message.reply_text(get_text(user_id, 'generating'))
        
        try:
            # Format the prompt for the AI API (width=3840 & height=2160 makes it 4K)
            safe_prompt = urllib.parse.quote(text)
            image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=3840&height=2160&nologo=true"
            
            # Download the image to the server temporarily
            response = requests.get(image_url)
            image_filename = f"{user_id}_ai_image.jpg"
            
            with open(image_filename, 'wb') as f:
                f.write(response.content)
                
            # Send as a DOCUMENT so Telegram doesn't compress the 4K quality!
            with open(image_filename, 'rb') as doc:
                await context.bot.send_document(chat_id=user_id, document=doc, filename="4K_AI_Artwork.jpg", caption=f"🎨 {text}")
                
            os.remove(image_filename) # Clean up server
            
            # Show main menu again
            await update.message.reply_text(get_text(user_id, 'main_menu'), reply_markup=main_menu_keyboard(user_id))
            
        except Exception as e:
            await update.message.reply_text(f"{get_text(user_id, 'error')} {str(e)}")

    # If the user sends a link (Video Downloader)
    elif "http://" in text or "https://" in text:
        context.user_data['last_link'] = text 
        keyboard = [
            [InlineKeyboardButton("🎬 Video (Best Quality)", callback_data='dl_mp4_best')],
            [InlineKeyboardButton("📱 Video (Low Quality)", callback_data='dl_mp4_low')],
            [InlineKeyboardButton("🎵 Audio Only (MP3)", callback_data='dl_mp3')],
            [InlineKeyboardButton(get_text(user_id, 'btn_back'), callback_data='show_main')]
        ]
        await update.message.reply_text(get_text(user_id, 'choose_format'), reply_markup=InlineKeyboardMarkup(keyboard))
        
    # If they just type random text
    else:
        await update.message.reply_text(get_text(user_id, 'main_menu'), reply_markup=main_menu_keyboard(user_id))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # --- Menu Navigation ---
    if query.data == 'show_main':
        user_states[user_id] = None # Cancel any pending actions
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

    # --- Start AI Image Process ---
    elif query.data == 'ask_image':
        user_states[user_id] = 'waiting_for_image' # Tell the bot to expect a prompt next
        await query.edit_message_text(get_text(user_id, 'ask_prompt'), reply_markup=back_keyboard(user_id))

    # --- Language Selection ---
    elif query.data in ['lang_en', 'lang_es']:
        user_languages[user_id] = query.data.split('_')[1]
        new_text = get_text(user_id, 'lang_set') + get_text(user_id, 'main_menu')
        await query.edit_message_text(new_text, reply_markup=main_menu_keyboard(user_id))

    # --- Download Buttons ---
    elif query.data.startswith('dl_'):
        link = context.user_data.get('last_link')
        if not link: return
            
        await query.edit_message_text(get_text(user_id, 'downloading'))
        
        for old_file in glob.glob(f"{user_id}_media*"):
            if os.path.exists(old_file): os.remove(old_file)

        ydl_opts = {
            'ffmpeg_location': FFMPEG_PATH, 
            'outtmpl': f'{user_id}_media.%(ext)s',
            'noplaylist': True,
            'quiet': True,
            'extractor_args': {'youtube': ['player_client=ios']}, 
        }
        
        if query.data == 'dl_mp4_best': ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif query.data == 'dl_mp4_low': ydl_opts['format'] = 'worst[ext=mp4]/worst'
        elif query.data == 'dl_mp3':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])

            downloaded_files = glob.glob(f"{user_id}_media*")
            if downloaded_files:
                final_file = downloaded_files[0]
                if query.data == 'dl_mp3':
                    with open(final_file, 'rb') as audio: await context.bot.send_audio(chat_id=user_id, audio=audio)
                else:
                    with open(final_file, 'rb') as video: await context.bot.send_video(chat_id=user_id, video=video)
            else:
                raise Exception("Could not locate the downloaded file.")
        except Exception as e:
            error_msg = f"{get_text(user_id, 'error')}\n{str(e)}"
            await context.bot.send_message(chat_id=user_id, text=error_msg)
        finally:
            for f in glob.glob(f"{user_id}_media*"):
                if os.path.exists(f): os.remove(f)

# --- 5. START THE BOT ---
if __name__ == '__main__':
    keep_alive()
    TOKEN = "8590047923:AAGMOfoDGuVotkf2zYp6kaChXKpRWOLph1w" 
    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler('start', start_command))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot is running...")
    bot_app.run_polling()
