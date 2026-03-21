"""
Super Bot — Telegram multi-tool bot
══════════════════════════════════════════════════════════════
HOW DOWNLOADS WORK
  • Platform buttons (YouTube/Instagram/TikTok/Facebook/Twitter/SoundCloud)
    show in the main menu. Tapping one asks for the link, then shows a
    Video / Audio choice before downloading.
  • Pasting a raw link directly also works — skips straight to format picker.
  • Cobalt API handles all downloads (no yt-dlp required).

SETUP
  BOT_TOKEN  — your Telegram bot token (required)
  ADMIN_IDS  — comma-separated Telegram user IDs for /broadcast (optional)
══════════════════════════════════════════════════════════════
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
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN       = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")
ADMIN_IDS   = {int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()}
MAX_FILE_MB = 50
RATE_LIMIT  = 15
RATE_WINDOW = 30
USERS_FILE  = "users.txt" # Saves users to a file for persistent broadcasts

# ══════════════════════════════════════════════════════════
# 2.  KEEP-ALIVE
# ══════════════════════════════════════════════════════════
_flask = Flask(__name__)

@_flask.route("/")
def _home():
    return "Bot is awake!"

def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    Thread(target=lambda: _flask.run(host="0.0.0.0", port=port), daemon=True).start()

# ══════════════════════════════════════════════════════════
# 3.  IN-MEMORY STATE & PERSISTENT USERS
# ══════════════════════════════════════════════════════════
user_languages: dict[int, str]         = {}
user_states:    dict[int, str | None]  = {}
_rate_buckets:  dict[int, list[float]] = defaultdict(list)

def is_rate_limited(uid: int) -> bool:
    now = time.monotonic()
    _rate_buckets[uid] =[ts for ts in _rate_buckets[uid] if now - ts < RATE_WINDOW]
    if len(_rate_buckets[uid]) >= RATE_LIMIT:
        return True
    _rate_buckets[uid].append(now)
    return False

def save_user(uid: int):
    """Saves user ID to a file so broadcast doesn't break on restart."""
    users = set()
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            users = {int(line.strip()) for line in f if line.strip().isdigit()}
    if uid not in users:
        with open(USERS_FILE, "a") as f:
            f.write(f"{uid}\n")

def get_all_users() -> set[int]:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return {int(line.strip()) for line in f if line.strip().isdigit()}
    return set()

# ══════════════════════════════════════════════════════════
# 4.  LINK VALIDATION
# ══════════════════════════════════════════════════════════
PLATFORM_VALIDATORS: dict[str, tuple[list[str], str]] = {
    "waiting_for_yt": (["youtube.com", "youtu.be"],             "invalid_yt"),
    "waiting_for_ig": (["instagram.com"],                        "invalid_ig"),
    "waiting_for_tt": (["tiktok.com", "vm.tiktok.com"],         "invalid_tt"),
    "waiting_for_fb": (["facebook.com", "fb.watch", "fb.com"],  "invalid_fb"),
    "waiting_for_tw": (["twitter.com", "x.com", "t.co"],        "invalid_tw"),
    "waiting_for_sc": (["soundcloud.com"],                       "invalid_sc"),
}

def _valid_platform_link(state: str, url: str) -> bool:
    domains, _ = PLATFORM_VALIDATORS[state]
    return any(d in url.lower() for d in domains)

