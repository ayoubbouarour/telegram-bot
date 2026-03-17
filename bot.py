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
user_states = {} 

TEXTS = {
    'en': {
        'main_menu': "🤖 **Welcome to the Media Bot!**\n\nChoose an option from the menu below:",
        'help_text': (
            "📖 **How to use me:**\n\n"
            "📥 **To Download:** Click YouTube, TikTok, or Instagram, then paste your link.\n"
            "🎨 **To Make Art:** Click the AI Image button and tell me what to draw.\n\n"
        ),
        'choose_lang': "🌐 Please choose your language:",
        'lang_set': "✅ Language set to English!\n\n",
        'choose_format': "🔗 Link detected! Choose your format:",
        'downloading': "Downloading... please wait ⏳",
        'ask_prompt': "🎨 **AI Image Maker**\n\nType a description of what you want me to draw (e.g., 'A cyberpunk cat' or 'A beautiful sunset over the mountains').",
        'generating': "🎨 Painting your masterpiece... Please wait ⏳",
        'ask_yt': "🔴 Please paste your **YouTube** link below:",
        'ask_ig': "📸 Please paste your **Instagram** link below:",
        'ask_tt': "🎵 Please paste your **TikTok** link below:",
        'invalid_yt': "❌ That doesn't look like a YouTube link. Please try again:",
        'invalid_ig': "❌ That doesn't look like an Instagram link. Please try again:",
        'invalid_tt': "❌ That doesn't look like a TikTok link. Please try again:",
        'error': "❌ Error:",
        'btn_help': "Help ℹ️",
        'btn_lang': "Language 🌐",
        'btn_image': "AI Image Maker 🎨",
        'btn_back': "Back 🔙"
    },
    'es': {
        'main_menu': "🤖 **¡Bienvenido al Media Bot!**\n\nElige una opción del menú de abajo:",
        'help_text': (
            "📖 **Cómo usarme:**\n\n"
            "📥 **Para Descargar:** Haz clic en YouTube, TikTok o Instagram, luego pega tu enlace.\n"
            "🎨 **Para Crear Arte:** Haz clic en Imagen IA y dime qué dibujar.\n\n"
        ),
        'choose_lang': "🌐 Por favor, elige tu idioma:",
        'lang_set': "✅ ¡Idioma cambiado a Español!\n\n",
        'choose_format': "🔗 ¡Enlace detectado! Elige el formato:",
        'downloading': "Descargando... por favor espera ⏳",
        'ask_prompt': "🎨 **Creador de Imágenes IA**\n\nEscribe qué quieres que dibuje (ej. 'Un gato ciberpunk' o 'Un hermoso atardecer').",
        'generating': "🎨 Pintando tu obra maestra... Por favor espera ⏳",
        'ask_yt': "🔴 Por favor pega tu enlace de **YouTube** abajo:",
        'ask_ig': "📸 Por favor pega tu enlace de **Instagram** abajo:",
        'ask_tt': "🎵 Por favor pega tu enlace de **TikTok** abajo:",
        'invalid_yt': "❌ Ese no parece un enlace de YouTube. Inténtalo de nuevo:",
        'invalid_ig': "❌ Ese no parece un enlace de Instagram. Inténtalo de nuevo:",
        'invalid_tt': "❌ Ese no parece un enlace de TikTok. Inténtalo de nuevo:",
        'error': "❌ Error:",
        'btn_help': "Ayuda ℹ️",
        'btn_lang': "Idioma 🌐",
        'btn_image': "Imagen IA 🎨",
        'btn_back': "Volver 🔙"
    }
}

def get_text(user_id, key):
    lang = user_languages.get(user_id, 'en')
    return TEXTS[lang][key]

