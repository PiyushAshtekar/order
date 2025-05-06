import os
import logging
from dotenv import load_dotenv
from quart import Quart, request, render_template, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from telegram.constants import ParseMode

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Set this on Render (e.g., https://your-app.onrender.com)

# Quart app
quart_app = Quart(__name__)

# Global cart (in-memory)
user_carts = {}

@quart_app.route('/')
async def index():
    return "🤖 Bot is running!"

@quart_app.route('/menu')
async def menu():
    return await render_template('menu.html')

# --- Telegram Bot Logic ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_carts[chat_id] = []

    # Send welcome image
    try:
        with open('static/burger.png', 'rb') as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption="🍔 Welcome to Raju Burger!\nUse this bot to order fictional fast food – the only fast food that is good for your health!\n\nLet's get started! 🎉"
            )
    except Exception as e:
        logging.error(f"Failed to send image: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="🍔 Welcome to Raju Burger!\nLet's get started! 🎉"
        )

    keyboard = [
        [InlineKeyboardButton("🛒 Order Food", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/menu"))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please tap below to order your perfect lunch! 🍽️", reply_markup=reply_markup)

# --- Telegram Webhook Handler ---
async def handle_webhook(req):
    try:
        data = await req.get_data()
        update = Update.de_json(data.decode("utf-8"), bot)
        await application.process_update(update)
    except Exception as e:
        logging.error(f"Error processing webhook: {e}")
    return Response("OK", status=200)

@quart_app.route('/telegram-webhook', methods=['POST'])
async def telegram_webhook():
    return await handle_webhook(request)

# --- Initialize Bot ---
application = ApplicationBuilder().token(BOT_TOKEN).build()
bot = application.bot

async def post_init(app: ApplicationBuilder):
    logging.info("Setting Telegram webhook...")
    await app.bot.set_webhook(f"{WEBHOOK_URL}/telegram-webhook")
    logging.info("Webhook set successfully.")

# Register handlers
application.add_handler(CommandHandler("start", start))

# --- Start the App ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import asyncio

    async def run():
        await post_init(application)
        await quart_app.run_task(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

    asyncio.run(run())