# ══════════════════════════════════════════════════════════
# 5.  TRANSLATIONS  (EN / ES / FR / PT / AR)
# ══════════════════════════════════════════════════════════
TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "main_menu":       "🤖 *Super Bot*\n\nTap a platform to download, or paste any link directly:",
        "tools_menu":      "🛠 *More Tools*\n\nChoose a tool:",
        "help_text": (
            "📖 *How to use me:*\n\n"
            "📥 *Download:* Tap a platform button _or_ just paste a link.\n"
            "🎬 *Video / 🎵 Audio:* Choose your format after pasting.\n"
            "🎨 *AI Image:* Describe what to draw.\n"
            "🔳 *QR Code:* Text or link → QR image.\n"
            "🗣️ *Voice:* Text → audio message.\n"
            "🔗 *Short URL:* Shorten any link.\n"
            "⛅ *Weather:* Type a city name.\n"
            "💱 *Currency:* e.g. `100 USD to EUR`"
        ),
        "choose_lang":     "🌐 Choose your language:",
        "lang_set":        "✅ Language set to English!\n\n",
        "ask_yt":          "🔴 *YouTube Downloader*\n\nPaste your YouTube link:",
        "ask_ig":          "📸 *Instagram Downloader*\n\nPaste your Instagram link:",
        "ask_tt":          "🎵 *TikTok Downloader*\n\nPaste your TikTok link:",
        "ask_fb":          "🔵 *Facebook Downloader*\n\nPaste your Facebook link:",
        "ask_tw":          "🐦 *Twitter/X Downloader*\n\nPaste your Twitter/X link:",
        "ask_sc":          "🎧 *SoundCloud Downloader*\n\nPaste your SoundCloud link:",
        "invalid_yt":      "❌ That doesn't look like a YouTube link. Try again:",
        "invalid_ig":      "❌ That doesn't look like an Instagram link. Try again:",
        "invalid_tt":      "❌ That doesn't look like a TikTok link. Try again:",
        "invalid_fb":      "❌ That doesn't look like a Facebook link. Try again:",
        "invalid_tw":      "❌ That doesn't look like a Twitter/X link. Try again:",
        "invalid_sc":      "❌ That doesn't look like a SoundCloud link. Try again:",
        "choose_format":   "✅ Link saved! Choose format:",
        "ask_image":       "🎨 *AI Image Maker*\n\nDescribe what you want drawn.",
        "ask_qr":          "🔳 *QR Generator*\n\nSend any text or link:",
        "ask_tts":         "🗣️ *Voice Maker*\n\nSend any text to read aloud:",
        "ask_shorten":     "🔗 *URL Shortener*\n\nPaste the link you want shortened:",
        "ask_weather":     "⛅ *Weather*\n\nType a city name (e.g. `London`):",
        "ask_currency":    "💱 *Currency Converter*\n\nType like: `100 USD to EUR`",
        "generating":      "🎨 Generating image… please wait",
        "auto_detect":     "🔗 Link detected! Processing…",
        "uploading":       "✅ Done! Uploading to Telegram…",
        "error":           "❌ Error:",
        "file_too_large":  "❌ File exceeds Telegram's 50 MB limit. Try a shorter clip.",
        "rate_limited":    "⏳ Please slow down a little.",
        "not_admin":       "🚫 Admins only.",
        "broadcast_usage": "Usage: /broadcast <message>",
        "broadcast_done":  "✅ Sent to {n} users.",
        "invalid_currency":"❌ Format not recognised. Try: `100 USD to EUR`",
        "btn_help":     "Help ℹ️",        "btn_lang":     "Language 🌐",
        "btn_image":    "AI Image 🎨",    "btn_qr":       "QR Code 🔳",
        "btn_tts":      "Voice 🗣️",       "btn_back":     "◀ Back",
        "btn_tools":    "More Tools 🛠",   "btn_shorten":  "Short URL 🔗",
        "btn_weather":  "Weather ⛅",      "btn_currency": "Currency 💱",
    },
    "es": {
        "main_menu":       "🤖 *Súper Bot*\n\nPulsa una plataforma o pega un enlace directamente:",
        "tools_menu":      "🛠 *Más Herramientas*\n\nElige una herramienta:",
        "help_text": (
            "📖 *Cómo usarme:*\n\n"
            "📥 *Descargar:* Pulsa un botón de plataforma _o_ pega un enlace.\n"
            "🎬 *Vídeo / 🎵 Audio:* Elige el formato tras pegar.\n"
            "🎨 *Imagen IA:* Describe qué dibujar.\n"
            "🔳 *QR:* Texto/enlace → imagen QR.\n"
            "🗣️ *Voz:* Texto → mensaje de audio.\n"
            "🔗 *Acortar URL:* Acorta cualquier enlace.\n"
            "⛅ *Clima:* Escribe una ciudad.\n"
            "💱 *Moneda:* p.ej. `100 USD to EUR`"
        ),
        "choose_lang":     "🌐 Elige tu idioma:",
        "lang_set":        "✅ ¡Idioma cambiado a Español!\n\n",
        "ask_yt":          "🔴 *Descargador YouTube*\n\nPega tu enlace de YouTube:",
        "ask_ig":          "📸 *Descargador Instagram*\n\nPega tu enlace de Instagram:",
        "ask_tt":          "🎵 *Descargador TikTok*\n\nPega tu enlace de TikTok:",
        "ask_fb":          "🔵 *Descargador Facebook*\n\nPega tu enlace de Facebook:",
        "ask_tw":          "🐦 *Descargador Twitter/X*\n\nPega tu enlace de Twitter/X:",
        "ask_sc":          "🎧 *Descargador SoundCloud*\n\nPega tu enlace de SoundCloud:",
        "invalid_yt":      "❌ No parece un enlace de YouTube. Inténtalo de nuevo:",
        "invalid_ig":      "❌ No parece un enlace de Instagram. Inténtalo de nuevo:",
        "invalid_tt":      "❌ No parece un enlace de TikTok. Inténtalo de nuevo:",
        "invalid_fb":      "❌ No parece un enlace de Facebook. Inténtalo de nuevo:",
        "invalid_tw":      "❌ No parece un enlace de Twitter/X. Inténtalo de nuevo:",
        "invalid_sc":      "❌ No parece un enlace de SoundCloud. Inténtalo de nuevo:",
        "choose_format":   "✅ ¡Enlace guardado! Elige el formato:",
        "ask_image":       "🎨 *Creador de Imágenes IA*\n\nDescribe qué quieres dibujar.",
        "ask_qr":          "🔳 *Generador QR*\n\nEnvía texto o un enlace:",
        "ask_tts":         "🗣️ *Creador de Voz*\n\nEnvía texto para leer en voz alta:",
        "ask_shorten":     "🔗 *Acortador de URL*\n\nPega el enlace a acortar:",
        "ask_weather":     "⛅ *Clima*\n\nEscribe el nombre de una ciudad:",
        "ask_currency":    "💱 *Conversor de Moneda*\n\nEscribe: `100 USD to EUR`",
        "generating":      "🎨 Generando imagen… espera",
        "auto_detect":     "🔗 ¡Enlace detectado! Procesando…",
        "uploading":       "✅ ¡Listo! Subiendo a Telegram…",
        "error":           "❌ Error:",
        "file_too_large":  "❌ El archivo supera el límite de 50 MB de Telegram.",
        "rate_limited":    "⏳ Ve un poco más despacio.",
        "not_admin":       "🚫 Solo administradores.",
        "broadcast_usage": "Uso: /broadcast <mensaje>",
        "broadcast_done":  "✅ Enviado a {n} usuarios.",
        "invalid_currency":"❌ Formato no reconocido. Prueba: `100 USD to EUR`",
        "btn_help":     "Ayuda ℹ️",       "btn_lang":     "Idioma 🌐",
        "btn_image":    "Imagen IA 🎨",   "btn_qr":       "Código QR 🔳",
        "btn_tts":      "Voz 🗣️",         "btn_back":     "◀ Volver",
        "btn_tools":    "Más Herramientas 🛠", "btn_shorten": "Acortar URL 🔗",
        "btn_weather":  "Clima ⛅",        "btn_currency": "Moneda 💱",
    },
    "fr": {
        "main_menu":       "🤖 *Super Bot*\n\nAppuyez sur une plateforme ou collez un lien directement :",
        "tools_menu":      "🛠 *Plus d'Outils*\n\nChoisissez un outil :",
        "help_text": (
            "📖 *Comment m'utiliser :*\n\n"
            "📥 *Télécharger :* Appuyez sur un bouton _ou_ collez un lien.\n"
            "🎬 *Vidéo / 🎵 Audio :* Choisissez le format après avoir collé.\n"
            "🎨 *Image IA :* Décrivez ce à dessiner.\n"
            "🔳 *QR :* Texte/lien → image QR.\n"
            "🗣️ *Voix :* Texte → message audio.\n"
            "🔗 *Raccourcir URL.*\n"
            "⛅ *Météo :* Tapez une ville.\n"
            "💱 *Monnaie :* ex. `100 USD to EUR`"
        ),
        "choose_lang":     "🌐 Choisissez votre langue :",
        "lang_set":        "✅ Langue réglée sur Français !\n\n",
        "ask_yt":          "🔴 *Téléchargeur YouTube*\n\nCollez votre lien YouTube :",
        "ask_ig":          "📸 *Téléchargeur Instagram*\n\nCollez votre lien Instagram :",
        "ask_tt":          "🎵 *Téléchargeur TikTok*\n\nCollez votre lien TikTok :",
        "ask_fb":          "🔵 *Téléchargeur Facebook*\n\nCollez votre lien Facebook :",
        "ask_tw":          "🐦 *Téléchargeur Twitter/X*\n\nCollez votre lien Twitter/X :",
        "ask_sc":          "🎧 *Téléchargeur SoundCloud*\n\nCollez votre lien SoundCloud :",
        "invalid_yt":      "❌ Ce n'est pas un lien YouTube. Réessayez :",
        "invalid_ig":      "❌ Ce n'est pas un lien Instagram. Réessayez :",
        "invalid_tt":      "❌ Ce n'est pas un lien TikTok. Réessayez :",
        "invalid_fb":      "❌ Ce n'est pas un lien Facebook. Réessayez :",
        "invalid_tw":      "❌ Ce n'est pas un lien Twitter/X. Réessayez :",
        "invalid_sc":      "❌ Ce n'est pas un lien SoundCloud. Réessayez :",
        "choose_format":   "✅ Lien enregistré ! Choisissez le format :",
        "ask_image":       "🎨 *Créateur d'Image IA*\n\nDécrivez ce à dessiner.",
        "ask_qr":          "🔳 *Générateur QR*\n\nEnvoyez texte ou lien :",
        "ask_tts":         "🗣️ *Créateur de Voix*\n\nEnvoyez du texte à lire :",
        "ask_shorten":     "🔗 *Raccourcisseur d'URL*\n\nCollez le lien à raccourcir :",
        "ask_weather":     "⛅ *Météo*\n\nTapez un nom de ville :",
        "ask_currency":    "💱 *Convertisseur de Devise*\n\nEx : `100 USD to EUR`",
        "generating":      "🎨 Génération d'image… patientez",
        "auto_detect":     "🔗 Lien détecté ! Traitement…",
        "uploading":       "✅ Terminé ! Envoi vers Telegram…",
        "error":           "❌ Erreur :",
        "file_too_large":  "❌ Fichier trop volumineux (limite 50 Mo).",
        "rate_limited":    "⏳ Ralentissez un peu.",
        "not_admin":       "🚫 Réservé aux admins.",
        "broadcast_usage": "Usage : /broadcast <message>",
        "broadcast_done":  "✅ Envoyé à {n} utilisateurs.",
        "invalid_currency":"❌ Format non reconnu. Essayez : `100 USD to EUR`",
        "btn_help":     "Aide ℹ️",        "btn_lang":     "Langue 🌐",
        "btn_image":    "Image IA 🎨",    "btn_qr":       "Code QR 🔳",
        "btn_tts":      "Voix 🗣️",        "btn_back":     "◀ Retour",
        "btn_tools":    "Plus d'Outils 🛠", "btn_shorten": "Raccourcir URL 🔗",
        "btn_weather":  "Météo ⛅",        "btn_currency": "Devise 💱",
    },
    "pt": {
        "main_menu":       "🤖 *Super Bot*\n\nToque numa plataforma ou cole um link diretamente:",
        "tools_menu":      "🛠 *Mais Ferramentas*\n\nEscolha uma ferramenta:",
        "help_text": (
            "📖 *Como me usar:*\n\n"
            "📥 *Baixar:* Toque num botão _ou_ cole um link.\n"
            "🎬 *Vídeo / 🎵 Áudio:* Escolha o formato após colar.\n"
            "🎨 *Imagem IA:* Descreva o que desenhar.\n"
            "🔳 *QR:* Texto/link → imagem QR.\n"
            "🗣️ *Voz:* Texto → mensagem de áudio.\n"
            "🔗 *Encurtar URL.*\n"
            "⛅ *Clima:* Digite uma cidade.\n"
            "💱 *Moeda:* ex. `100 USD to EUR`"
        ),
        "choose_lang":     "🌐 Escolha seu idioma:",
        "lang_set":        "✅ Idioma definido para Português!\n\n",
        "ask_yt":          "🔴 *Downloader YouTube*\n\nCole seu link do YouTube:",
        "ask_ig":          "📸 *Downloader Instagram*\n\nCole seu link do Instagram:",
        "ask_tt":          "🎵 *Downloader TikTok*\n\nCole seu link do TikTok:",
        "ask_fb":          "🔵 *Downloader Facebook*\n\nCole seu link do Facebook:",
        "ask_tw":          "🐦 *Downloader Twitter/X*\n\nCole seu link do Twitter/X:",
        "ask_sc":          "🎧 *Downloader SoundCloud*\n\nCole seu link do SoundCloud:",
        "invalid_yt":      "❌ Não parece um link do YouTube. Tente novamente:",
        "invalid_ig":      "❌ Não parece um link do Instagram. Tente novamente:",
        "invalid_tt":      "❌ Não parece um link do TikTok. Tente novamente:",
        "invalid_fb":      "❌ Não parece um link do Facebook. Tente novamente:",
        "invalid_tw":      "❌ Não parece um link do Twitter/X. Tente novamente:",
        "invalid_sc":      "❌ Não parece um link do SoundCloud. Tente novamente:",
        "choose_format":   "✅ Link salvo! Escolha o formato:",
        "ask_image":       "🎨 *Criador de Imagem IA*\n\nDescreva o que quer desenhado.",
        "ask_qr":          "🔳 *Gerador QR*\n\nEnvie qualquer texto ou link:",
        "ask_tts":         "🗣️ *Criador de Voz*\n\nEnvie texto para ler em voz alta:",
        "ask_shorten":     "🔗 *Encurtador de URL*\n\nCole o link a encurtar:",
        "ask_weather":     "⛅ *Clima*\n\nDigite o nome de uma cidade:",
        "ask_currency":    "💱 *Conversor de Moeda*\n\nEx: `100 USD to EUR`",
        "generating":      "🎨 Gerando imagem… aguarde",
        "auto_detect":     "🔗 Link detectado! Processando…",
        "uploading":       "✅ Pronto! Enviando para o Telegram…",
        "error":           "❌ Erro:",
        "file_too_large":  "❌ Arquivo grande demais (limite 50 MB).",
        "rate_limited":    "⏳ Vá um pouco mais devagar.",
        "not_admin":       "🚫 Apenas administradores.",
        "broadcast_usage": "Uso: /broadcast <mensagem>",
        "broadcast_done":  "✅ Enviado para {n} usuários.",
        "invalid_currency":"❌ Formato não reconhecido. Tente: `100 USD to EUR`",
        "btn_help":     "Ajuda ℹ️",       "btn_lang":     "Idioma 🌐",
        "btn_image":    "Imagem IA 🎨",   "btn_qr":       "Código QR 🔳",
        "btn_tts":      "Voz 🗣️",         "btn_back":     "◀ Voltar",
        "btn_tools":    "Mais Ferramentas 🛠", "btn_shorten": "Encurtar URL 🔗",
        "btn_weather":  "Clima ⛅",        "btn_currency": "Moeda 💱",
    },
    "ar": {
        "main_menu":       "🤖 *الروبوت الخارق*\n\nاضغط على منصة أو الصق رابطًا مباشرة:",
        "tools_menu":      "🛠 *المزيد من الأدوات*\n\nاختر أداة:",
        "help_text": (
            "📖 *كيف تستخدم الروبوت:*\n\n"
            "📥 *للتحميل:* اضغط زر منصة _أو_ الصق رابطًا مباشرة.\n"
            "🎬 *فيديو / 🎵 صوت:* اختر الصيغة بعد اللصق.\n"
            "🎨 *صورة ذكاء اصطناعي:* صِف ما تريد رسمه.\n"
            "🔳 *رمز QR:* نص/رابط → صورة QR.\n"
            "🗣️ *الصوت:* نص → رسالة صوتية.\n"
            "🔗 *اختصار URL.*\n"
            "⛅ *الطقس:* اكتب اسم مدينة.\n"
            "💱 *العملة:* مثال: `100 USD to EUR`"
        ),
        "choose_lang":     "🌐 اختر لغتك:",
        "lang_set":        "✅ تم تعيين اللغة إلى العربية!\n\n",
        "ask_yt":          "🔴 *تحميل يوتيوب*\n\nالصق رابط يوتيوب:",
        "ask_ig":          "📸 *تحميل إنستغرام*\n\nالصق رابط إنستغرام:",
        "ask_tt":          "🎵 *تحميل تيك توك*\n\nالصق رابط تيك توك:",
        "ask_fb":          "🔵 *تحميل فيسبوك*\n\nالصق رابط فيسبوك:",
        "ask_tw":          "🐦 *تحميل تويتر/X*\n\nالصق رابط تويتر/X:",
        "ask_sc":          "🎧 *تحميل ساوند كلاود*\n\nالصق رابط ساوند كلاود:",
        "invalid_yt":      "❌ هذا ليس رابط يوتيوب. حاول مجددًا:",
        "invalid_ig":      "❌ هذا ليس رابط إنستغرام. حاول مجددًا:",
        "invalid_tt":      "❌ هذا ليس رابط تيك توك. حاول مجددًا:",
        "invalid_fb":      "❌ هذا ليس رابط فيسبوك. حاول مجددًا:",
        "invalid_tw":      "❌ هذا ليس رابط تويتر/X. حاول مجددًا:",
        "invalid_sc":      "❌ هذا ليس رابط ساوند كلاود. حاول مجددًا:",
        "choose_format":   "✅ تم حفظ الرابط! اختر الصيغة:",
        "ask_image":       "🎨 *صانع الصور*\n\nصِف ما تريد رسمه.",
        "ask_qr":          "🔳 *مولد QR*\n\nأرسل أي نص أو رابط:",
        "ask_tts":         "🗣️ *صانع الصوت*\n\nأرسل نصًا لقراءته:",
        "ask_shorten":     "🔗 *مختصر URL*\n\nالصق الرابط المراد اختصاره:",
        "ask_weather":     "⛅ *الطقس*\n\nاكتب اسم مدينة:",
        "ask_currency":    "💱 *محول العملات*\n\nمثال: `100 USD to EUR`",
        "generating":      "🎨 جاري إنشاء الصورة… يرجى الانتظار",
        "auto_detect":     "🔗 تم اكتشاف رابط! جاري المعالجة…",
        "uploading":       "✅ تم! جاري الرفع إلى تيليغرام…",
        "error":           "❌ خطأ:",
        "file_too_large":  "❌ الملف أكبر من حد تيليغرام (50 ميغابايت).",
        "rate_limited":    "⏳ تباطأ قليلًا.",
        "not_admin":       "🚫 للمشرفين فقط.",
        "broadcast_usage": "الاستخدام: /broadcast <رسالة>",
        "broadcast_done":  "✅ تم الإرسال إلى {n} مستخدم.",
        "invalid_currency":"❌ تنسيق غير معروف. جرب: `100 USD to EUR`",
        "btn_help":     "مساعدة ℹ️",              "btn_lang":     "اللغة 🌐",
        "btn_image":    "صورة ذكاء اصطناعي 🎨",   "btn_qr":       "رمز QR 🔳",
        "btn_tts":      "صوت 🗣️",                 "btn_back":     "◀ رجوع",
        "btn_tools":    "المزيد من الأدوات 🛠",    "btn_shorten":  "اختصار URL 🔗",
        "btn_weather":  "الطقس ⛅",                "btn_currency": "العملة 💱",
    },
}

