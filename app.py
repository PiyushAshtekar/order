import os
import logging
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

load_dotenv()

# Bot credentials
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
print("BOT_TOKEN")
print(BOT_TOKEN)
PORT = int(os.environ.get('PORT', 8443))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://order-rhgz.onrender.com/webhook")  # Replace with your deployed URL

# Flask app
flask_app = Flask(__name__)

# Telegram handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🛒 Add to Cart", web_app={"url": "https://order-rhgz.onrender.com"})]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome! Click below to open the cart.", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=f"You clicked: {query.data}")

async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.effective_message.web_app_data.data
    logging.info(f"Received web app data: {data}")
    await update.message.reply_text(f"✅ Received your cart data:\n{data}")

# Set webhook
def set_webhook():
    from telegram import Bot
    bot = Bot(BOT_TOKEN)
    bot.set_webhook(WEBHOOK_URL)

# Webhook route
@flask_app.route('/', methods=['GET'])
def index():
    return "Telegram Bot is running!", 200

# Initialize and run
if __name__ == '__main__':
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )

    # Create Telegram application
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))

    # Set webhook
    set_webhook()

    # Run Flask app
    flask_app.run(host='0.0.0.0', port=PORT)
