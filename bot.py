import os
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- 1. KEEP-ALIVE WEBSITE CODE ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is awake and running!"

def run_flask():
    # Render assigns a port automatically, so we need to fetch it
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# --- 2. TELEGRAM BOT CODE ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I am online 24/7!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text(f"You said: {text}")

if __name__ == '__main__':
    # Start the fake website first
    keep_alive()

    # Start the Telegram bot
    # PUT YOUR TOKEN HERE:
    TOKEN = "YOUR_TOKEN_HERE"

    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler('start', start_command))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    bot_app.run_polling()