def t(uid: int, key: str) -> str:
    lang = user_languages.get(uid, "en")
    return TEXTS.get(lang, TEXTS["en"]).get(key, TEXTS["en"].get(key, key))

# ══════════════════════════════════════════════════════════
# 6.  KEYBOARDS
# ══════════════════════════════════════════════════════════
def main_menu_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
            InlineKeyboardButton("YouTube 🔴",    callback_data="ask_yt"),
            InlineKeyboardButton("Instagram 📸",  callback_data="ask_ig"),
            InlineKeyboardButton("TikTok 🎵",     callback_data="ask_tt"),
        ],[
            InlineKeyboardButton("Facebook 🔵",   callback_data="ask_fb"),
            InlineKeyboardButton("Twitter/X 🐦",  callback_data="ask_tw"),
            InlineKeyboardButton("SoundCloud 🎧", callback_data="ask_sc"),
        ],[
            InlineKeyboardButton(t(uid, "btn_image"), callback_data="ask_image"),
            InlineKeyboardButton(t(uid, "btn_qr"),    callback_data="ask_qr"),
            InlineKeyboardButton(t(uid, "btn_tts"),   callback_data="ask_tts"),
        ],[
            InlineKeyboardButton(t(uid, "btn_tools"), callback_data="show_tools"),
            InlineKeyboardButton(t(uid, "btn_lang"),  callback_data="show_lang"),
            InlineKeyboardButton(t(uid, "btn_help"),  callback_data="show_help"),
        ],
    ])

