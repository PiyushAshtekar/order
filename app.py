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
        comment = data.get('comment', '')

        if not items:
            await update.message.reply_text("❌ Cart is empty.")
            return

        chat_id = update.effective_chat.id
        user_carts[chat_id] = []
        
        item_counts = {}
        total = 0
        for item in items:
            if item not in MENU_ITEMS:
                await update.message.reply_text(f"❌ Invalid item: {item}")
                continue
                
            user_carts[chat_id].append(item)
            item_counts[item] = item_counts.get(item, 0) + 1
            total += MENU_ITEMS[item]['price']

        # Generate token number and order ID
        token_number = str(uuid4())[:6].upper()
        order_id = str(uuid4())[:8].upper()
        
        # Create a detailed order confirmation
        confirmation = f"🎉 Order #{order_id} Confirmed!\n"
        confirmation += f"🎫 Your Token Number: {token_number}\n\n"
        confirmation += "📋 Order Summary:\n"
        for item, count in item_counts.items():
            item_total = MENU_ITEMS[item]['price'] * count
            confirmation += f"• {count}× {MENU_ITEMS[item]['name']} = ${item_total:.2f}\n"
        
        confirmation += f"\n💰 Total: ${total:.2f}"
        
        if comment.strip():
            confirmation += f"\n\n💭 Your Comment:\n{comment}"
        
        # Generate PDF bill
        file_path = generate_invoice_pdf(chat_id, user_carts[chat_id], token_number, order_id)
        
        # Send confirmation message and PDF
        await update.message.reply_text(confirmation)
        await context.bot.send_document(
            chat_id=chat_id,
            document=open(file_path, 'rb'),
            filename=f"bill_{order_id}.pdf",
            caption=f"🧾 Here's your bill for Order #{order_id}"
        )
        
        # Clean up PDF file
        os.remove(file_path)
        
        # Send close_webapp instruction
        response_data = {
            "type": "close_webapp",
            "token": token_number
        }
        await update.message.reply_text(
            text="Order processed successfully!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Close", callback_data=json.dumps(response_data))]
            ])
        )
    except Exception as e:
        print("❌ Error in web_app_data_handler:", e)
        await update.message.reply_text("⚠️ Something went wrong adding your items.")


def generate_invoice_pdf(chat_id, cart, token_number, order_id):
    # Create a temporary directory if it doesn't exist
    temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    filename = f"bill_{order_id}.pdf"
    file_path = os.path.join(temp_dir, filename)

    c = canvas.Canvas(file_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "Order Bill")
    
    c.setFont("Helvetica", 12)
    c.drawString(50, 720, f"Order #: {order_id}")
    c.drawString(50, 700, f"Token Number: {token_number}")
    c.drawString(50, 680, f"User ID: {chat_id}")
    
    # Draw line separator
    c.line(50, 670, 550, 670)
    
    # Items header
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 650, "Item")
    c.drawString(350, 650, "Quantity")
    c.drawString(450, 650, "Price")
    
    y = 620
    total = 0
    item_counts = {}
    
    # Count items
    for item_key in cart:
        item_counts[item_key] = item_counts.get(item_key, 0) + 1
    
    # Draw items
    c.setFont("Helvetica", 12)
    for item_key, count in item_counts.items():
        item = MENU_ITEMS[item_key]
        item_total = item['price'] * count
        c.drawString(50, y, item['name'])
        c.drawString(350, y, str(count))
        c.drawString(450, y, f"${item_total:.2f}")
        y -= 20
        total += item_total
    
    # Draw line separator
    c.line(50, y - 10, 550, y - 10)
    
    # Draw total
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, y - 30, "Total:")
    c.drawString(450, y - 30, f"${total:.2f}")
    
    # Footer
    c.setFont("Helvetica", 10)
    c.drawString(50, 50, "Thank you for your order!")
    c.drawString(50, 35, "Please keep this bill for reference.")
    
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
