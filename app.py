import os
import logging
from flask import Flask, render_template
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", 5000))

# Flask app
flask_app = Flask(__name__)

# Global cart (in-memory)
user_carts = {}

@flask_app.route('/')
def index():
    return "🤖 Bot is running!"

@flask_app.route('/menu')
def menu():
    return render_template('menu.html')

# Telegram bot setup
app = ApplicationBuilder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_carts[chat_id] = []

    # Send burger image
    try:
        with open('static/burger.png', 'rb') as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption="🍔 Welcome to Raju Burger! 🍔\n\nUse this bot to order fictional fast food – the only fast food that is good for your health!\n\nLet's get started! 🎉"
            )
    except Exception as e:
        logging.error(f"Failed to send welcome image: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="🍔 Welcome to Raju Burger! 🍔\n\nUse this bot to order fictional fast food – the only fast food that is good for your health!\n\nLet's get started! 🎉"
        )

    keyboard = [
        [InlineKeyboardButton("🛒 Order Food", web_app=WebAppInfo(url="https://order-rhgz.onrender.com/menu"))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please tap the button below to order your perfect lunch! 🍽️", reply_markup=reply_markup)


def main():
    # Logging
    logging.basicConfig(level=logging.INFO)
    
    # Add start handler
    app.add_handler(CommandHandler("start", start))

    # Start polling
    app.run_polling()

if __name__ == "__main__":
    main()
    flask_app.run(host="0.0.0.0", port=PORT)