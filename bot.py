import os
import requests
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- 1. KEEP-ALIVE WEBSITE CODE ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is awake and running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()


# --- 2. NEW BOT FEATURES ---

# The /start command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = "Hello! Try these commands:\n/joke - Get a random joke\n/menu - See some buttons"
    await update.message.reply_text(welcome_message)

# The /joke command
async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Let me think of a joke...")
    # Fetch a joke from a free API
    response = requests.get("https://official-joke-api.appspot.com/random_joke")
    joke_data = response.json()
    # Send the joke
    await update.message.reply_text(f"{joke_data['setup']}\n\n... {joke_data['punchline']} 😆")

# The /menu command (Clickable Buttons)
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Create the buttons
    keyboard = [
        [InlineKeyboardButton("Say Hello 👋", callback_data='hello')],
        [InlineKeyboardButton("Tell me my ID 🆔", callback_data='id')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Please choose an option:', reply_markup=reply_markup)

# This handles what happens when a user clicks a button
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # This stops the loading animation on the button

    if query.data == 'hello':
        await query.edit_message_text(text="Hello there, my friend! 👋")
    elif query.data == 'id':
        user_id = query.from_user.id
        await query.edit_message_text(text=f"Your secret Telegram ID is: {user_id}")

# Normal text message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text(f"You said: {text}\n(Try typing /menu or /joke!)")


# --- 3. START THE BOT ---
if __name__ == '__main__':
    keep_alive() # Start the fake website
    
    # PUT YOUR TOKEN HERE!
    TOKEN = "8590047923:AAFuBw1yg117VIiFVUU3xBicp8b71TSuHn0" 
    
    bot_app = Application.builder().token(TOKEN).build()
    
    # Add our new commands to the bot
    bot_app.add_handler(CommandHandler('start', start_command))
    bot_app.add_handler(CommandHandler('joke', joke_command))
    bot_app.add_handler(CommandHandler('menu', menu_command))
    
    # Add the button handler
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    
    # Add the normal text handler
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot is running...")
    bot_app.run_polling()