# --- 3. MENU GENERATORS ---
def main_menu_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("YouTube 🔴", callback_data='ask_yt'),
         InlineKeyboardButton("Instagram 📸", callback_data='ask_ig'),
         InlineKeyboardButton("TikTok 🎵", callback_data='ask_tt')],
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
    user_states[user_id] = None 
    await update.message.reply_text(get_text(user_id, 'main_menu'), reply_markup=main_menu_keyboard(user_id))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    text_lower = text.lower()
    state = user_states.get(user_id)

    # --- AI IMAGE GENERATOR ---
    if state == 'waiting_for_image':
        user_states[user_id] = None 
        msg = await update.message.reply_text(get_text(user_id, 'generating'))
        try:
            safe_prompt = urllib.parse.quote(text)
            image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1920&height=1080&nologo=true"
            response = requests.get(image_url)
            image_filename = f"{user_id}_ai.jpg"
            with open(image_filename, 'wb') as f:
                f.write(response.content)
            with open(image_filename, 'rb') as photo:
                await context.bot.send_photo(chat_id=user_id, photo=photo, caption=f"🎨 {text}")
            os.remove(image_filename) 
            await msg.delete() 
            await update.message.reply_text(get_text(user_id, 'main_menu'), reply_markup=main_menu_keyboard(user_id))
        except Exception as e:
            await msg.edit_text(f"{get_text(user_id, 'error')} {str(e)}")

    # --- STRICT LINK VALIDATION (THE FIX) ---
    elif state in ['waiting_for_yt', 'waiting_for_ig', 'waiting_for_tt']:
        
        # Check if the user pasted a YouTube link in the YouTube section
        if state == 'waiting_for_yt' and not ('youtube.com' in text_lower or 'youtu.be' in text_lower):
            await update.message.reply_text(get_text(user_id, 'invalid_yt'), reply_markup=back_keyboard(user_id))
            return
            
        # Check if the user pasted an IG link in the IG section
        elif state == 'waiting_for_ig' and 'instagram.com' not in text_lower:
            await update.message.reply_text(get_text(user_id, 'invalid_ig'), reply_markup=back_keyboard(user_id))
            return
            
        # Check if the user pasted a TT link in the TikTok section
        elif state == 'waiting_for_tt' and 'tiktok.com' not in text_lower:
            await update.message.reply_text(get_text(user_id, 'invalid_tt'), reply_markup=back_keyboard(user_id))
            return

        # If it passes the check, proceed to download formats!
        user_states[user_id] = None 
        context.user_data['last_link'] = text 
        keyboard = [
            [InlineKeyboardButton("🎬 Video (Best Quality)", callback_data='dl_mp4_best')],
            [InlineKeyboardButton("📱 Video (Low Quality)", callback_data='dl_mp4_low')],
            [InlineKeyboardButton("🎵 Audio Only (MP3)", callback_data='dl_mp3')],
            [InlineKeyboardButton(get_text(user_id, 'btn_back'), callback_data='show_main')]
        ]
        await update.message.reply_text(get_text(user_id, 'choose_format'), reply_markup=InlineKeyboardMarkup(keyboard))
        
    # --- IF THEY SEND A LINK WITHOUT CLICKING A BUTTON FIRST ---
    elif "http://" in text or "https://" in text:
        context.user_data['last_link'] = text 
        keyboard = [
            [InlineKeyboardButton("🎬 Video (Best Quality)", callback_data='dl_mp4_best')],
            [InlineKeyboardButton("📱 Video (Low Quality)", callback_data='dl_mp4_low')],
            [InlineKeyboardButton("🎵 Audio Only (MP3)", callback_data='dl_mp3')],
            [InlineKeyboardButton(get_text(user_id, 'btn_back'), callback_data='show_main')]
        ]
        await update.message.reply_text(get_text(user_id, 'choose_format'), reply_markup=InlineKeyboardMarkup(keyboard))

    # --- UNKNOWN MESSAGES ---
    else:
        await update.message.reply_text(get_text(user_id, 'main_menu'), reply_markup=main_menu_keyboard(user_id))


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # --- Menu Navigation ---
    if query.data == 'show_main':
        user_states[user_id] = None 
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

    # --- Platform Link Requests (Sets the State) ---
    elif query.data == 'ask_yt':
        user_states[user_id] = 'waiting_for_yt' # BOT NOW REMEMBERS YOU CLICKED YOUTUBE
        await query.edit_message_text(get_text(user_id, 'ask_yt'), reply_markup=back_keyboard(user_id))
        
    elif query.data == 'ask_ig':
        user_states[user_id] = 'waiting_for_ig' # BOT NOW REMEMBERS YOU CLICKED IG
        await query.edit_message_text(get_text(user_id, 'ask_ig'), reply_markup=back_keyboard(user_id))
        
    elif query.data == 'ask_tt':
        user_states[user_id] = 'waiting_for_tt' # BOT NOW REMEMBERS YOU CLICKED TIKTOK
        await query.edit_message_text(get_text(user_id, 'ask_tt'), reply_markup=back_keyboard(user_id))

    # --- Start AI Image Process ---
    elif query.data == 'ask_image':
        user_states[user_id] = 'waiting_for_image' 
        await query.edit_message_text(get_text(user_id, 'ask_prompt'), reply_markup=back_keyboard(user_id))

    # --- Language Selection ---
    elif query.data in ['lang_en', 'lang_es']:
        user_languages[user_id] = query.data.split('_')[1]
        new_text = get_text(user_id, 'lang_set') + get_text(user_id, 'main_menu')
        await query.edit_message_text(new_text, reply_markup=main_menu_keyboard(user_id))

    # --- Download Media ---
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
            error_msg = f"{get_text(user_id, 'error')} {str(e)}"
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
