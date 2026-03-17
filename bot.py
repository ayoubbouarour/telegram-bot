import os
import glob
import yt_dlp
import requests
import imageio_ffmpeg
import urllib.parse
from threading import Thread
from flask import Flask
from gtts import gTTS
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

# Massive Translation Dictionary
TEXTS = {
    'en': {
        'main_menu': "🤖 **Welcome to the Super Bot!**\n\nChoose an option from the menu below:",
        'help_text': "📖 **How to use me:**\n\n📥 **Download:** Click a social media button and paste your link.\n🎨 **AI Image:** Tell me what to draw.\n🔳 **QR Code:** Turn any text/link into a QR code.\n🗣️ **Voice Maker:** Type text, and I will speak it out loud!",
        'choose_lang': "🌐 Please choose your language:",
        'lang_set': "✅ Language set to English!\n\n",
        'choose_format': "🔗 Link detected! Choose your format:",
        'downloading': "Downloading... please wait ⏳",
        'ask_prompt': "🎨 **AI Image Maker**\n\nType a description of what you want me to draw.",
        'generating': "🎨 Painting your masterpiece... Please wait ⏳",
        'ask_yt': "🔴 Please paste your **YouTube** link below:",
        'ask_ig': "📸 Please paste your **Instagram** link below:",
        'ask_tt': "🎵 Please paste your **TikTok** link below:",
        'invalid_yt': "❌ That doesn't look like a YouTube link. Try again:",
        'invalid_ig': "❌ That doesn't look like an Instagram link. Try again:",
        'invalid_tt': "❌ That doesn't look like a TikTok link. Try again:",
        'ask_qr': "🔳 **QR Code Generator**\n\nSend me any text or link, and I will turn it into a QR code!",
        'ask_tts': "🗣️ **Voice Maker**\n\nSend me any text, and I will read it out loud for you!",
        'error': "❌ Error:",
        'btn_help': "Help ℹ️", 'btn_lang': "Language 🌐", 'btn_image': "AI Image 🎨",
        'btn_qr': "QR Code 🔳", 'btn_tts': "Voice Maker 🗣️", 'btn_back': "Back 🔙"
    },
    'es': {
        'main_menu': "🤖 **¡Bienvenido al Súper Bot!**\n\nElige una opción del menú de abajo:",
        'help_text': "📖 **Cómo usarme:**\n\n📥 **Descargar:** Haz clic en una red social y pega tu enlace.\n🎨 **Imagen IA:** Dime qué dibujar.\n🔳 **Código QR:** Convierte texto/enlace en un QR.\n🗣️ **Voz:** ¡Escribe texto y lo leeré en voz alta!",
        'choose_lang': "🌐 Por favor, elige tu idioma:", 'lang_set': "✅ ¡Idioma cambiado a Español!\n\n",
        'choose_format': "🔗 ¡Enlace detectado! Elige el formato:", 'downloading': "Descargando... por favor espera ⏳",
        'ask_prompt': "🎨 **Creador de Imágenes IA**\n\nEscribe qué quieres que dibuje.",
        'generating': "🎨 Pintando tu obra maestra... Por favor espera ⏳",
        'ask_yt': "🔴 Pega tu enlace de **YouTube** abajo:", 'ask_ig': "📸 Pega tu enlace de **Instagram** abajo:", 'ask_tt': "🎵 Pega tu enlace de **TikTok** abajo:",
        'invalid_yt': "❌ Ese no parece un enlace de YouTube. Inténtalo de nuevo:", 'invalid_ig': "❌ Ese no parece un enlace de Instagram. Inténtalo de nuevo:", 'invalid_tt': "❌ Ese no parece un enlace de TikTok. Inténtalo de nuevo:",
        'ask_qr': "🔳 **Generador QR**\n\n¡Envíame cualquier texto o enlace y lo convertiré en un QR!",
        'ask_tts': "🗣️ **Creador de Voz**\n\n¡Envíame un texto y lo leeré en voz alta!",
        'error': "❌ Error:", 'btn_help': "Ayuda ℹ️", 'btn_lang': "Idioma 🌐", 'btn_image': "Imagen IA 🎨", 'btn_qr': "Código QR 🔳", 'btn_tts': "Voz IA 🗣️", 'btn_back': "Volver 🔙"
    },
    'fr': {
        'main_menu': "🤖 **Bienvenue sur le Super Bot !**\n\nChoisissez une option ci-dessous :",
        'help_text': "📖 **Comment m'utiliser :**\n\n📥 **Télécharger:** Cliquez sur un réseau social et collez votre lien.\n🎨 **Image IA:** Dites-moi quoi dessiner.\n🔳 **Code QR:** Transformez n'importe quel texte/lien en QR.\n🗣️ **Voix:** Tapez un texte et je le lirai !",
        'choose_lang': "🌐 Choisissez votre langue :", 'lang_set': "✅ Langue configurée sur Français !\n\n",
        'choose_format': "🔗 Lien détecté ! Choisissez le format :", 'downloading': "Téléchargement... veuillez patienter ⏳",
        'ask_prompt': "🎨 **Créateur d'Image IA**\n\nDécrivez ce que vous voulez que je dessine.",
        'generating': "🎨 Création de votre chef-d'œuvre... Patientez ⏳",
        'ask_yt': "🔴 Collez votre lien **YouTube** ci-dessous :", 'ask_ig': "📸 Collez votre lien **Instagram** ci-dessous :", 'ask_tt': "🎵 Collez votre lien **TikTok** ci-dessous :",
        'invalid_yt': "❌ Ce n'est pas un lien YouTube. Réessayez :", 'invalid_ig': "❌ Ce n'est pas un lien Instagram. Réessayez :", 'invalid_tt': "❌ Ce n'est pas un lien TikTok. Réessayez :",
        'ask_qr': "🔳 **Générateur QR**\n\nEnvoyez-moi un texte ou un lien pour créer un QR code !",
        'ask_tts': "🗣️ **Créateur de Voix**\n\nEnvoyez-moi un texte et je le lirai à voix haute !",
        'error': "❌ Erreur :", 'btn_help': "Aide ℹ️", 'btn_lang': "Langue 🌐", 'btn_image': "Image IA 🎨", 'btn_qr': "Code QR 🔳", 'btn_tts': "Voix IA 🗣️", 'btn_back': "Retour 🔙"
    },
    'pt': {
        'main_menu': "🤖 **Bem-vindo ao Super Bot!**\n\nEscolha uma opção no menu abaixo:",
        'help_text': "📖 **Como me usar:**\n\n📥 **Baixar:** Clique em uma rede social e cole o link.\n🎨 **Imagem IA:** Diga o que desenhar.\n🔳 **Código QR:** Transforme texto/link em um QR.\n🗣️ **Voz:** Digite algo e eu falarei em voz alta!",
        'choose_lang': "🌐 Escolha seu idioma:", 'lang_set': "✅ Idioma definido para Português!\n\n",
        'choose_format': "🔗 Link detectado! Escolha o formato:", 'downloading': "Baixando... por favor aguarde ⏳",
        'ask_prompt': "🎨 **Criador de Imagem IA**\n\nDescreva o que deseja que eu desenhe.",
        'generating': "🎨 Pintando sua obra-prima... Aguarde ⏳",
        'ask_yt': "🔴 Cole seu link do **YouTube** abaixo:", 'ask_ig': "📸 Cole seu link do **Instagram** abaixo:", 'ask_tt': "🎵 Cole seu link do **TikTok** abaixo:",
        'invalid_yt': "❌ Isso não parece um link do YouTube. Tente novamente:", 'invalid_ig': "❌ Isso não parece um link do Instagram. Tente novamente:", 'invalid_tt': "❌ Isso não parece um link do TikTok. Tente novamente:",
        'ask_qr': "🔳 **Gerador QR**\n\nEnvie qualquer texto ou link e eu farei um código QR!",
        'ask_tts': "🗣️ **Criador de Voz**\n\nEnvie um texto e eu lerei em voz alta!",
        'error': "❌ Erro:", 'btn_help': "Ajuda ℹ️", 'btn_lang': "Idioma 🌐", 'btn_image': "Imagem IA 🎨", 'btn_qr': "Código QR 🔳", 'btn_tts': "Voz IA 🗣️", 'btn_back': "Voltar 🔙"
    },
    'ar': {
        'main_menu': "🤖 **مرحباً بك في الروبوت الخارق!**\n\nاختر خياراً من القائمة أدناه:",
        'help_text': "📖 **كيف تستخدم الروبوت:**\n\n📥 **للتحميل:** انقر فوق شبكة اجتماعية والصق الرابط.\n🎨 **صورة الذكاء الاصطناعي:** أخبرني ماذا أرسم.\n🔳 **رمز QR:** تحويل أي نص/رابط إلى رمز استجابة سريعة.\n🗣️ **الصوت:** اكتب نصاً وسأقرأه بصوت عالٍ!",
        'choose_lang': "🌐 يرجى اختيار لغتك:", 'lang_set': "✅ تم تعيين اللغة إلى العربية!\n\n",
        'choose_format': "🔗 تم اكتشاف رابط! اختر التنسيق:", 'downloading': "جاري التنزيل... يرجى الانتظار ⏳",
        'ask_prompt': "🎨 **صانع صور الذكاء الاصطناعي**\n\nاكتب وصفًا لما تريدني أن أرسمه.",
        'generating': "🎨 جاري رسم تحفتك الفنية... يرجى الانتظار ⏳",
        'ask_yt': "🔴 يرجى لصق رابط **يوتيوب** أدناه:", 'ask_ig': "📸 يرجى لصق رابط **إنستغرام** أدناه:", 'ask_tt': "🎵 يرجى لصق رابط **تيك توك** أدناه:",
        'invalid_yt': "❌ هذا لا يبدو كرابط يوتيوب. حاول مرة أخرى:", 'invalid_ig': "❌ هذا لا يبدو كرابط إنستغرام. حاول مرة أخرى:", 'invalid_tt': "❌ هذا لا يبدو كرابط تيك توك. حاول مرة أخرى:",
        'ask_qr': "🔳 **مولد رمز QR**\n\nأرسل لي أي نص أو رابط وسأحوله إلى رمز استجابة سريعة!",
        'ask_tts': "🗣️ **صانع الصوت**\n\nأرسل لي نصاً وسأقرأه بصوت عالٍ من أجلك!",
        'error': "❌ خطأ:", 'btn_help': "مساعدة ℹ️", 'btn_lang': "اللغة 🌐", 'btn_image': "صورة ذكاء اصطناعي 🎨", 'btn_qr': "رمز QR 🔳", 'btn_tts': "صوت 🗣️", 'btn_back': "رجوع 🔙"
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
        [InlineKeyboardButton(get_text(user_id, 'btn_image'), callback_data='ask_image'),
         InlineKeyboardButton(get_text(user_id, 'btn_qr'), callback_data='ask_qr'),
         InlineKeyboardButton(get_text(user_id, 'btn_tts'), callback_data='ask_tts')],
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
    lang_code = user_languages.get(user_id, 'en')

    # --- QR CODE MAKER ---
    if state == 'waiting_for_qr':
        user_states[user_id] = None 
        safe_text = urllib.parse.quote(text)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=512x512&data={safe_text}"
        await context.bot.send_photo(chat_id=user_id, photo=qr_url, caption="✅ QR Code")
        await update.message.reply_text(get_text(user_id, 'main_menu'), reply_markup=main_menu_keyboard(user_id))

    # --- TEXT TO SPEECH (VOICE MAKER) ---
    elif state == 'waiting_for_tts':
        user_states[user_id] = None 
        try:
            tts = gTTS(text=text, lang=lang_code)
            filename = f"{user_id}_voice.mp3"
            tts.save(filename)
            with open(filename, 'rb') as voice:
                await context.bot.send_voice(chat_id=user_id, voice=voice)
            os.remove(filename)
        except Exception as e:
            await update.message.reply_text(f"{get_text(user_id, 'error')} {str(e)}")
        await update.message.reply_text(get_text(user_id, 'main_menu'), reply_markup=main_menu_keyboard(user_id))

    # --- AI IMAGE GENERATOR ---
    elif state == 'waiting_for_image':
        user_states[user_id] = None 
        msg = await update.message.reply_text(get_text(user_id, 'generating'))
        try:
            safe_prompt = urllib.parse.quote(text)
            image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1920&height=1080&nologo=true"
            response = requests.get(image_url)
            image_filename = f"{user_id}_ai.jpg"
            with open(image_filename, 'wb') as f: f.write(response.content)
            with open(image_filename, 'rb') as photo:
                await context.bot.send_photo(chat_id=user_id, photo=photo, caption=f"🎨 {text}")
            os.remove(image_filename) 
            await msg.delete() 
            await update.message.reply_text(get_text(user_id, 'main_menu'), reply_markup=main_menu_keyboard(user_id))
        except Exception as e:
            await msg.edit_text(f"{get_text(user_id, 'error')} {str(e)}")

    # --- STRICT LINK VALIDATION ---
    elif state in ['waiting_for_yt', 'waiting_for_ig', 'waiting_for_tt']:
        if state == 'waiting_for_yt' and not ('youtube.com' in text_lower or 'youtu.be' in text_lower):
            await update.message.reply_text(get_text(user_id, 'invalid_yt'), reply_markup=back_keyboard(user_id))
            return
        elif state == 'waiting_for_ig' and 'instagram.com' not in text_lower:
            await update.message.reply_text(get_text(user_id, 'invalid_ig'), reply_markup=back_keyboard(user_id))
            return
        elif state == 'waiting_for_tt' and 'tiktok.com' not in text_lower:
            await update.message.reply_text(get_text(user_id, 'invalid_tt'), reply_markup=back_keyboard(user_id))
            return

        user_states[user_id] = None 
        context.user_data['last_link'] = text 
        keyboard = [
            [InlineKeyboardButton("🎬 Video (Best)", callback_data='dl_mp4_best'), InlineKeyboardButton("📱 Video (Low)", callback_data='dl_mp4_low')],
            [InlineKeyboardButton("🎵 Audio (MP3)", callback_data='dl_mp3'), InlineKeyboardButton(get_text(user_id, 'btn_back'), callback_data='show_main')]
        ]
        await update.message.reply_text(get_text(user_id, 'choose_format'), reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif "http://" in text or "https://" in text:
        context.user_data['last_link'] = text 
        keyboard = [
            [InlineKeyboardButton("🎬 Video (Best)", callback_data='dl_mp4_best'), InlineKeyboardButton("📱 Video (Low)", callback_data='dl_mp4_low')],
            [InlineKeyboardButton("🎵 Audio (MP3)", callback_data='dl_mp3'), InlineKeyboardButton(get_text(user_id, 'btn_back'), callback_data='show_main')]
        ]
        await update.message.reply_text(get_text(user_id, 'choose_format'), reply_markup=InlineKeyboardMarkup(keyboard))

    else:
        await update.message.reply_text(get_text(user_id, 'main_menu'), reply_markup=main_menu_keyboard(user_id))


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == 'show_main':
        user_states[user_id] = None 
        await query.edit_message_text(get_text(user_id, 'main_menu'), reply_markup=main_menu_keyboard(user_id))
        
    elif query.data == 'show_help':
        await query.edit_message_text(get_text(user_id, 'help_text'), reply_markup=back_keyboard(user_id))
        
    elif query.data == 'show_lang':
        keyboard = [
            [InlineKeyboardButton("English 🇬🇧", callback_data='lang_en'), InlineKeyboardButton("Español 🇪🇸", callback_data='lang_es')],
            [InlineKeyboardButton("Français 🇫🇷", callback_data='lang_fr'), InlineKeyboardButton("Português 🇧🇷", callback_data='lang_pt')],
            [InlineKeyboardButton("العربية 🇸🇦", callback_data='lang_ar')],
            [InlineKeyboardButton(get_text(user_id, 'btn_back'), callback_data='show_main')]
        ]
        await query.edit_message_text(get_text(user_id, 'choose_lang'), reply_markup=InlineKeyboardMarkup(keyboard))

    # New Tool Buttons
    elif query.data == 'ask_qr':
        user_states[user_id] = 'waiting_for_qr'
        await query.edit_message_text(get_text(user_id, 'ask_qr'), reply_markup=back_keyboard(user_id))
        
    elif query.data == 'ask_tts':
        user_states[user_id] = 'waiting_for_tts'
        await query.edit_message_text(get_text(user_id, 'ask_tts'), reply_markup=back_keyboard(user_id))

    elif query.data == 'ask_yt':
        user_states[user_id] = 'waiting_for_yt' 
        await query.edit_message_text(get_text(user_id, 'ask_yt'), reply_markup=back_keyboard(user_id))
    elif query.data == 'ask_ig':
        user_states[user_id] = 'waiting_for_ig' 
        await query.edit_message_text(get_text(user_id, 'ask_ig'), reply_markup=back_keyboard(user_id))
    elif query.data == 'ask_tt':
        user_states[user_id] = 'waiting_for_tt' 
        await query.edit_message_text(get_text(user_id, 'ask_tt'), reply_markup=back_keyboard(user_id))
    elif query.data == 'ask_image':
        user_states[user_id] = 'waiting_for_image' 
        await query.edit_message_text(get_text(user_id, 'ask_prompt'), reply_markup=back_keyboard(user_id))

    # Languages Setup
    elif query.data.startswith('lang_'):
        user_languages[user_id] = query.data.split('_')[1] # Gets 'en', 'es', 'fr', 'pt', or 'ar'
        new_text = get_text(user_id, 'lang_set') + get_text(user_id, 'main_menu')
        await query.edit_message_text(new_text, reply_markup=main_menu_keyboard(user_id))

    elif query.data.startswith('dl_'):
        link = context.user_data.get('last_link')
        if not link: return
            
        await query.edit_message_text(get_text(user_id, 'downloading'))
        for old_file in glob.glob(f"{user_id}_media*"):
            if os.path.exists(old_file): os.remove(old_file)

        ydl_opts = {
            'ffmpeg_location': FFMPEG_PATH, 
            'outtmpl': f'{user_id}_media.%(ext)s', 'noplaylist': True, 'quiet': True,
            'extractor_args': {'youtube': ['player_client=ios']}, 
        }
        
        if query.data == 'dl_mp4_best': ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif query.data == 'dl_mp4_low': ydl_opts['format'] = 'worst[ext=mp4]/worst'
        elif query.data == 'dl_mp3':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([link])
            downloaded_files = glob.glob(f"{user_id}_media*")
            if downloaded_files:
                final_file = downloaded_files[0]
                if query.data == 'dl_mp3':
                    with open(final_file, 'rb') as audio: await context.bot.send_audio(chat_id=user_id, audio=audio)
                else:
                    with open(final_file, 'rb') as video: await context.bot.send_video(chat_id=user_id, video=video)
            else: raise Exception("Could not locate the downloaded file.")
        except Exception as e: await context.bot.send_message(chat_id=user_id, text=f"{get_text(user_id, 'error')} {str(e)}")
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
