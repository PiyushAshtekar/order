import os
import logging
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ParseMode
import asyncio

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Flask app
flask_app = Flask(__name__)
bot_app = None  # Global variable to hold the Telegram Application

async def set_webhook():
    global bot_app
    if bot_app:
        logging.info("Setting webhook...")
        try:
            await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/telegram-webhook")
            logging.info(f"Webhook set to: {WEBHOOK_URL}/telegram-webhook")
        except Exception as e:
            logging.error(f"Error setting webhook: {e}")

@flask_app.before_first_request
def initialize_bot():
    global bot_app
    logging.basicConfig(level=logging.INFO)
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    asyncio.create_task(set_webhook())
    logging.info("Telegram bot application initialized.")

@flask_app.route('/')
def index():
    return "🤖 Bot is running!"

@flask_app.route('/menu')
def menu():
    return render_template('menu.html')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_carts = {}  # Initialize user_carts here for each command

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

async def handle_webhook(request):
    global bot_app
    if not bot_app:
        return "Bot not initialized", 503
    try:
        update = Update.de_json(await request.get_data().decode("utf-8"), bot_app.bot)
        logging.info(f"Received update: {update}")
        await bot_app.process_update(update)
    except Exception as e:
        logging.error(f"Error processing webhook: {e}")
    return "OK"

@flask_app.route('/telegram-webhook', methods=['POST'])
async def telegram_webhook():
    return await handle_webhook(request)

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0")