import os
import logging
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode
import asyncio

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Ensure this is set in Render's environment

# Flask app
flask_app = Flask(__name__)

# Global cart (in-memory) - Consider persistent storage for real applications
user_carts = {}

@flask_app.route('/')
def index():
    return "🤖 Bot is running!"

@flask_app.route('/menu')
def menu():
    return render_template('menu.html')

# --- Telegram Bot Logic ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_carts[chat_id] = []

    # Send burger image
    try:
        # Assuming 'static/burger.png' is in the same directory or accessible
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
        [InlineKeyboardButton("🛒 Order Food", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/menu"))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please tap the button below to order your perfect lunch! 🍽️", reply_markup=reply_markup)

# --- Webhook Handling ---
async def handle_webhook(request):
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    try:
        update = Update.de_json(await request.get_data().decode("utf-8"), app.bot)
        logging.info(f"Received update: {update}")  # Log the entire update
        await app.process_update(update)
    except Exception as e:
        logging.error(f"Error processing webhook: {e}")
    return "OK"

@flask_app.route('/telegram-webhook', methods=['POST'])
async def telegram_webhook():
    return await handle_webhook(request)

async def post_init(app: ApplicationBuilder):
    logging.info("Running post_init to set webhook...")
    try:
        await app.bot.set_webhook(f"{WEBHOOK_URL}/telegram-webhook")
        logging.info(f"Webhook set to: {WEBHOOK_URL}/telegram-webhook")
    except Exception as e:
        logging.error(f"Error setting webhook: {e}")

def main():
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    logging.info(f"Application object: {app}") # Log the application object
    app.add_handler(CommandHandler("start", start))

    async def run_app():
        await app.initialize()
        await app.start()
        # We don't need to run app.updater.start() for webhook

    asyncio.run(run_app())

    # Note: We are not running app.run_polling() here. Flask will handle the incoming webhook.

if __name__ == "__main__":
    main()
    flask_app.run(host="0.0.0.0")