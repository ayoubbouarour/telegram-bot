"""
Super Bot — Telegram multi-tool bot (Cobalt API Edition)
══════════════════════════════════════════════════════════════
TOOLS
  ▸ Downloader  — Cobalt API Proxy (Bypasses YouTube IP Bans!)
  ▸ AI Image    — Pollinations.ai
  ▸ QR Code     — api.qrserver.com
  ▸ Voice Maker — gTTS text-to-speech
  ▸ URL Shortener — tinyurl.com
  ▸ Weather     — wttr.in
  ▸ Currency    — open.er-api.com
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
RATE_LIMIT  = 8
RATE_WINDOW = 60

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
# 3.  IN-MEMORY STATE
# ══════════════════════════════════════════════════════════
user_languages: dict[int, str]         = {}
user_states:    dict[int, str | None]  = {}
_rate_buckets:  dict[int, list[float]] = defaultdict(list)

def is_rate_limited(uid: int) -> bool:
    now = time.monotonic()
    _rate_buckets[uid] = [ts for ts in _rate_buckets[uid] if now - ts < RATE_WINDOW]
    if len(_rate_buckets[uid]) >= RATE_LIMIT:
        return True
    _rate_buckets[uid].append(now)
    return False

# ══════════════════════════════════════════════════════════
# 4.  TRANSLATIONS
# ══════════════════════════════════════════════════════════
TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "main_menu":       "🤖 *Super Bot*\n\nChoose a tool below:",
        "tools_menu":      "🛠 *More Tools*\n\nChoose a tool:",
        "help_text": (
            "📖 *How to use me:*\n\n"
            "📥 *Download:* Tap a platform then paste your link.\n"
            "🎨 *AI Image:* Describe what to draw.\n"
            "🔳 *QR Code:* Text or link → QR image.\n"
            "🗣️ *Voice:* Text → audio message.\n"
            "🔗 *Short URL:* Shorten any link.\n"
            "⛅ *Weather:* Type a city name.\n"
            "💱 *Currency:* e.g. `100 USD to EUR`"
        ),
        "choose_lang":     "🌐 Choose your language:",
        "lang_set":        "✅ Language set to English!\n\n",
        "choose_format":   "🔗 Link ready! Pick a format:",
        "downloading":     "⬇️ Downloading… please wait",
        "ask_prompt":      "🎨 *AI Image Maker*\n\nDescribe what you want drawn.",
        "generating":      "🎨 Generating image… please wait",
        "ask_yt":          "🔴 Paste your *YouTube* link:",
        "ask_ig":          "📸 Paste your *Instagram* link:",
        "ask_tt":          "🎵 Paste your *TikTok* link:",
        "ask_fb":          "🔵 Paste your *Facebook* link:",
        "ask_tw":          "🐦 Paste your *Twitter / X* link:",
        "invalid_yt":      "❌ That's not a YouTube link. Try again:",
        "invalid_ig":      "❌ That's not an Instagram link. Try again:",
        "invalid_tt":      "❌ That's not a TikTok link. Try again:",
        "invalid_fb":      "❌ That's not a Facebook link. Try again:",
        "invalid_tw":      "❌ That's not a Twitter/X link. Try again:",
        "ask_qr":          "🔳 *QR Generator*\n\nSend any text or link:",
        "ask_tts":         "🗣️ *Voice Maker*\n\nSend any text to read aloud:",
        "ask_shorten":     "🔗 *URL Shortener*\n\nPaste the link you want shortened:",
        "ask_weather":     "⛅ *Weather*\n\nType a city name (e.g. `London`):",
        "ask_currency":    "💱 *Currency Converter*\n\nType like: `100 USD to EUR`",
        "error":           "❌ Something went wrong:",
        "file_too_large":  "❌ File too large for Telegram (50 MB limit). Try lower quality.",
        "rate_limited":    "⏳ Too many requests. Please wait a moment.",
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
        "main_menu":       "🤖 *Súper Bot*\n\nElige una herramienta:",
        "tools_menu":      "🛠 *Más Herramientas*\n\nElige una herramienta:",
        "help_text": (
            "📖 *Cómo usarme:*\n\n"
            "📥 *Descargar:* Pulsa una plataforma y pega el enlace.\n"
            "🎨 *Imagen IA:* Describe qué dibujar.\n"
            "🔳 *QR:* Texto/enlace → imagen QR.\n"
            "🗣️ *Voz:* Texto → mensaje de audio.\n"
            "🔗 *Acortar URL:* Acorta cualquier enlace.\n"
            "⛅ *Clima:* Escribe una ciudad.\n"
            "💱 *Moneda:* p.ej. `100 USD to EUR`"
        ),
        "choose_lang":     "🌐 Elige tu idioma:",
        "lang_set":        "✅ ¡Idioma cambiado a Español!\n\n",
        "choose_format":   "🔗 ¡Enlace listo! Elige el formato:",
        "downloading":     "⬇️ Descargando… espera",
        "ask_prompt":      "🎨 *Creador de Imágenes IA*\n\nDescribe qué quieres dibujar.",
        "generating":      "🎨 Generando imagen… espera",
        "ask_yt":          "🔴 Pega tu enlace de *YouTube*:",
        "ask_ig":          "📸 Pega tu enlace de *Instagram*:",
        "ask_tt":          "🎵 Pega tu enlace de *TikTok*:",
        "ask_fb":          "🔵 Pega tu enlace de *Facebook*:",
        "ask_tw":          "🐦 Pega tu enlace de *Twitter/X*:",
        "invalid_yt":      "❌ No es un enlace de YouTube. Inténtalo de nuevo:",
        "invalid_ig":      "❌ No es un enlace de Instagram. Inténtalo de nuevo:",
        "invalid_tt":      "❌ No es un enlace de TikTok. Inténtalo de nuevo:",
        "invalid_fb":      "❌ No es un enlace de Facebook. Inténtalo de nuevo:",
        "invalid_tw":      "❌ No es un enlace de Twitter/X. Inténtalo de nuevo:",
        "ask_qr":          "🔳 *Generador QR*\n\nEnvía texto o un enlace:",
        "ask_tts":         "🗣️ *Creador de Voz*\n\nEnvía texto para leer en voz alta:",
        "ask_shorten":     "🔗 *Acortador de URL*\n\nPega el enlace a acortar:",
        "ask_weather":     "⛅ *Clima*\n\nEscribe el nombre de una ciudad:",
        "ask_currency":    "💱 *Conversor de Moneda*\n\nEscribe: `100 USD to EUR`",
        "error":           "❌ Algo salió mal:",
        "file_too_large":  "❌ Archivo demasiado grande (límite 50 MB). Prueba menor calidad.",
        "rate_limited":    "⏳ Demasiadas solicitudes. Espera un momento.",
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
        "main_menu":       "🤖 *Super Bot*\n\nChoisissez un outil :",
        "tools_menu":      "🛠 *Plus d'Outils*\n\nChoisissez un outil :",
        "help_text": "📖 *Comment m'utiliser :*\n\n📥 *Télécharger :* Cliquez sur une plateforme et collez le lien.\n🎨 *Image IA :* Décrivez ce à dessiner.\n🔳 *QR :* Texte/lien → image QR.\n🗣️ *Voix :* Texte → message audio.\n🔗 *Raccourcir URL :* Raccourcissez n'importe quel lien.\n⛅ *Météo :* Tapez une ville.\n💱 *Monnaie :* ex. `100 USD to EUR`",
        "choose_lang":     "🌐 Choisissez votre langue :", "lang_set": "✅ Langue réglée sur Français !\n\n",
        "choose_format":   "🔗 Lien prêt ! Choisissez le format :", "downloading": "⬇️ Téléchargement… patientez",
        "ask_prompt":      "🎨 *Créateur d'Image IA*\n\nDécrivez ce à dessiner.", "generating": "🎨 Génération d'image… patientez",
        "ask_yt": "🔴 Collez votre lien *YouTube* :", "ask_ig": "📸 Collez votre lien *Instagram* :", "ask_tt": "🎵 Collez votre lien *TikTok* :",
        "ask_fb": "🔵 Collez votre lien *Facebook* :", "ask_tw": "🐦 Collez votre lien *Twitter/X* :",
        "invalid_yt": "❌ Ce n'est pas un lien YouTube. Réessayez :", "invalid_ig": "❌ Ce n'est pas un lien Instagram. Réessayez :",
        "invalid_tt": "❌ Ce n'est pas un lien TikTok. Réessayez :", "invalid_fb": "❌ Ce n'est pas un lien Facebook. Réessayez :",
        "invalid_tw": "❌ Ce n'est pas un lien Twitter/X. Réessayez :",
        "ask_qr": "🔳 *Générateur QR*\n\nEnvoyez texte ou lien :", "ask_tts": "🗣️ *Créateur de Voix*\n\nEnvoyez du texte à lire :",
        "ask_shorten": "🔗 *Raccourcisseur d'URL*\n\nCollez le lien à raccourcir :", "ask_weather": "⛅ *Météo*\n\nTapez un nom de ville :",
        "ask_currency": "💱 *Convertisseur de Devise*\n\nEx : `100 USD to EUR`", "error": "❌ Une erreur s'est produite :",
        "file_too_large": "❌ Fichier trop volumineux (limite 50 Mo). Essayez qualité inférieure.", "rate_limited": "⏳ Trop de requêtes. Attendez un moment.",
        "not_admin": "🚫 Réservé aux admins.", "broadcast_usage": "Usage : /broadcast <message>", "broadcast_done": "✅ Envoyé à {n} utilisateurs.",
        "invalid_currency":"❌ Format non reconnu. Essayez : `100 USD to EUR`",
        "btn_help": "Aide ℹ️", "btn_lang": "Langue 🌐", "btn_image": "Image IA 🎨", "btn_qr": "Code QR 🔳", "btn_tts": "Voix 🗣️", "btn_back": "◀ Retour",
        "btn_tools": "Plus d'Outils 🛠", "btn_shorten": "Raccourcir URL 🔗", "btn_weather": "Météo ⛅", "btn_currency": "Devise 💱",
    },
    "pt": {
        "main_menu": "🤖 *Super Bot*\n\nEscolha uma ferramenta:", "tools_menu": "🛠 *Mais Ferramentas*\n\nEscolha uma ferramenta:",
        "help_text": "📖 *Como me usar:*\n\n📥 *Baixar:* Toque em uma plataforma e cole o link.\n🎨 *Imagem IA:* Descreva o que desenhar.\n🔳 *QR:* Texto/link → imagem QR.\n🗣️ *Voz:* Texto → mensagem de áudio.\n🔗 *Encurtar URL:* Encurte qualquer link.\n⛅ *Clima:* Digite o nome de uma cidade.\n💱 *Moeda:* ex. `100 USD to EUR`",
        "choose_lang": "🌐 Escolha seu idioma:", "lang_set": "✅ Idioma definido para Português!\n\n",
        "choose_format": "🔗 Link pronto! Escolha o formato:", "downloading": "⬇️ Baixando… aguarde",
        "ask_prompt": "🎨 *Criador de Imagem IA*\n\nDescreva o que quer desenhado.", "generating": "🎨 Gerando imagem… aguarde",
        "ask_yt": "🔴 Cole seu link do *YouTube*:", "ask_ig": "📸 Cole seu link do *Instagram*:", "ask_tt": "🎵 Cole seu link do *TikTok*:",
        "ask_fb": "🔵 Cole seu link do *Facebook*:", "ask_tw": "🐦 Cole seu link do *Twitter/X*:",
        "invalid_yt": "❌ Não é um link do YouTube. Tente novamente:", "invalid_ig": "❌ Não é um link do Instagram. Tente novamente:",
        "invalid_tt": "❌ Não é um link do TikTok. Tente novamente:", "invalid_fb": "❌ Não é um link do Facebook. Tente novamente:",
        "invalid_tw": "❌ Não é um link do Twitter/X. Tente novamente:",
        "ask_qr": "🔳 *Gerador QR*\n\nEnvie qualquer texto ou link:", "ask_tts": "🗣️ *Criador de Voz*\n\nEnvie texto para ler em voz alta:",
        "ask_shorten": "🔗 *Encurtador de URL*\n\nCole o link a encurtar:", "ask_weather": "⛅ *Clima*\n\nDigite o nome de uma cidade:",
        "ask_currency": "💱 *Conversor de Moeda*\n\nEx: `100 USD to EUR`", "error": "❌ Algo deu errado:",
        "file_too_large": "❌ Arquivo grande demais (limite 50 MB). Tente qualidade menor.", "rate_limited": "⏳ Muitas solicitações. Aguarde um momento.",
        "not_admin": "🚫 Apenas administradores.", "broadcast_usage": "Uso: /broadcast <mensagem>", "broadcast_done": "✅ Enviado para {n} usuários.",
        "invalid_currency":"❌ Formato não reconhecido. Tente: `100 USD to EUR`",
        "btn_help": "Ajuda ℹ️", "btn_lang": "Idioma 🌐", "btn_image": "Imagem IA 🎨", "btn_qr": "Código QR 🔳", "btn_tts": "Voz 🗣️", "btn_back": "◀ Voltar",
        "btn_tools": "Mais Ferramentas 🛠", "btn_shorten": "Encurtar URL 🔗", "btn_weather": "Clima ⛅", "btn_currency": "Moeda 💱",
    },
    "ar": {
        "main_menu": "🤖 *الروبوت الخارق*\n\nاختر أداة:", "tools_menu": "🛠 *المزيد من الأدوات*\n\nاختر أداة:",
        "help_text": "📖 *كيف تستخدم الروبوت:*\n\n📥 *للتحميل:* اضغط على منصة والصق الرابط.\n🎨 *صورة ذكاء اصطناعي:* صِف ما تريد رسمه.\n🔳 *رمز QR:* نص/رابط → صورة QR.\n🗣️ *الصوت:* نص → رسالة صوتية.\n🔗 *اختصار URL:* اختصر أي رابط.\n⛅ *الطقس:* اكتب اسم مدينة.\n💱 *العملة:* مثال: `100 USD to EUR`",
        "choose_lang": "🌐 اختر لغتك:", "lang_set": "✅ تم تعيين اللغة إلى العربية!\n\n",
        "choose_format": "🔗 الرابط جاهز! اختر التنسيق:", "downloading": "⬇️ جاري التنزيل… يرجى الانتظار",
        "ask_prompt": "🎨 *صانع الصور*\n\nصِف ما تريد رسمه.", "generating": "🎨 جاري إنشاء الصورة… يرجى الانتظار",
        "ask_yt": "🔴 الصق رابط *يوتيوب*:", "ask_ig": "📸 الصق رابط *إنستغرام*:", "ask_tt": "🎵 الصق رابط *تيك توك*:",
        "ask_fb": "🔵 الصق رابط *فيسبوك*:", "ask_tw": "🐦 الصق رابط *تويتر/X*:",
        "invalid_yt": "❌ هذا ليس رابط يوتيوب. حاول مجددًا:", "invalid_ig": "❌ هذا ليس رابط إنستغرام. حاول مجددًا:",
        "invalid_tt": "❌ هذا ليس رابط تيك توك. حاول مجددًا:", "invalid_fb": "❌ هذا ليس رابط فيسبوك. حاول مجددًا:",
        "invalid_tw": "❌ هذا ليس رابط تويتر/X. حاول مجددًا:",
        "ask_qr": "🔳 *مولد QR*\n\nأرسل أي نص أو رابط:", "ask_tts": "🗣️ *صانع الصوت*\n\nأرسل نصًا لقراءته:",
        "ask_shorten": "🔗 *مختصر URL*\n\nالصق الرابط المراد اختصاره:", "ask_weather": "⛅ *الطقس*\n\nاكتب اسم مدينة:",
        "ask_currency": "💱 *محول العملات*\n\nمثال: `100 USD to EUR`", "error": "❌ حدث خطأ:",
        "file_too_large": "❌ الملف كبير جدًا (الحد 50 ميغابايت). جرب جودة أقل.", "rate_limited": "⏳ طلبات كثيرة جدًا. انتظر لحظة.",
        "not_admin": "🚫 للمشرفين فقط.", "broadcast_usage": "الاستخدام: /broadcast <رسالة>", "broadcast_done": "✅ تم الإرسال إلى {n} مستخدم.",
        "invalid_currency":"❌ تنسيق غير معروف. جرب: `100 USD to EUR`",
        "btn_help": "مساعدة ℹ️", "btn_lang": "اللغة 🌐", "btn_image": "صورة ذكاء اصطناعي 🎨", "btn_qr": "رمز QR 🔳", "btn_tts": "صوت 🗣️", "btn_back": "◀ رجوع",
        "btn_tools": "المزيد من الأدوات 🛠", "btn_shorten": "اختصار URL 🔗", "btn_weather": "الطقس ⛅", "btn_currency": "العملة 💱",
    },
}

def t(uid: int, key: str) -> str:
    lang = user_languages.get(uid, "en")
    return TEXTS.get(lang, TEXTS["en"]).get(key, TEXTS["en"].get(key, key))

# ══════════════════════════════════════════════════════════
# 5.  LINK VALIDATION & KEYBOARDS
# ══════════════════════════════════════════════════════════
LINK_VALIDATORS: dict[str, tuple[list[str], str]] = {
    "waiting_for_yt": (["youtube.com", "youtu.be"],            "invalid_yt"),
    "waiting_for_ig": (["instagram.com"],                       "invalid_ig"),
    "waiting_for_tt": (["tiktok.com", "vm.tiktok.com"],        "invalid_tt"),
    "waiting_for_fb": (["facebook.com", "fb.watch", "fb.com"], "invalid_fb"),
    "waiting_for_tw": (["twitter.com", "x.com", "t.co"],       "invalid_tw"),
}

def _valid_link(state: str, url: str) -> bool:
    domains, _ = LINK_VALIDATORS[state]
    return any(d in url.lower() for d in domains)

def main_menu_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("YouTube 🔴", callback_data="ask_yt"), InlineKeyboardButton("Instagram 📸", callback_data="ask_ig")],
        [InlineKeyboardButton("TikTok 🎵", callback_data="ask_tt"), InlineKeyboardButton("Facebook 🔵", callback_data="ask_fb"), InlineKeyboardButton("Twitter/X 🐦", callback_data="ask_tw")],
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

def format_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Video HD", callback_data="dl_mp4_best"), InlineKeyboardButton("📱 Video SD", callback_data="dl_mp4_low")],
        [InlineKeyboardButton("🎵 Audio MP3", callback_data="dl_mp3"), InlineKeyboardButton(t(uid, "btn_back"), callback_data="show_main")]
    ])

# ══════════════════════════════════════════════════════════
# 6.  HELPERS
# ══════════════════════════════════════════════════════════
def cleanup(pattern: str) -> None:
    for path in glob.glob(pattern):
        try: os.remove(path)
        except OSError: pass

_DOTS = ["", " ·", " ··", " ···"]
async def _animate(msg, stop: asyncio.Event, base: str) -> None:
    i = 0
    while not stop.is_set():
        try: await msg.edit_text(base + _DOTS[i % len(_DOTS)], parse_mode="Markdown")
        except Exception: pass
        i += 1
        await asyncio.sleep(2.5)

# ══════════════════════════════════════════════════════════
# 7.  NEW DOWNLOAD ENGINE: COBALT API (BYPASSES YOUTUBE BANS)
# ══════════════════════════════════════════════════════════
def _run_cobalt_download(url: str, fmt_key: str, prefix: str) -> str:
    """Downloads directly using the Cobalt API Proxy. No yt-dlp required."""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    # Configure payload based on requested quality
    payload = {"url": url, "vCodec": "h264"}
    if fmt_key == "mp4_best":
        payload["vQuality"] = "720" # Safest resolution to stay under 50MB limit
    elif fmt_key == "mp4_low":
        payload["vQuality"] = "360"
    elif fmt_key == "mp3":
        payload["isAudioOnly"] = True

    # Use robust public Cobalt instances
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
            break # Success!
        except Exception as e:
            last_error = e
            continue

    if not data:
        raise Exception("API Servers are currently busy. Please try again in a few minutes.")

    if data.get("status") == "error":
        raise Exception(data.get("text", "Unknown API Error"))

    # Extract the direct download link
    download_url = None
    if data.get("status") in ["stream", "redirect"]:
        download_url = data["url"]
    elif data.get("status") == "picker": # Used when downloading TikTok slides
        download_url = data["picker"][0]["url"] 
    else:
        raise Exception("Unknown response format from API.")

    # Stream the file to disk
    ext = "mp3" if fmt_key == "mp3" else "mp4"
    filename = f"{prefix}.{ext}"

    stream_resp = requests.get(download_url, stream=True, timeout=30)
    stream_resp.raise_for_status()

    # Early Size Check (Abort if over 50MB to save Render bandwidth!)
    content_len = stream_resp.headers.get("Content-Length")
    if content_len and int(content_len) > 50 * 1024 * 1024:
        raise ValueError("FILE_TOO_LARGE")

    with open(filename, 'wb') as f:
        for chunk in stream_resp.iter_content(chunk_size=1024 * 1024):
            if chunk: f.write(chunk)

    # Final Size Check
    if os.path.getsize(filename) > 50 * 1024 * 1024:
        os.remove(filename)
        raise ValueError("FILE_TOO_LARGE")

    return filename

# ══════════════════════════════════════════════════════════
# 8. EXTRA TOOL FUNCTIONS
# ══════════════════════════════════════════════════════════
def _shorten_url(url: str) -> str:
    encoded = urllib.parse.quote(url, safe="")
    r = requests.get(f"https://tinyurl.com/api-create.php?url={encoded}", timeout=10)
    return r.text.strip()

def _get_weather(city: str) -> str:
    r = requests.get(f"https://wttr.in/{urllib.parse.quote(city)}?format=4", timeout=10, headers={"User-Agent": "curl/7.68.0"})
    return r.text.strip()

def _convert_currency(query: str) -> str:
    m = re.compile(r"(\d+(?:[.,]\d+)?)\s*([a-zA-Z]{3})\s+(?:to|in|→)\s*([a-zA-Z]{3})", re.I).search(query)
    if not m: return ""
    amount, src, dst = float(m.group(1).replace(",", ".")), m.group(2).upper(), m.group(3).upper()
    data = requests.get(f"https://open.er-api.com/v6/latest/{src}", timeout=10).json()
    if data.get("result") != "success" or dst not in data["rates"]: return ""
    return f"💱 {amount:g} {src} = *{amount * data['rates'][dst]:.4g} {dst}*"

# ══════════════════════════════════════════════════════════
# 9. COMMANDS & MESSAGE HANDLERS
# ══════════════════════════════════════════════════════════
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    user_states[uid] = None
    context.application.bot_data.setdefault("all_users", set()).add(uid)
    await update.message.reply_text(t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    await update.message.reply_text(t(uid, "help_text"), reply_markup=back_keyboard(uid), parse_mode="Markdown")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        await update.message.reply_text(t(uid, "not_admin"))
        return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text(t(uid, "broadcast_usage"))
        return
    sent = 0
    for target in context.application.bot_data.get("all_users", set()):
        try:
            await context.bot.send_message(chat_id=target, text=text)
            sent += 1
        except Exception: pass
    await update.message.reply_text(t(uid, "broadcast_done").format(n=sent))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid, text = update.effective_user.id, update.message.text.strip()
    state = user_states.get(uid)
    context.application.bot_data.setdefault("all_users", set()).add(uid)

    if is_rate_limited(uid):
        await update.message.reply_text(t(uid, "rate_limited"))
        return

    if state == "waiting_for_qr":
        user_states[uid] = None
        safe = urllib.parse.quote(text)
        await context.bot.send_photo(chat_id=uid, photo=f"https://api.qrserver.com/v1/create-qr-code/?size=512x512&data={safe}", caption="✅ QR Code")
        await _send_main(update, uid)

    elif state == "waiting_for_tts":
        user_states[uid] = None
        fname = f"{uid}_voice.mp3"
        try:
            tts = gTTS(text=text, lang=user_languages.get(uid, "en"))
            await asyncio.to_thread(tts.save, fname)
            with open(fname, "rb") as fh: await context.bot.send_voice(chat_id=uid, voice=fh)
        except Exception as exc: await update.message.reply_text(f"{t(uid, 'error')} {exc}")
        finally: cleanup(fname)
        await _send_main(update, uid)

    elif state == "waiting_for_image":
        user_states[uid] = None
        msg = await update.message.reply_text(t(uid, "generating"))
        stop = asyncio.Event()
        anim = asyncio.create_task(_animate(msg, stop, t(uid, "generating")))
        fname = f"{uid}_ai.jpg"
        try:
            resp = await asyncio.to_thread(requests.get, f"https://image.pollinations.ai/prompt/{urllib.parse.quote(text)}?width=1920&height=1080&nologo=true", timeout=90)
            resp.raise_for_status()
            stop.set(); anim.cancel()
            with open(fname, "wb") as fh: fh.write(resp.content)
            with open(fname, "rb") as fh: await context.bot.send_photo(chat_id=uid, photo=fh, caption=f"🎨 {text}")
            await msg.delete()
        except Exception as exc:
            stop.set(); anim.cancel()
            await msg.edit_text(f"{t(uid, 'error')} {exc}")
        finally:
            cleanup(fname)
            await _send_main(update, uid)

    elif state == "waiting_for_shorten":
        user_states[uid] = None
        try: await update.message.reply_text(f"🔗 {await asyncio.to_thread(_shorten_url, text)}")
        except Exception as exc: await update.message.reply_text(f"{t(uid, 'error')} {exc}")
        await _send_main(update, uid)

    elif state == "waiting_for_weather":
        user_states[uid] = None
        try: await update.message.reply_text(f"⛅ {await asyncio.to_thread(_get_weather, text)}")
        except Exception as exc: await update.message.reply_text(f"{t(uid, 'error')} {exc}")
        await _send_main(update, uid)

    elif state == "waiting_for_currency":
        user_states[uid] = None
        try:
            res = await asyncio.to_thread(_convert_currency, text)
            await update.message.reply_text(res if res else t(uid, "invalid_currency"), parse_mode="Markdown")
        except Exception as exc: await update.message.reply_text(f"{t(uid, 'error')} {exc}")
        await _send_main(update, uid)

    elif state in LINK_VALIDATORS:
        if not _valid_link(state, text):
            await update.message.reply_text(t(uid, LINK_VALIDATORS[state][1]), reply_markup=back_keyboard(uid))
            return
        user_states[uid] = None
        context.user_data["last_link"] = text
        await update.message.reply_text(t(uid, "choose_format"), reply_markup=format_keyboard(uid), parse_mode="Markdown")

    elif text.startswith(("http://", "https://")):
        context.user_data["last_link"] = text
        await update.message.reply_text(t(uid, "choose_format"), reply_markup=format_keyboard(uid), parse_mode="Markdown")
    else:
        await _send_main(update, uid)

async def _send_main(update: Update, uid: int) -> None:
    await update.message.reply_text(t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown")

# ══════════════════════════════════════════════════════════
# 10. BUTTON HANDLER
# ══════════════════════════════════════════════════════════
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query, uid = update.callback_query, update.callback_query.from_user.id
    data = query.data
    await query.answer()

    if is_rate_limited(uid):
        await query.answer(t(uid, "rate_limited"), show_alert=True)
        return

    # Basic UI Navigation
    if data == "show_main":
        user_states[uid] = None
        await query.edit_message_text(t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown")
    elif data == "show_tools":
        await query.edit_message_text(t(uid, "tools_menu"), reply_markup=tools_menu_keyboard(uid), parse_mode="Markdown")
    elif data == "show_help":
        await query.edit_message_text(t(uid, "help_text"), reply_markup=back_keyboard(uid), parse_mode="Markdown")
    elif data == "show_lang":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("English 🇬🇧", callback_data="lang_en"), InlineKeyboardButton("Español 🇪🇸", callback_data="lang_es")],
            [InlineKeyboardButton("Français 🇫🇷", callback_data="lang_fr"), InlineKeyboardButton("Português 🇧🇷", callback_data="lang_pt")],
            [InlineKeyboardButton("العربية 🇸🇦", callback_data="lang_ar"), InlineKeyboardButton(t(uid, "btn_back"), callback_data="show_main")]
        ])
        await query.edit_message_text(t(uid, "choose_lang"), reply_markup=kb, parse_mode="Markdown")
        
    # Set States
    elif data.startswith("ask_"):
        user_states[uid] = f"waiting_for_{data[4:]}"
        await query.edit_message_text(t(uid, data), reply_markup=back_keyboard(uid), parse_mode="Markdown")
    elif data.startswith("lang_"):
        user_languages[uid] = data[5:]
        await query.edit_message_text(t(uid, "lang_set") + t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown")

    # The New Cobalt Downloader trigger
    elif data.startswith("dl_"):
        link = context.user_data.get("last_link")
        if not link:
            await query.edit_message_text(t(uid, "error") + " No link stored. Please paste a link first.")
            return

        fmt_key = data[3:]
        prefix = f"{uid}_media"
        cleanup(f"{prefix}*")

        base_text = t(uid, "downloading")
        msg = await query.edit_message_text(base_text)
        stop = asyncio.Event()
        anim = asyncio.create_task(_animate(msg, stop, base_text))

        try:
            # Passes to our new custom Cobalt function!
            final_file = await asyncio.to_thread(_run_cobalt_download, link, fmt_key, prefix)
            stop.set(); anim.cancel()

            with open(final_file, "rb") as fh:
                if fmt_key == "mp3": await context.bot.send_audio(chat_id=uid, audio=fh)
                else: await context.bot.send_video(chat_id=uid, video=fh)
            try: await msg.delete()
            except Exception: pass

        except ValueError as ve:
            stop.set(); anim.cancel()
            if str(ve) == "FILE_TOO_LARGE":
                await context.bot.send_message(chat_id=uid, text=t(uid, "file_too_large"))
            else:
                await context.bot.send_message(chat_id=uid, text=f"{t(uid, 'error')}\n`{ve}`")
        except Exception as exc:
            stop.set(); anim.cancel()
            logger.error("Download Error uid=%s: %s", uid, exc)
            await context.bot.send_message(chat_id=uid, text=f"{t(uid, 'error')}\n`{exc}`")
        finally:
            cleanup(f"{prefix}*")

# ══════════════════════════════════════════════════════════
# 11. ENTRY POINT
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    keep_alive()
    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("help", help_command))
    bot_app.add_handler(CommandHandler("broadcast", broadcast_command))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    logger.info("Bot is running…")
    bot_app.run_polling(drop_pending_updates=True)
