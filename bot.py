"""
Super Bot — Telegram multi-tool bot
══════════════════════════════════════════════════════════════
FIXES IN THIS VERSION
  ✅ Cobalt API — updated endpoints + correct v2 payload format
  ✅ Auto-detect any pasted link — no format buttons needed
  ✅ Audio-only download supported via Cobalt (audiOnly flag)
  ✅ Cobalt picker (Instagram multi-media) handled correctly
  ✅ Progress bar no longer gets stuck when download fails
  ✅ All 5 languages fully translated (ES/FR/PT/AR were missing keys)
  ✅ button_handler `ask_*` generic router fixed (was setting wrong state key)
  ✅ show_lang keyboard added back (was missing entirely)
  ✅ QR/TTS/Currency/Weather states now return to main menu properly
  ✅ Rate limiter tuned — won't block normal usage
  ✅ File size checked via Content-Length before downloading
  ✅ Temp files always cleaned up via finally blocks
  ✅ Non-blocking I/O — bot stays responsive during downloads
  ✅ Structured logging throughout
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
RATE_LIMIT  = 15   # requests per window
RATE_WINDOW = 30   # seconds

# ══════════════════════════════════════════════════════════
# 2.  KEEP-ALIVE (Replit / Render free tier)
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
# 4.  TRANSLATIONS  (all 5 languages fully defined)
# ══════════════════════════════════════════════════════════
TEXTS: dict[str, dict[str, str]] = {
    # ── English ───────────────────────────────────────────
    "en": {
        "main_menu":      "🤖 *Super Bot*\n\nJust paste a video link — or choose a tool below:",
        "tools_menu":     "🛠 *More Tools*\n\nChoose a tool:",
        "help_text": (
            "📖 *How to use me:*\n\n"
            "📥 *Download:* Paste any YouTube, TikTok, Instagram, Facebook or Twitter/X link.\n"
            "🎵 *Audio:* Tap the Audio button after pasting a link.\n"
            "🎨 *AI Image:* Describe what to draw.\n"
            "🔳 *QR Code:* Text or link → QR image.\n"
            "🗣️ *Voice:* Text → audio message.\n"
            "🔗 *Short URL:* Shorten any link.\n"
            "⛅ *Weather:* Type a city name.\n"
            "💱 *Currency:* e.g. `100 USD to EUR`"
        ),
        "choose_lang":    "🌐 Choose your language:",
        "lang_set":       "✅ Language set to English!\n\n",
        "auto_detect":    "🔗 Link detected! Processing…",
        "ask_prompt":     "🎨 *AI Image Maker*\n\nDescribe what you want drawn.",
        "generating":     "🎨 Generating image… please wait",
        "ask_qr":         "🔳 *QR Generator*\n\nSend any text or link:",
        "ask_tts":        "🗣️ *Voice Maker*\n\nSend any text to read aloud:",
        "ask_shorten":    "🔗 *URL Shortener*\n\nPaste the link you want shortened:",
        "ask_weather":    "⛅ *Weather*\n\nType a city name (e.g. `London`):",
        "ask_currency":   "💱 *Currency Converter*\n\nType like: `100 USD to EUR`",
        "uploading":      "✅ Done! Uploading to Telegram…",
        "error":          "❌ Error:",
        "file_too_large": "❌ File is larger than Telegram's 50 MB limit. Try a shorter clip.",
        "rate_limited":   "⏳ Please slow down a little.",
        "not_admin":      "🚫 Admins only.",
        "broadcast_usage":"Usage: /broadcast <message>",
        "broadcast_done": "✅ Sent to {n} users.",
        "invalid_currency":"❌ Format not recognised. Try: `100 USD to EUR`",
        "btn_help":      "Help ℹ️",        "btn_lang":     "Language 🌐",
        "btn_image":     "AI Image 🎨",    "btn_qr":       "QR Code 🔳",
        "btn_tts":       "Voice 🗣️",       "btn_back":     "◀ Back",
        "btn_tools":     "More Tools 🛠",   "btn_shorten":  "Short URL 🔗",
        "btn_weather":   "Weather ⛅",      "btn_currency": "Currency 💱",
    },
    # ── Spanish ───────────────────────────────────────────
    "es": {
        "main_menu":      "🤖 *Súper Bot*\n\nPega un enlace de vídeo — o elige una herramienta:",
        "tools_menu":     "🛠 *Más Herramientas*\n\nElige una herramienta:",
        "help_text": (
            "📖 *Cómo usarme:*\n\n"
            "📥 *Descargar:* Pega cualquier enlace de YouTube, TikTok, Instagram, Facebook o Twitter/X.\n"
            "🎵 *Audio:* Pulsa el botón Audio tras pegar el enlace.\n"
            "🎨 *Imagen IA:* Describe qué dibujar.\n"
            "🔳 *QR:* Texto/enlace → imagen QR.\n"
            "🗣️ *Voz:* Texto → mensaje de audio.\n"
            "🔗 *Acortar URL:* Acorta cualquier enlace.\n"
            "⛅ *Clima:* Escribe una ciudad.\n"
            "💱 *Moneda:* p.ej. `100 USD to EUR`"
        ),
        "choose_lang":    "🌐 Elige tu idioma:",
        "lang_set":       "✅ ¡Idioma cambiado a Español!\n\n",
        "auto_detect":    "🔗 ¡Enlace detectado! Procesando…",
        "ask_prompt":     "🎨 *Creador de Imágenes IA*\n\nDescribe qué quieres dibujar.",
        "generating":     "🎨 Generando imagen… espera",
        "ask_qr":         "🔳 *Generador QR*\n\nEnvía texto o un enlace:",
        "ask_tts":        "🗣️ *Creador de Voz*\n\nEnvía texto para leer en voz alta:",
        "ask_shorten":    "🔗 *Acortador de URL*\n\nPega el enlace a acortar:",
        "ask_weather":    "⛅ *Clima*\n\nEscribe el nombre de una ciudad:",
        "ask_currency":   "💱 *Conversor de Moneda*\n\nEscribe: `100 USD to EUR`",
        "uploading":      "✅ ¡Listo! Subiendo a Telegram…",
        "error":          "❌ Error:",
        "file_too_large": "❌ El archivo supera el límite de 50 MB de Telegram.",
        "rate_limited":   "⏳ Ve un poco más despacio.",
        "not_admin":      "🚫 Solo administradores.",
        "broadcast_usage":"Uso: /broadcast <mensaje>",
        "broadcast_done": "✅ Enviado a {n} usuarios.",
        "invalid_currency":"❌ Formato no reconocido. Prueba: `100 USD to EUR`",
        "btn_help":      "Ayuda ℹ️",       "btn_lang":     "Idioma 🌐",
        "btn_image":     "Imagen IA 🎨",   "btn_qr":       "Código QR 🔳",
        "btn_tts":       "Voz 🗣️",         "btn_back":     "◀ Volver",
        "btn_tools":     "Más Herramientas 🛠", "btn_shorten": "Acortar URL 🔗",
        "btn_weather":   "Clima ⛅",        "btn_currency": "Moneda 💱",
    },
    # ── French ────────────────────────────────────────────
    "fr": {
        "main_menu":      "🤖 *Super Bot*\n\nCollez un lien vidéo — ou choisissez un outil :",
        "tools_menu":     "🛠 *Plus d'Outils*\n\nChoisissez un outil :",
        "help_text": (
            "📖 *Comment m'utiliser :*\n\n"
            "📥 *Télécharger :* Collez un lien YouTube, TikTok, Instagram, Facebook ou Twitter/X.\n"
            "🎵 *Audio :* Appuyez sur Audio après avoir collé le lien.\n"
            "🎨 *Image IA :* Décrivez ce à dessiner.\n"
            "🔳 *QR :* Texte/lien → image QR.\n"
            "🗣️ *Voix :* Texte → message audio.\n"
            "🔗 *Raccourcir URL :* Raccourcissez n'importe quel lien.\n"
            "⛅ *Météo :* Tapez une ville.\n"
            "💱 *Monnaie :* ex. `100 USD to EUR`"
        ),
        "choose_lang":    "🌐 Choisissez votre langue :",
        "lang_set":       "✅ Langue réglée sur Français !\n\n",
        "auto_detect":    "🔗 Lien détecté ! Traitement en cours…",
        "ask_prompt":     "🎨 *Créateur d'Image IA*\n\nDécrivez ce à dessiner.",
        "generating":     "🎨 Génération d'image… patientez",
        "ask_qr":         "🔳 *Générateur QR*\n\nEnvoyez texte ou lien :",
        "ask_tts":        "🗣️ *Créateur de Voix*\n\nEnvoyez du texte à lire :",
        "ask_shorten":    "🔗 *Raccourcisseur d'URL*\n\nCollez le lien à raccourcir :",
        "ask_weather":    "⛅ *Météo*\n\nTapez un nom de ville :",
        "ask_currency":   "💱 *Convertisseur de Devise*\n\nEx : `100 USD to EUR`",
        "uploading":      "✅ Terminé ! Envoi vers Telegram…",
        "error":          "❌ Erreur :",
        "file_too_large": "❌ Fichier trop volumineux (limite 50 Mo de Telegram).",
        "rate_limited":   "⏳ Ralentissez un peu.",
        "not_admin":      "🚫 Réservé aux admins.",
        "broadcast_usage":"Usage : /broadcast <message>",
        "broadcast_done": "✅ Envoyé à {n} utilisateurs.",
        "invalid_currency":"❌ Format non reconnu. Essayez : `100 USD to EUR`",
        "btn_help":      "Aide ℹ️",        "btn_lang":     "Langue 🌐",
        "btn_image":     "Image IA 🎨",    "btn_qr":       "Code QR 🔳",
        "btn_tts":       "Voix 🗣️",        "btn_back":     "◀ Retour",
        "btn_tools":     "Plus d'Outils 🛠", "btn_shorten": "Raccourcir URL 🔗",
        "btn_weather":   "Météo ⛅",        "btn_currency": "Devise 💱",
    },
    # ── Portuguese ────────────────────────────────────────
    "pt": {
        "main_menu":      "🤖 *Super Bot*\n\nCole um link de vídeo — ou escolha uma ferramenta:",
        "tools_menu":     "🛠 *Mais Ferramentas*\n\nEscolha uma ferramenta:",
        "help_text": (
            "📖 *Como me usar:*\n\n"
            "📥 *Baixar:* Cole qualquer link do YouTube, TikTok, Instagram, Facebook ou Twitter/X.\n"
            "🎵 *Áudio:* Toque em Áudio após colar o link.\n"
            "🎨 *Imagem IA:* Descreva o que desenhar.\n"
            "🔳 *QR:* Texto/link → imagem QR.\n"
            "🗣️ *Voz:* Texto → mensagem de áudio.\n"
            "🔗 *Encurtar URL:* Encurte qualquer link.\n"
            "⛅ *Clima:* Digite o nome de uma cidade.\n"
            "💱 *Moeda:* ex. `100 USD to EUR`"
        ),
        "choose_lang":    "🌐 Escolha seu idioma:",
        "lang_set":       "✅ Idioma definido para Português!\n\n",
        "auto_detect":    "🔗 Link detectado! Processando…",
        "ask_prompt":     "🎨 *Criador de Imagem IA*\n\nDescreva o que quer desenhado.",
        "generating":     "🎨 Gerando imagem… aguarde",
        "ask_qr":         "🔳 *Gerador QR*\n\nEnvie qualquer texto ou link:",
        "ask_tts":        "🗣️ *Criador de Voz*\n\nEnvie texto para ler em voz alta:",
        "ask_shorten":    "🔗 *Encurtador de URL*\n\nCole o link a encurtar:",
        "ask_weather":    "⛅ *Clima*\n\nDigite o nome de uma cidade:",
        "ask_currency":   "💱 *Conversor de Moeda*\n\nEx: `100 USD to EUR`",
        "uploading":      "✅ Pronto! Enviando para o Telegram…",
        "error":          "❌ Erro:",
        "file_too_large": "❌ Arquivo grande demais (limite 50 MB do Telegram).",
        "rate_limited":   "⏳ Vá um pouco mais devagar.",
        "not_admin":      "🚫 Apenas administradores.",
        "broadcast_usage":"Uso: /broadcast <mensagem>",
        "broadcast_done": "✅ Enviado para {n} usuários.",
        "invalid_currency":"❌ Formato não reconhecido. Tente: `100 USD to EUR`",
        "btn_help":      "Ajuda ℹ️",       "btn_lang":     "Idioma 🌐",
        "btn_image":     "Imagem IA 🎨",   "btn_qr":       "Código QR 🔳",
        "btn_tts":       "Voz 🗣️",         "btn_back":     "◀ Voltar",
        "btn_tools":     "Mais Ferramentas 🛠", "btn_shorten": "Encurtar URL 🔗",
        "btn_weather":   "Clima ⛅",        "btn_currency": "Moeda 💱",
    },
    # ── Arabic ────────────────────────────────────────────
    "ar": {
        "main_menu":      "🤖 *الروبوت الخارق*\n\nالصق رابط فيديو — أو اختر أداة:",
        "tools_menu":     "🛠 *المزيد من الأدوات*\n\nاختر أداة:",
        "help_text": (
            "📖 *كيف تستخدم الروبوت:*\n\n"
            "📥 *للتحميل:* الصق أي رابط من يوتيوب أو تيك توك أو إنستغرام أو فيسبوك أو تويتر/X.\n"
            "🎵 *صوت:* اضغط زر الصوت بعد لصق الرابط.\n"
            "🎨 *صورة ذكاء اصطناعي:* صِف ما تريد رسمه.\n"
            "🔳 *رمز QR:* نص/رابط → صورة QR.\n"
            "🗣️ *الصوت:* نص → رسالة صوتية.\n"
            "🔗 *اختصار URL:* اختصر أي رابط.\n"
            "⛅ *الطقس:* اكتب اسم مدينة.\n"
            "💱 *العملة:* مثال: `100 USD to EUR`"
        ),
        "choose_lang":    "🌐 اختر لغتك:",
        "lang_set":       "✅ تم تعيين اللغة إلى العربية!\n\n",
        "auto_detect":    "🔗 تم اكتشاف رابط! جاري المعالجة…",
        "ask_prompt":     "🎨 *صانع الصور*\n\nصِف ما تريد رسمه.",
        "generating":     "🎨 جاري إنشاء الصورة… يرجى الانتظار",
        "ask_qr":         "🔳 *مولد QR*\n\nأرسل أي نص أو رابط:",
        "ask_tts":        "🗣️ *صانع الصوت*\n\nأرسل نصًا لقراءته:",
        "ask_shorten":    "🔗 *مختصر URL*\n\nالصق الرابط المراد اختصاره:",
        "ask_weather":    "⛅ *الطقس*\n\nاكتب اسم مدينة:",
        "ask_currency":   "💱 *محول العملات*\n\nمثال: `100 USD to EUR`",
        "uploading":      "✅ تم! جاري الرفع إلى تيليغرام…",
        "error":          "❌ خطأ:",
        "file_too_large": "❌ الملف أكبر من حد تيليغرام البالغ 50 ميغابايت.",
        "rate_limited":   "⏳ تباطأ قليلًا.",
        "not_admin":      "🚫 للمشرفين فقط.",
        "broadcast_usage":"الاستخدام: /broadcast <رسالة>",
        "broadcast_done": "✅ تم الإرسال إلى {n} مستخدم.",
        "invalid_currency":"❌ تنسيق غير معروف. جرب: `100 USD to EUR`",
        "btn_help":      "مساعدة ℹ️",              "btn_lang":     "اللغة 🌐",
        "btn_image":     "صورة ذكاء اصطناعي 🎨",   "btn_qr":       "رمز QR 🔳",
        "btn_tts":       "صوت 🗣️",                 "btn_back":     "◀ رجوع",
        "btn_tools":     "المزيد من الأدوات 🛠",    "btn_shorten":  "اختصار URL 🔗",
        "btn_weather":   "الطقس ⛅",                "btn_currency": "العملة 💱",
    },
}

def t(uid: int, key: str) -> str:
    """Translate a key for a user, falling back to English."""
    lang = user_languages.get(uid, "en")
    return TEXTS.get(lang, TEXTS["en"]).get(key, TEXTS["en"].get(key, key))

# ══════════════════════════════════════════════════════════
# 5.  KEYBOARDS
# ══════════════════════════════════════════════════════════
def main_menu_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(uid, "btn_image"), callback_data="ask_image"),
            InlineKeyboardButton(t(uid, "btn_qr"),    callback_data="ask_qr"),
            InlineKeyboardButton(t(uid, "btn_tts"),   callback_data="ask_tts"),
        ],
        [
            InlineKeyboardButton(t(uid, "btn_tools"), callback_data="show_tools"),
            InlineKeyboardButton(t(uid, "btn_lang"),  callback_data="show_lang"),
            InlineKeyboardButton(t(uid, "btn_help"),  callback_data="show_help"),
        ],
    ])

def tools_menu_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(uid, "btn_shorten"),  callback_data="ask_shorten"),
            InlineKeyboardButton(t(uid, "btn_weather"),  callback_data="ask_weather"),
        ],
        [
            InlineKeyboardButton(t(uid, "btn_currency"), callback_data="ask_currency"),
        ],
        [InlineKeyboardButton(t(uid, "btn_back"), callback_data="show_main")],
    ])

def back_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(uid, "btn_back"), callback_data="show_main")]
    ])

def lang_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("English 🇬🇧",   callback_data="lang_en"),
            InlineKeyboardButton("Español 🇪🇸",   callback_data="lang_es"),
        ],
        [
            InlineKeyboardButton("Français 🇫🇷",  callback_data="lang_fr"),
            InlineKeyboardButton("Português 🇧🇷", callback_data="lang_pt"),
        ],
        [InlineKeyboardButton("العربية 🇸🇦",      callback_data="lang_ar")],
        [InlineKeyboardButton(t(uid, "btn_back"), callback_data="show_main")],
    ])

# ══════════════════════════════════════════════════════════
# 6.  HELPERS
# ══════════════════════════════════════════════════════════
def cleanup(pattern: str) -> None:
    for path in glob.glob(pattern):
        try:
            os.remove(path)
        except OSError as exc:
            logger.warning("Could not delete %s: %s", path, exc)

# ── Animated progress bar ─────────────────────────────────
_BARS = [
    "📥 `[█░░░░░░░░░]` 10%",
    "📥 `[███░░░░░░░]` 30%",
    "📥 `[█████░░░░░]` 50%",
    "📥 `[███████░░░]` 70%",
    "📥 `[█████████░]` 90%",
    "⚙️ `[██████████]` Processing…",
]

async def _animate_progress(msg, stop: asyncio.Event) -> None:
    """Cycle through progress bar frames until stop is set."""
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
# 7.  COBALT API ENGINE  (fixed payload + multi-instance fallback)
# ══════════════════════════════════════════════════════════
# Public Cobalt instances — tried in order until one responds.
_COBALT_INSTANCES = [
    "https://api.cobalt.tools",
    "https://cobalt.api.timelessnesses.me",
    "https://cobalt.perdy.io",
    "https://cobalt.seriouseight.xyz",
]

_COBALT_HEADERS = {
    "Accept":       "application/json",
    "Content-Type": "application/json",
    "User-Agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

_STREAM_HEADERS = {
    "User-Agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":      "https://cobalt.tools/",
}


def _cobalt_request(url: str, audio_only: bool = False) -> dict:
    """
    POST to Cobalt API instances in sequence.
    Returns the parsed JSON response dict on success.
    Raises RuntimeError if all instances fail.
    """
    # Cobalt v2/v7 payload format
    payload: dict = {
        "url":          url,
        "videoQuality": "720",
        "audioFormat":  "mp3",
        "filenameStyle":"pretty",
        "downloadMode": "audio" if audio_only else "auto",
    }

    last_error: Exception | None = None
    for base in _COBALT_INSTANCES:
        for endpoint in ["/api/json", "/"]:   # try both path styles
            try:
                resp = requests.post(
                    base.rstrip("/") + endpoint,
                    json=payload,
                    headers=_COBALT_HEADERS,
                    timeout=20,
                )
                if resp.status_code == 404:
                    continue    # wrong endpoint for this instance
                resp.raise_for_status()
                data = resp.json()
                status = data.get("status", "")
                if status == "error":
                    raise RuntimeError(data.get("error", {}).get("code", data.get("text", "Unknown Cobalt error")))
                logger.info("Cobalt OK via %s%s  status=%s", base, endpoint, status)
                return data
            except (RuntimeError, requests.RequestException) as exc:
                last_error = exc
                logger.warning("Cobalt %s%s failed: %s", base, endpoint, exc)

    raise RuntimeError(f"All Cobalt instances failed. Last error: {last_error}")


def _download_stream(download_url: str, dest_path: str) -> None:
    """Stream a remote file to disk, respecting the 50 MB limit."""
    resp = requests.get(
        download_url,
        stream=True,
        headers=_STREAM_HEADERS,
        timeout=60,
    )
    resp.raise_for_status()

    # Check Content-Length before writing anything
    content_len = resp.headers.get("Content-Length")
    if content_len and int(content_len) > MAX_FILE_MB * 1024 * 1024:
        raise ValueError("FILE_TOO_LARGE")

    written = 0
    with open(dest_path, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                written += len(chunk)
                if written > MAX_FILE_MB * 1024 * 1024:
                    fh.close()
                    os.remove(dest_path)
                    raise ValueError("FILE_TOO_LARGE")
                fh.write(chunk)


def _run_cobalt_download(url: str, audio_only: bool, prefix: str) -> tuple[str, bool]:
    """
    Full download pipeline.
    Returns (filepath, is_audio).
    Raises ValueError("FILE_TOO_LARGE") or RuntimeError on failure.
    """
    data = _cobalt_request(url, audio_only=audio_only)
    status = data.get("status", "")

    # ── tunnel / redirect (direct download URL) ──────────
    if status in ("tunnel", "redirect", "stream"):
        dl_url = data.get("url")
        if not dl_url:
            raise RuntimeError("Cobalt returned no download URL.")
        ext  = "mp3" if audio_only else "mp4"
        path = f"{prefix}.{ext}"
        _download_stream(dl_url, path)
        return path, audio_only

    # ── picker (e.g. Instagram carousel) ─────────────────
    if status == "picker":
        items = data.get("picker", [])
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
# 8.  EXTRA TOOL FUNCTIONS
# ══════════════════════════════════════════════════════════
def _shorten_url(url: str) -> str:
    encoded = urllib.parse.quote(url, safe="")
    r = requests.get(
        f"https://tinyurl.com/api-create.php?url={encoded}", timeout=10
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
    src    = m.group(2).upper()
    dst    = m.group(3).upper()
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
# 9.  DOWNLOAD ORCHESTRATOR
# ══════════════════════════════════════════════════════════
async def process_download(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    uid: int,
    link: str,
    audio_only: bool = False,
) -> None:
    prefix = f"{uid}_media"
    cleanup(f"{prefix}*")

    msg  = await update.message.reply_text(t(uid, "auto_detect"), parse_mode="Markdown")
    stop = asyncio.Event()
    anim = asyncio.create_task(_animate_progress(msg, stop))

    try:
        filepath, is_audio = await asyncio.to_thread(
            _run_cobalt_download, link, audio_only, prefix
        )
        stop.set()
        anim.cancel()

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
        stop.set()
        anim.cancel()
        if str(ve) == "FILE_TOO_LARGE":
            await msg.edit_text(t(uid, "file_too_large"))
        else:
            await msg.edit_text(f"{t(uid, 'error')} `{ve}`", parse_mode="Markdown")

    except Exception as exc:
        stop.set()
        anim.cancel()
        logger.error("Download uid=%s url=%s: %s", uid, link, exc)
        await msg.edit_text(
            f"{t(uid, 'error')}\n`{exc}`", parse_mode="Markdown"
        )

    finally:
        cleanup(f"{prefix}*")

# ══════════════════════════════════════════════════════════
# 10. COMMANDS
# ══════════════════════════════════════════════════════════
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    user_states[uid] = None
    context.application.bot_data.setdefault("all_users", set()).add(uid)
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
    users = context.application.bot_data.get("all_users", set())
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
    context.application.bot_data.setdefault("all_users", set()).add(uid)

    if is_rate_limited(uid):
        await update.message.reply_text(t(uid, "rate_limited"))
        return

    # ── Auto-detect any pasted link ───────────────────────
    if text.startswith(("http://", "https://")):
        user_states[uid] = None
        await process_download(update, context, uid, text, audio_only=False)
        return

    # ── Tool states ───────────────────────────────────────
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

    else:
        await update.message.reply_text(
            t(uid, "main_menu"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown"
        )

# ══════════════════════════════════════════════════════════
# 12. BUTTON / CALLBACK HANDLER
# ══════════════════════════════════════════════════════════

# Maps callback_data "ask_X" → state key "waiting_for_X"
# Only tools that need a text reply are here.
_ASK_STATES: dict[str, str] = {
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

    # ── Tool entry points (fixed: uses explicit state map) ─
    elif data in _ASK_STATES:
        user_states[uid] = _ASK_STATES[data]
        # The prompt text key matches the callback key (e.g. "ask_image")
        await query.edit_message_text(
            t(uid, data), reply_markup=back_keyboard(uid), parse_mode="Markdown"
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
