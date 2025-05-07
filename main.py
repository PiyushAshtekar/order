import os
import sys
import json
import logging
from dotenv import load_dotenv
from quart import Quart, request, render_template, Response, send_file
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters)
from utils import generate_token, generate_order_pdf
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Set this on Render (e.g., https://your-app.onrender.com)

# Validate environment variables
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN environment variable is missing!")
    sys.exit(1)
    
if not WEBHOOK_URL:
    logger.error("WEBHOOK_URL environment variable is missing!")
    sys.exit(1)

logger.info(f"Using webhook URL: {WEBHOOK_URL}")

# Quart app
quart_app = Quart(__name__)

# Global cart (in-memory)
user_carts = {}

@quart_app.route('/')
async def index():
    logger.info("Root endpoint accessed")
    return "🤖 Raju Burger Bot is running!"

@quart_app.route('/menu')
async def menu():
    logger.info("Menu endpoint accessed")
    return await render_template('menu.html')

# --- Telegram Bot Logic ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Start command received from user {update.effective_user.id}")
    
    chat_id = update.effective_chat.id
    user_carts[chat_id] = []

    # Send welcome message first (in case image fails)
    await context.bot.send_message(
        chat_id=chat_id,
        text="🍔 Welcome to Raju Burger!\nLet's get started! 🎉"
    )
    logger.info("Welcome message sent")

    # Try to send welcome image
    try:
        with open('static/burger.png', 'rb') as photo:
            logger.info("Sending welcome image")
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption="Use this bot to order fictional fast food – the only fast food that is good for your health! 🍔"
            )
            logger.info("Welcome image sent successfully")
    except Exception as e:
        logger.error(f"Failed to send image: {e}", exc_info=True)

    # Send inline keyboard
    try:
        keyboard = [
            [InlineKeyboardButton("🛒 Order Food", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/menu"))]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        logger.info(f"Sending inline keyboard with menu URL: {WEBHOOK_URL}/menu")
        await update.message.reply_text("Please tap below to order your perfect lunch! 🍽️", reply_markup=reply_markup)
        logger.info("Inline keyboard sent successfully")
    except Exception as e:
        logger.error(f"Failed to send inline keyboard: {e}", exc_info=True)

# --- Telegram Webhook Handler ---
@quart_app.route('/telegram-webhook', methods=['POST'])
async def telegram_webhook():
    try:
        data = await request.get_data()
        logger.info(f"Received webhook data length: {len(data)} bytes")
        
        if not data:
            logger.error("Empty webhook data received")
            return Response("No data", status=400)
        
        # Convert the string data to JSON first
        import json
        json_data = json.loads(data.decode("utf-8"))
        logger.info(f"Webhook data: {json_data}")
        
        update = Update.de_json(json_data, bot)
        logger.info(f"Processing update ID: {update.update_id if update else 'None'}")
        
        await application.process_update(update)
        return Response("OK", status=200)
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return Response(f"Error: {str(e)}", status=500)

# Endpoint to check if the webhook is properly set
@quart_app.route('/check-webhook', methods=['GET'])
async def check_webhook():
    try:
        webhook_info = await bot.get_webhook_info()
        return {
            "webhook_url": webhook_info.url,
            "has_custom_certificate": webhook_info.has_custom_certificate,
            "pending_update_count": webhook_info.pending_update_count,
            "max_connections": webhook_info.max_connections,
            "ip_address": webhook_info.ip_address,
            "allowed_updates": webhook_info.allowed_updates
        }
    except Exception as e:
        logger.error(f"Error checking webhook: {e}", exc_info=True)
        return {"error": str(e)}

# --- Initialize Bot ---
logger.info("Initializing Telegram bot application")
application = ApplicationBuilder().token(BOT_TOKEN).build()
bot = application.bot

async def post_init(app: ApplicationBuilder):
    webhook_url = f"{WEBHOOK_URL}/telegram-webhook"
    logger.info(f"Setting Telegram webhook to: {webhook_url}")
    
    try:
        # Remove any existing webhook first
        logger.info("Removing existing webhook...")
        await app.bot.delete_webhook(drop_pending_updates=True)
        
        # Set the new webhook
        logger.info("Setting new webhook...")
        await app.bot.set_webhook(
            url=webhook_url,
            allowed_updates=['message', 'callback_query'],
            drop_pending_updates=True
        )
        
        # Verify the webhook was set properly
        webhook_info = await app.bot.get_webhook_info()
        logger.info(f"Webhook status: URL={webhook_info.url}, Pending updates: {webhook_info.pending_update_count}")
        
        if webhook_info.url != webhook_url:
            logger.error(f"Webhook URL mismatch! Expected: {webhook_url}, Got: {webhook_info.url}")
        else:
            logger.info("Webhook set successfully.")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}", exc_info=True)
        raise

# Register handlers
# Add error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# Handle web app data
async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("handle_webapp_data called")  # Log function entry
    try:
        # Verify we have web_app_data
        if not update.message or not update.message.web_app_data:
            logger.error("No web_app_data received")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Sorry, no order data was received. Please try again."
            )
            return

        logger.info(f"Raw web_app_data: {update.message.web_app_data.data}")  # Log raw data

        # Parse the order data
        try:
            data = json.loads(update.message.web_app_data.data)
            logger.info(f"Parsed JSON data: {data}")  # Log parsed data
            if not data or 'items' not in data:
                raise ValueError("Invalid order data format")
            logger.info(f"Valid order data: {data}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse order data: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Sorry, there was an error with your order data. Please try again."
            )
            return
        except ValueError as e:
            logger.error(f"Invalid order data: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Sorry, your order appears to be empty or invalid. Please try again."
            )
            return

        # Generate order token
        token = generate_token()
        logger.info(f"Generated token: {token}")

        try:
            # Generate PDF
            pdf_path = generate_order_pdf(data, token)
            logger.info(f"Generated PDF path: {pdf_path}")

            # Prepare order summary
            items_summary = "\n".join([f"• {item['quantity']}x {item['name']}" for item in data['items']])
            total = sum(float(item['price']) * int(item['quantity']) for item in data['items'])
            logger.info(f"Order summary: {items_summary}, Total: {total}")

            # Send detailed confirmation message
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"🎉 Thank you for your order!\n\n"
                     f"🔖 Order Token: {token}\n\n"
                     f"📋 Order Summary:\n{items_summary}\n\n"
                     f"💰 Total: ₹{total:.2f}\n\n"
                     f"📍 Please collect your order from counter {data.get('counter', 1)}\n\n"
                     f"📝 Your detailed order confirmation is attached below:",
                parse_mode=ParseMode.HTML
            )
            logger.info("Confirmation message sent")

            # Send PDF file
            with open(pdf_path, 'rb') as pdf:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=pdf,
                    filename=f"order_{token}.pdf",
                    caption="Your order details and bill 📄"
                )
            logger.info("PDF file sent")

            # Clean up PDF file
            os.remove(pdf_path)
            logger.info("PDF file cleaned up")

        except Exception as e:
            logger.error(f"Error generating or sending order confirmation: {e}", exc_info=True)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Your order was received, but there was an error generating the confirmation. Please contact support with your order token: " + token
            )

    except Exception as e:
        logger.error(f"Unexpected error processing order: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Sorry, there was an unexpected error processing your order. Please try again."
        )
    finally:
        logger.info("handle_webapp_data completed")  # Log function exit