def download_format_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
            InlineKeyboardButton("🎬 Video",       callback_data="dl_video"),
            InlineKeyboardButton("🎵 Audio (MP3)", callback_data="dl_audio"),
        ],[InlineKeyboardButton(t(uid, "btn_back"), callback_data="show_main")],
    ])

def tools_menu_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
            InlineKeyboardButton(t(uid, "btn_shorten"),  callback_data="ask_shorten"),
            InlineKeyboardButton(t(uid, "btn_weather"),  callback_data="ask_weather"),
        ],[InlineKeyboardButton(t(uid, "btn_currency"), callback_data="ask_currency")],[InlineKeyboardButton(t(uid, "btn_back"), callback_data="show_main")],
    ])

def back_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(t(uid, "btn_back"), callback_data="show_main")]
    ])

def lang_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
            InlineKeyboardButton("English 🇬🇧",   callback_data="lang_en"),
            InlineKeyboardButton("Español 🇪🇸",   callback_data="lang_es"),
        ],[
            InlineKeyboardButton("Français 🇫🇷",  callback_data="lang_fr"),
            InlineKeyboardButton("Português 🇧🇷", callback_data="lang_pt"),
        ],[InlineKeyboardButton("العربية 🇸🇦",      callback_data="lang_ar")],[InlineKeyboardButton(t(uid, "btn_back"), callback_data="show_main")],
    ])

