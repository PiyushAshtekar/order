import logging
import os
import json
from uuid import uuid4
from flask import Flask, render_template, request
from dotenv import load_dotenv
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Load .env
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", 5000))

# Flask app
flask_app = Flask(__name__)

# Global cart (in-memory)
user_carts = {}

# Menu
MENU_ITEMS = {
    "burger": {"name": "🍔 Burger", "price": 4.99},
    "fries": {"name": "🍟 Fries", "price": 1.49},
    "hotdog": {"name": "🌭 Hotdog", "price": 3.49},
    "taco": {"name": "🌮 Taco", "price": 3.99},
    "pizza": {"name": "🍕 Pizza", "price": 7.99},
    "donut": {"name": "🍩 Donut", "price": 1.49},
}

# Telegram bot application
app = ApplicationBuilder().token(BOT_TOKEN).build()

@flask_app.route('/')
def index():
    return 'Bot is running!'

@flask_app.route('/menu')
def menu():
    return render_template('menu.html')

@flask_app.route('/webhook', methods=['POST'])
async def webhook():
    update = Update.de_json(request.get_json(), app.bot)
    await app.process_update(update)
    return 'OK'

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_carts[chat_id] = []

    keyboard = [
        [InlineKeyboardButton("🛒 Open Mini App Menu", web_app=WebAppInfo(url="https://order-rhgz.onrender.com/menu"))],
        *[
            [InlineKeyboardButton(f"{item['name']} - ${item['price']}", callback_data=key)]
            for key, item in MENU_ITEMS.items()
        ],
        [InlineKeyboardButton("🛍 View Cart", callback_data='view_cart')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome! Select items or use Mini App:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id

    if query.data == 'view_cart':
        cart = user_carts.get(chat_id, [])
        if not cart:
            await query.edit_message_text("🛒 Your cart is empty.")
            return

        cart_text = "\n".join([f"- {MENU_ITEMS[item]['name']} - ${MENU_ITEMS[item]['price']}" for item in cart])
        total = sum([MENU_ITEMS[item]['price'] for item in cart])
        cart_text += f"\n\nTotal: ${total}"
        keyboard = [[InlineKeyboardButton("✅ Checkout", callback_data='checkout')]]
        await query.edit_message_text(cart_text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'checkout':
        cart = user_carts.get(chat_id, [])
        if not cart:
            await query.edit_message_text("Cart is empty.")
            return

        file_path = generate_invoice_pdf(chat_id, cart)
        await context.bot.send_document(chat_id=chat_id, document=open(file_path, 'rb'), filename="invoice.pdf")
        os.remove(file_path)
        user_carts[chat_id] = []
        await query.edit_message_text("✅ Order confirmed! Invoice sent.")

    elif query.data in MENU_ITEMS:
        user_carts.setdefault(chat_id, []).append(query.data)
        await context.bot.send_message(chat_id=chat_id, text=f"{MENU_ITEMS[query.data]['name']} added to cart!")

async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📥 Received web_app_data:", update.message.web_app_data.data)

    try:
        data = json.loads(update.message.web_app_data.data)
        items = data.get('items', [])

        if not items:
            await update.message.reply_text("❌ Cart is empty.")
            return

        chat_id = update.effective_chat.id
        user_carts[chat_id] = []
        
        item_counts = {}
        for item in items:
            if item not in MENU_ITEMS:
                await update.message.reply_text(f"❌ Invalid item: {item}")
                continue
                
            user_carts[chat_id].append(item)
            item_counts[item] = item_counts.get(item, 0) + 1

        # Create a summary message
        summary = "🛒 Added to cart:\n"
        for item, count in item_counts.items():
            summary += f"- {count}x {MENU_ITEMS[item]['name']}\n"
        
        await update.message.reply_text(summary)
    except Exception as e:
        print("❌ Error in web_app_data_handler:", e)
        await update.message.reply_text("⚠️ Something went wrong adding your items.")


def generate_invoice_pdf(chat_id, cart):
    # Create a temporary directory if it doesn't exist
    temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    filename = f"invoice_{chat_id}_{uuid4().hex}.pdf"
    file_path = os.path.join(temp_dir, filename)

    c = canvas.Canvas(file_path, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(50, 750, "Invoice")
    c.drawString(50, 735, f"User ID: {chat_id}")
    y = 700
    total = 0
    for item_key in cart:
        item = MENU_ITEMS[item_key]
        c.drawString(50, y, f"{item['name']} - ${item['price']}")
        y -= 20
        total += item['price']
    c.drawString(50, y - 20, f"Total: ${total}")
    c.save()
    return file_path

def set_webhook():
    import asyncio
    webhook_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url=https://order-rhgz.onrender.com/webhook"
    asyncio.run(app.bot.set_webhook(url=webhook_url))
    logging.info(f"Webhook set to {webhook_url}")

def main():
    if not BOT_TOKEN:
        logging.error("BOT TOKEN is missing.")
        return

    # Configure logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

if __name__ == '__main__':
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    app.run_polling()