# Add a general message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received message: {update.message.text}")
    await update.message.reply_text("I received your message!")

# In the section where handlers are registered:
logger.info("Registering command handlers")
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(MessageHandler(filters.ALL, handle_webapp_data))
application.add_error_handler(error_handler)

# Add a catch-all logger
async def log_all_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"ALL UPDATES: {update}")

application.add_handler(MessageHandler(filters.ALL, log_all_updates))

# --- Start the App ---
if __name__ == "__main__":
    import asyncio

    async def run():
        port = int(os.getenv("PORT", 10000))
        logger.info(f"Starting application on port {port}")
        
        # Initialize the application first
        logger.info("Initializing application...")
        await application.initialize()
        
        # Setup webhook
        try:
            await post_init(application)
        except Exception as e:
            logger.error(f"Failed to initialize webhook: {e}", exc_info=True)
            sys.exit(1)
        
        # Start the application
        logger.info("Starting application...")
        await application.start()
        
        # Start Quart server
        logger.info("Starting Quart server")
        await quart_app.run_task(host="0.0.0.0", port=port)

    asyncio.run(run())


@quart_app.before_serving
async def startup():
    logger.info("Initializing application before serving...")
    await application.initialize()
    await application.start()
    await post_init(application)

@quart_app.after_serving
async def shutdown():
    logger.info("Shutting down application...")
    await application.stop()
    await application.shutdown()