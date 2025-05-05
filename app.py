import logging
import os
import json
from uuid import uuid4
from datetime import datetime
from flask import Flask, render_template, request
from dotenv import load_dotenv
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
# import secrets


# Load .env
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", 5000))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://order-rhgz.onrender.com/webhook")

# Flask app
flask_app = Flask(__name__)

# Global cart (in-memory)
user_carts = {}

# Menu (prices in INR to match menu.html)
MENU_ITEMS = {
    "burger": {"name": "🍔 Burger", "price": 150.00},
    "fries": {"name": "🍟 Fries", "price": 100.00},
    "hotdog": {"name": "🌭 Hotdog", "price": 200.00},
    "taco": {"name": "🌮 Taco", "price": 150.00},
    "pizza": {"name": "🍕 Pizza", "price": 350.00},
    "donut": {"name": "🍩 Donut", "price": 80.00},
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
def webhook():
    # Verify secret token if set
    if os.getenv("WEBHOOK_SECRET"):
        token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
        if token != os.getenv("WEBHOOK_SECRET"):
            logging.warning("❌ Invalid secret token received")
            return 'Unauthorized', 401
    
    try:
        data = request.get_json()
        logging.info(f"📥 Received webhook data: {data}")
        update = Update.de_json(data, app.bot)
        app.process_update(update)
        return 'OK'
    except Exception as e:
        logging.error(f"❌ Error processing webhook: {str(e)}")
        return 'Error', 500
# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_carts[chat_id] = []

    # Send welcome message with inline button
    try:
        keyboard = [
            [InlineKeyboardButton(
                    "🛒 Order Food", 
                    web_app=WebAppInfo(url="https://order-rhgz.onrender.com/menu"))]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🍔 Welcome to Raju Burger! 🍔\n\n"
            "Use this bot to order fictional fast food – the only fast food that is good for your health!\n\n"
            "Tap the button below to view the menu and place your order! 🎉",
            reply_markup=reply_markup
        )
    except Exception as e:
        logging.error(f"Failed to send welcome message: {e}")
        await update.message.reply_text("⚠️ Something went wrong. Please try again.")

async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("📥 Received web_app_data: %s", update.message.web_app_data.data)

    try:
        # Close the web app first
        await update.effective_message.delete()
        
        data = json.loads(update.message.web_app_data.data)
        items = data.get('items', [])
        comment = data.get('comment', '')
        payment_method = data.get('paymentMethod', 'unknown')

        if not items:
            logging.warning("Empty cart received")
            await update.message.reply_text("❌ Cart is empty.")
            return

        chat_id = update.effective_chat.id
        user_carts[chat_id] = [item['item'] for item in items for _ in range(item['quantity'])]

        # Generate order token
        order_id = str(uuid4())[:8].upper()
        logging.info("Generated order ID: %s", order_id)

        # Create order confirmation message
        item_counts = {}
        total = 0
        for item in user_carts[chat_id]:
            item_counts[item] = item_counts.get(item, 0) + 1
            total += MENU_ITEMS[item]['price']

        confirmation = f"🎉 Order Successfully Placed!\n\n"
        confirmation += f"🔢 Order Token: #{order_id}\n\n"
        confirmation += "📋 Order Summary:\n"
        for item, count in item_counts.items():
            item_total = MENU_ITEMS[item]['price'] * count
            confirmation += f"• {count}× {MENU_ITEMS[item]['name']} = ₹{item_total:.2f}\n"
        confirmation += f"\n💰 Total: ₹{total:.2f}"
        confirmation += f"\n💳 Payment Method: {payment_method.capitalize()}"
        if comment.strip():
            confirmation += f"\n\n💭 Your Comment:\n{comment}"

        # Generate and send PDF bill
        try:
            file_path = generate_invoice_pdf(chat_id, user_carts[chat_id], order_id, comment)
            await context.bot.send_document(
                chat_id=chat_id,
                document=open(file_path, 'rb'),
                filename=f"invoice_{order_id}.pdf",
                caption="📄 Here's your order invoice!"
            )
            os.remove(file_path)
        except Exception as pdf_error:
            logging.error("Failed to generate or send PDF: %s", pdf_error)
            confirmation += "\n\n⚠️ Failed to generate invoice, but your order is confirmed."

        # Send confirmation message
        await update.message.reply_text(confirmation)
        user_carts[chat_id] = []  # Clear cart after order
    except Exception as e:
        logging.error("❌ Error in web_app_data_handler: %s", str(e))
        await update.message.reply_text("⚠️ Something went wrong processing your order. Please try again.")
        
def generate_invoice_pdf(chat_id, cart, order_id, comment=''):
    temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    filename = f"invoice_{chat_id}_{uuid4().hex}.pdf"
    file_path = os.path.join(temp_dir, filename)

    c = canvas.Canvas(file_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "Order Invoice")
    
    c.setFont("Helvetica", 12)
    c.drawString(50, 720, f"Order ID: #{order_id}")
    c.drawString(50, 700, f"User ID: {chat_id}")
    c.drawString(50, 680, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    c.line(50, 660, 550, 660)
    
    y = 630
    total = 0
    item_counts = {}
    
    for item_key in cart:
        item_counts[item_key] = item_counts.get(item_key, 0) + 1
    
    c.drawString(50, y, "Item")
    c.drawString(300, y, "Quantity")
    c.drawString(400, y, "Price")
    c.drawString(500, y, "Total")
    y -= 30
    
    for item_key, count in item_counts.items():
        item = MENU_ITEMS[item_key]
        item_total = item['price'] * count
        total += item_total
        
        c.drawString(50, y, item['name'])
        c.drawString(300, y, str(count))
        c.drawString(400, y, f"₹{item['price']:.2f}")
        c.drawString(500, y, f"₹{item_total:.2f}")
        y -= 20
    
    y -= 20
    c.line(50, y, 550, y)
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(400, y, "Total:")
    c.drawString(500, y, f"₹{total:.2f}")
    
    if comment.strip():
        y -= 40
        c.setFont("Helvetica", 12)
        c.drawString(50, y, "Customer Comment:")
        y -= 20
        for line in comment.split('\n'):
            c.drawString(50, y, line)
            y -= 15
    
    c.save()
    return file_path

async def set_webhook():
    try:
        await app.bot.set_webhook(
            url=WEBHOOK_URL,
            secret_token=os.getenv("WEBHOOK_SECRET")  # Add this line
        )
        logging.info(f"✅ Webhook successfully set to {WEBHOOK_URL}")
    except Exception as e:
        logging.error(f"❌ Failed to set webhook: {str(e)}")
        raise

def main():
    if not BOT_TOKEN:
        logging.error("BOT TOKEN is missing.")
        return

    # Configure logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))

    # Initialize bot
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_webhook())

    # Run Flask app
    flask_app.run(host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    main()