# ══════════════════════════════════════════════════════════
# 7.  HELPERS
# ══════════════════════════════════════════════════════════
def cleanup(pattern: str) -> None:
    for path in glob.glob(pattern):
        try:
            os.remove(path)
        except OSError as exc:
            logger.warning("Could not delete %s: %s", path, exc)

_BARS =[
    "📥 `[█░░░░░░░░░]` 10%",
    "📥 `[███░░░░░░░]` 30%",
    "📥 `[█████░░░░░]` 50%",
    "📥 `[███████░░░]` 70%",
    "📥 `[█████████░]` 90%",
    "⚙️ `[██████████]` Processing…",
]

async def _animate_progress(msg, stop: asyncio.Event) -> None:
    i = 0
    while not stop.is_set():
        try:
            await msg.edit_text(_BARS[min(i, len(_BARS) - 1)], parse_mode="Markdown")
        except Exception:
            pass
        if i < len(_BARS) - 1:
            i += 1
        await asyncio.sleep(2.0)

# ══════════════════════════════════════════════════════════
# 8.  COBALT API ENGINE (DYNAMIC & ROBUST)
# ══════════════════════════════════════════════════════════
_COBALT_HEADERS = {
    "Accept":        "application/json",
    "Content-Type":  "application/json",
    "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

_STREAM_HEADERS = {
    "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":       "https://cobalt.tools/",
}

def get_cobalt_instances() -> list[str]:
    """Dynamically fetch a list of healthy Cobalt instances, with solid fallbacks."""
    bases =[
        "https://api.cobalt.tools",
        "https://co.wuk.sh",
        "https://api.cobalt.bkc.icu",
        "https://cobalt.tools.run",
        "https://cobalt.meowing.de",
        "https://cobalt.canine.tools"
    ]
    try:
        # Fetch live community instances
        r = requests.get("https://instances.cobalt.best/api/instances.json", timeout=10)
        if r.status_code == 200:
            for inst in r.json():
                api = inst.get("api")
                score = inst.get("score", 0)
                is_online = inst.get("online", {}).get("api", False)
                
                # Only add instances that are online and have a high reliability score
                if api and is_online and score >= 90:
                    if api not in bases:
                        bases.append(api)
    except Exception as e:
        logger.warning("Could not fetch dynamic instances: %s", e)
    
    return bases

def _cobalt_request(url: str, audio_only: bool = False) -> dict:
    payload: dict = {
        "url":          url,
        "videoQuality": "720",
        "audioFormat":  "mp3",
        "filenameStyle":"pretty",
        "downloadMode": "audio" if audio_only else "auto",
    }
    last_error: Exception | None = None
    instances = get_cobalt_instances()
    
    for base in instances:
        for endpoint in ["/api/json", "/"]:
            try:
                resp = requests.post(
                    base.rstrip("/") + endpoint,
                    json=payload,
                    headers=_COBALT_HEADERS,
                    timeout=15,
                )
                
                # Skip instances that are dead, incorrectly configured, or explicitly blocking us
                if resp.status_code in (404, 405, 403, 401, 429):
                    continue
                
                resp.raise_for_status()
                data = resp.json()
                status = data.get("status", "")
                
                if status == "error":
                    err_data = data.get("error", {})
                    if isinstance(err_data, dict):
                        err_code = err_data.get("code", data.get("text", "Unknown Cobalt error"))
                    else:
                        err_code = str(err_data) or data.get("text", "Unknown Cobalt error")
                    
                    # If this instance requires an API key or is rate-limiting, skip it
                    if "rate-limit" in err_code.lower() or "auth" in err_code.lower():
                        continue
                        
                    raise RuntimeError(err_code)
                
                logger.info("Cobalt OK via %s%s status=%s", base, endpoint, status)
                return data
            except (RuntimeError, requests.RequestException) as exc:
                last_error = exc
                logger.debug("Cobalt %s%s → %s", base, endpoint, exc)
                
    raise RuntimeError(f"All Cobalt instances failed. Last error: {last_error}")

def _download_stream(download_url: str, dest_path: str) -> None:
    resp = requests.get(download_url, stream=True, headers=_STREAM_HEADERS, timeout=60)
    resp.raise_for_status()
    content_len = resp.headers.get("Content-Length")
    if content_len and int(content_len) > MAX_FILE_MB * 1024 * 1024:
        raise ValueError("FILE_TOO_LARGE")
    written = 0
    with open(dest_path, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                written += len(chunk)
                if written > MAX_FILE_MB * 1024 * 1024:
                    raise ValueError("FILE_TOO_LARGE")
                fh.write(chunk)

def _run_cobalt_download(url: str, audio_only: bool, prefix: str) -> tuple[str, bool]:
    data   = _cobalt_request(url, audio_only=audio_only)
    status = data.get("status", "")
    if status in ("tunnel", "redirect", "stream"):
        dl_url = data.get("url")
        if not dl_url:
            raise RuntimeError("Cobalt returned no download URL.")
        ext  = "mp3" if audio_only else "mp4"
        path = f"{prefix}.{ext}"
        _download_stream(dl_url, path)
        return path, audio_only
    if status == "picker":
        items = data.get("picker",[])
        if not items:
            raise RuntimeError("Cobalt picker returned no items.")
        dl_url = items[0].get("url")
        if not dl_url:
            raise RuntimeError("Cobalt picker item has no URL.")
        path = f"{prefix}.mp4"
        _download_stream(dl_url, path)
        return path, False
    raise RuntimeError(f"Unexpected Cobalt status: {status!r}")

# ══════════════════════════════════════════════════════════
# 9.  EXTRA TOOL FUNCTIONS
# ══════════════════════════════════════════════════════════
def _shorten_url(url: str) -> str:
    r = requests.get(
        f"https://tinyurl.com/api-create.php?url={urllib.parse.quote(url, safe='')}",
        timeout=10,
    )
    r.raise_for_status()
    return r.text.strip()

def _get_weather(city: str) -> str:
    r = requests.get(
        f"https://wttr.in/{urllib.parse.quote(city)}?format=4",
        timeout=10,
        headers={"User-Agent": "curl/7.68.0"},
    )
    r.raise_for_status()
    return r.text.strip()

_CURRENCY_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*([a-zA-Z]{3})\s+(?:to|in|→)\s*([a-zA-Z]{3})", re.I
)

def _convert_currency(query: str) -> str:
    m = _CURRENCY_RE.search(query)
    if not m:
        return ""
    amount = float(m.group(1).replace(",", "."))
    src, dst = m.group(2).upper(), m.group(3).upper()
    r = requests.get(f"https://open.er-api.com/v6/latest/{src}", timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("result") != "success":
        return ""
    rate = data["rates"].get(dst)
    if rate is None:
        return ""
    return f"💱 *{amount:g} {src}* = *{amount * rate:.4g} {dst}*"

# ══════════════════════════════════════════════════════════
# 10. COMMANDS
# ══════════════════════════════════════════════════════════
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    user_states[uid] = None
    save_user(uid)  # Saves user persistently
    await update.message.reply_text(
        t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    await update.message.reply_text(
        t(uid, "help_text"), reply_markup=back_keyboard(uid), parse_mode="Markdown"
    )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        await update.message.reply_text(t(uid, "not_admin"))
        return
    if not context.args:
        await update.message.reply_text(t(uid, "broadcast_usage"))
        return
    text  = " ".join(context.args)
    users = get_all_users() # Load from persistent file
    sent  = 0
    for target in users:
        try:
            await context.bot.send_message(chat_id=target, text=text)
            sent += 1
        except Exception as exc:
            logger.warning("Broadcast uid=%s: %s", target, exc)
    await update.message.reply_text(t(uid, "broadcast_done").format(n=sent))

# ══════════════════════════════════════════════════════════
# 11. MESSAGE HANDLER
# ══════════════════════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid   = update.effective_user.id
    text  = update.message.text.strip()
    state = user_states.get(uid)
    save_user(uid) # Ensure user is persistently saved

    if is_rate_limited(uid):
        await update.message.reply_text(t(uid, "rate_limited"))
        return

    # ── Platform states: validate link then show format picker ──
    if state in PLATFORM_VALIDATORS:
        if not _valid_platform_link(state, text):
            _, bad_key = PLATFORM_VALIDATORS[state]
            await update.message.reply_text(
                t(uid, bad_key), reply_markup=back_keyboard(uid), parse_mode="Markdown"
            )
            return
        # Valid link — save it and show Video / Audio choice
        user_states[uid] = None
        context.user_data["pending_link"] = text
        await update.message.reply_text(
            t(uid, "choose_format"),
            reply_markup=download_format_keyboard(uid),
            parse_mode="Markdown",
        )
        return

    # ── Raw link pasted with no prior state ──────────────
    if state is None and text.startswith(("http://", "https://")):
        user_states[uid] = None
        context.user_data["pending_link"] = text
        await update.message.reply_text(
            t(uid, "choose_format"),
            reply_markup=download_format_keyboard(uid),
            parse_mode="Markdown",
        )
        return

    # ── QR Code ──────────────────────────────────────────
    if state == "waiting_for_qr":
        user_states[uid] = None
        safe = urllib.parse.quote(text)
        await context.bot.send_photo(
            chat_id=uid,
            photo=f"https://api.qrserver.com/v1/create-qr-code/?size=512x512&data={safe}",
            caption="✅ QR Code",
        )
        await update.message.reply_text(
            t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown"
        )

    # ── Text-to-Speech ────────────────────────────────────
    elif state == "waiting_for_tts":
        user_states[uid] = None
        fname = f"{uid}_voice.mp3"
        try:
            tts = gTTS(text=text, lang=user_languages.get(uid, "en"))
            await asyncio.to_thread(tts.save, fname)
            with open(fname, "rb") as fh:
                await context.bot.send_voice(chat_id=uid, voice=fh)
        except Exception as exc:
            logger.error("TTS uid=%s: %s", uid, exc)
            await update.message.reply_text(f"{t(uid, 'error')} {exc}")
        finally:
            cleanup(fname)
        await update.message.reply_text(
            t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown"
        )

    # ── AI Image ──────────────────────────────────────────
    elif state == "waiting_for_image":
        user_states[uid] = None
        msg   = await update.message.reply_text(t(uid, "generating"), parse_mode="Markdown")
        fname = f"{uid}_ai.jpg"
        try:
            safe = urllib.parse.quote(text)
            resp = await asyncio.to_thread(
                requests.get,
                f"https://image.pollinations.ai/prompt/{safe}?width=1080&height=1080&nologo=true",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=60,
            )
            resp.raise_for_status()
            with open(fname, "wb") as fh:
                fh.write(resp.content)
            with open(fname, "rb") as fh:
                await context.bot.send_photo(chat_id=uid, photo=fh, caption=f"🎨 {text}")
            await msg.delete()
        except Exception as exc:
            logger.error("Image uid=%s: %s", uid, exc)
            await msg.edit_text(f"{t(uid, 'error')} {exc}")
        finally:
            cleanup(fname)
            await update.message.reply_text(
                t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown"
            )

    # ── URL Shortener ─────────────────────────────────────
    elif state == "waiting_for_shorten":
        user_states[uid] = None
        try:
            short = await asyncio.to_thread(_shorten_url, text)
            await update.message.reply_text(f"🔗 {short}")
        except Exception as exc:
            await update.message.reply_text(f"{t(uid, 'error')} {exc}")
        await update.message.reply_text(
            t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown"
        )

    # ── Weather ───────────────────────────────────────────
    elif state == "waiting_for_weather":
        user_states[uid] = None
        try:
            info = await asyncio.to_thread(_get_weather, text)
            await update.message.reply_text(f"⛅ {info}")
        except Exception as exc:
            await update.message.reply_text(f"{t(uid, 'error')} {exc}")
        await update.message.reply_text(
            t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown"
        )

    # ── Currency ──────────────────────────────────────────
    elif state == "waiting_for_currency":
        user_states[uid] = None
        try:
            result = await asyncio.to_thread(_convert_currency, text)
            if not result:
                await update.message.reply_text(
                    t(uid, "invalid_currency"), parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(result, parse_mode="Markdown")
        except Exception as exc:
            await update.message.reply_text(f"{t(uid, 'error')} {exc}")
        await update.message.reply_text(
            t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown"
        )

    # ── Fallback ──────────────────────────────────────────
    else:
        await update.message.reply_text(
            t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown"
        )

# ══════════════════════════════════════════════════════════
# 12. BUTTON / CALLBACK HANDLER
# ══════════════════════════════════════════════════════════
_PLATFORM_STATES: dict[str, str] = {
    "ask_yt": "waiting_for_yt",
    "ask_ig": "waiting_for_ig",
    "ask_tt": "waiting_for_tt",
    "ask_fb": "waiting_for_fb",
    "ask_tw": "waiting_for_tw",
    "ask_sc": "waiting_for_sc",
}

_TOOL_STATES_MAP: dict[str, str] = {
    "ask_image":    "waiting_for_image",
    "ask_qr":       "waiting_for_qr",
    "ask_tts":      "waiting_for_tts",
    "ask_shorten":  "waiting_for_shorten",
    "ask_weather":  "waiting_for_weather",
    "ask_currency": "waiting_for_currency",
}

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    uid   = query.from_user.id
    data  = query.data
    await query.answer()

    if is_rate_limited(uid):
        await query.answer(t(uid, "rate_limited"), show_alert=True)
        return

    # ── Navigation ────────────────────────────────────────
    if data == "show_main":
        user_states[uid] = None
        await query.edit_message_text(
            t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown"
        )

    elif data == "show_tools":
        await query.edit_message_text(
            t(uid, "tools_menu"), reply_markup=tools_menu_keyboard(uid), parse_mode="Markdown"
        )

    elif data == "show_help":
        await query.edit_message_text(
            t(uid, "help_text"), reply_markup=back_keyboard(uid), parse_mode="Markdown"
        )

    elif data == "show_lang":
        await query.edit_message_text(
            t(uid, "choose_lang"), reply_markup=lang_keyboard(uid), parse_mode="Markdown"
        )

    # ── Language selection ────────────────────────────────
    elif data.startswith("lang_"):
        user_languages[uid] = data[5:]
        await query.edit_message_text(
            t(uid, "lang_set") + t(uid, "main_menu"),
            reply_markup=main_menu_keyboard(uid),
            parse_mode="Markdown",
        )

    # ── Platform buttons → ask for link ──────────────────
    elif data in _PLATFORM_STATES:
        user_states[uid] = _PLATFORM_STATES[data]
        await query.edit_message_text(
            t(uid, data), reply_markup=back_keyboard(uid), parse_mode="Markdown"
        )

    # ── Tool buttons → ask for text ───────────────────────
    elif data in _TOOL_STATES_MAP:
        user_states[uid] = _TOOL_STATES_MAP[data]
        await query.edit_message_text(
            t(uid, data), reply_markup=back_keyboard(uid), parse_mode="Markdown"
        )

    # ── Format picker: Video ──────────────────────────────
    elif data == "dl_video":
        link = context.user_data.get("pending_link")
        if not link:
            await query.edit_message_text(
                t(uid, "error") + " No link saved. Please paste a link first.",
                parse_mode="Markdown",
            )
            return
        await query.edit_message_text(t(uid, "auto_detect"), parse_mode="Markdown")
        await _start_download_from_button(query, context, uid, link, audio_only=False)

    # ── Format picker: Audio ──────────────────────────────
    elif data == "dl_audio":
        link = context.user_data.get("pending_link")
        if not link:
            await query.edit_message_text(
                t(uid, "error") + " No link saved. Please paste a link first.",
                parse_mode="Markdown",
            )
            return
        await query.edit_message_text(t(uid, "auto_detect"), parse_mode="Markdown")
        await _start_download_from_button(query, context, uid, link, audio_only=True)

async def _start_download_from_button(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    uid: int,
    link: str,
    audio_only: bool,
) -> None:
    prefix = f"{uid}_media"
    cleanup(f"{prefix}*")

    msg  = query.message
    stop = asyncio.Event()
    anim = asyncio.create_task(_animate_progress(msg, stop))

    try:
        filepath, is_audio = await asyncio.to_thread(
            _run_cobalt_download, link, audio_only, prefix
        )
        stop.set(); anim.cancel()
        try:
            await msg.edit_text(t(uid, "uploading"), parse_mode="Markdown")
        except Exception:
            pass
        with open(filepath, "rb") as fh:
            if is_audio:
                await context.bot.send_audio(chat_id=uid, audio=fh)
            else:
                await context.bot.send_video(chat_id=uid, video=fh)
        try:
            await msg.delete()
        except Exception:
            pass
    except ValueError as ve:
        stop.set(); anim.cancel()
        await msg.edit_text(
            t(uid, "file_too_large") if str(ve) == "FILE_TOO_LARGE"
            else f"{t(uid, 'error')} `{ve}`",
            parse_mode="Markdown",
        )
    except Exception as exc:
        stop.set(); anim.cancel()
        logger.error("Download uid=%s url=%s: %s", uid, link, exc)
        await msg.edit_text(f"{t(uid, 'error')}\n`{exc}`", parse_mode="Markdown")
    finally:
        cleanup(f"{prefix}*")
        await context.bot.send_message(
            chat_id=uid,
            text=t(uid, "main_menu"),
            reply_markup=main_menu_keyboard(uid),
            parse_mode="Markdown",
        )

# ══════════════════════════════════════════════════════════
# 13. ENTRY POINT
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    keep_alive()
    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start",     start_command))
    bot_app.add_handler(CommandHandler("help",      help_command))
    bot_app.add_handler(CommandHandler("broadcast", broadcast_command))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    logger.info("Bot is running…")
    bot_app.run_polling(drop_pending_updates=True)
