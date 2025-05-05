import logging
import os
import json
from uuid import uuid4
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackContext

# Load .env
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", 5000))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Make sure this is set correctly


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
logging.basicConfig(level=logging.INFO)


@flask_app.route('/')
def index():
    return 'Bot is running!'


@flask_app.route('/menu')
def menu():
    return render_template('menu.html')


@flask_app.route('/webhook', methods=['POST'])  #  Ensure this is POST
def webhook():
    """This is where Telegram sends updates."""
    try:
        data = request.get_json()  # Get the update data as JSON
        logging.info(f"Received webhook data: {data}")
        update = Update.de_json(data, app.bot)  # Pass the data to Update.de_json
        app.process_update(update)  # Process the update using the bot's application
        return jsonify(status='OK')  #  Return a JSON response
    except Exception as e:
        logging.error(f"Error processing webhook: {e}")
        return jsonify(status='ERROR', message=str(e)), 500  # Return a JSON error response



# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message with an inline button to open the menu."""
    chat_id = update.effective_chat.id
    user_carts[chat_id] = []  # Initialize user's cart

    # Create an inline keyboard with a button that opens the web app.
    keyboard = [
        [InlineKeyboardButton(
            "🛒 Order Food",
            web_app=WebAppInfo(url=f"{WEBHOOK_URL}/menu")  # Use the correct URL
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        # Send the welcome message with the inline keyboard.
        await context.bot.send_message(
            chat_id=chat_id,
            text="🍔 Welcome to Raju Burger! 🍔\n\n"
                 "Use this bot to order fictional fast food – the only fast food that is good for your health!\n\n"
                 "Tap the button below to view the menu and place your order! 🎉",
            reply_markup=reply_markup
        )
    except Exception as e:
        logging.error(f"Failed to send welcome message: {e}")



async def process_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes the order data sent from the web app."""
    chat_id = update.effective_chat.id
    # Ensure the message is coming from a Web App
    if update.message and update.message.web_app_data:
        try:
            # Parse the order data from the Web App
            order_data = json.loads(update.message.web_app_data.data)
            logging.info(f"Order data received: {order_data}")

            # Extract relevant information
            order_items = order_data.get("items", [])
            comment = order_data.get("comment", "")
            payment_method = order_data.get("paymentMethod", "Cash")  # Default to cash if not provided

            if not order_items:
                await context.bot.send_message(chat_id=chat_id, text="❌ No items found in your order.")
                return

            # Calculate total price
            total_price = 0
            order_details_text = "🧾 Order Details:\n"
            for item_data in order_items:
                item_name = item_data.get("item")
                quantity = item_data.get("quantity", 0)
                if item_name and quantity > 0:
                    if item_name in MENU_ITEMS:
                        item_price = MENU_ITEMS[item_name]["price"]
                        total_price += item_price * quantity
                        order_details_text += f"- {MENU_ITEMS[item_name]['name']} x {quantity}: ₹{item_price * quantity:.2f}\n"
                    else:
                        order_details_text += f"- {item_name} x {quantity}: Price N/A\n"
                        total_price += 0  # Consider how to handle unknown items

            order_details_text += f"Total: ₹{total_price:.2f}\n"
            order_details_text += f"Payment Method: {payment_method}\n"
            if comment:
                order_details_text += f"Comment: {comment}\n"

            # Generate a unique order/counter number
            order_number = str(uuid4()).split('-')[0].upper()
            order_details_text += f"Order Number: {order_number}\n"

            # Generate and send the bill as a PDF
            pdf_file = generate_bill_pdf(order_number, order_items, total_price, comment, chat_id) # Pass chat_id
            if pdf_file:
                with open(pdf_file, 'rb') as pdf_document:
                    await context.bot.send_document(chat_id=chat_id, document=pdf_document,
                                                  caption=order_details_text)
                os.remove(pdf_file)  # Clean up the PDF file

            else:
                await context.bot.send_message(chat_id=chat_id,
                                              text=f"✅ Order confirmed! Your order number is {order_number}.  However, there was an issue generating your bill. Please contact support.")
                await context.bot.send_message(chat_id=chat_id, text=order_details_text)

        except json.JSONDecodeError:
            await context.bot.send_message(chat_id=chat_id,
                                          text="❌ Invalid data received from the menu. Please try again.")
            logging.error("Invalid JSON data received from Web App.")
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id,
                                          text=f"❌ An error occurred while processing your order: {e}")
            logging.error(f"Error processing order: {e}")
    else:
        await context.bot.send_message(chat_id=chat_id,
                                      text="❌ This command is only valid when used from the Web App.")



def generate_bill_pdf(order_number, order_items, total, comment, chat_id):
    """Generates a PDF bill for the order."""
    try:
        # Create a unique filename for the PDF using the order number and chat_id
        file_path = f"order_bill_{chat_id}_{order_number}.pdf"
        c = canvas.Canvas(file_path, pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, "Raju Burger - Order Bill")  # Consistent title
        c.setFont("Helvetica", 12)
        c.drawString(50, 730, f"Order Number: {order_number}")
        c.drawString(50, 710, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        y = 680
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "Item")
        c.drawString(300, y, "Quantity")
        c.drawString(400, y, "Price")
        c.drawString(500, y, "Total")
        y -= 10
        c.line(50, y, 550, y)  # Add a line

        c.setFont("Helvetica", 12)
        for item_data in order_items:
            item_name = item_data.get("item")
            quantity = item_data.get("quantity", 0)
            if item_name and quantity > 0:
                if item_name in MENU_ITEMS:
                    item_price = MENU_ITEMS[item_name]["price"]
                    c.drawString(50, y, MENU_ITEMS[item_name]["name"])
                    c.drawString(300, y, str(quantity))
                    c.drawString(400, y, f"₹{item_price:.2f}")
                    c.drawString(500, y, f"₹{item_price * quantity:.2f}")
                    y -= 20
                else:
                    c.drawString(50, y, item_name)
                    c.drawString(300, y, str(quantity))
                    c.drawString(400, y, "N/A")
                    c.drawString(500, y, "N/A")
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
    except Exception as e:
        logging.error(f"Error generating PDF bill: {e}")
        return None  # Return None in case of an error


async def set_webhook(context: CallbackContext):
    """Sets the bot's webhook."""
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook" # Correctly construct the webhook URL
        await context.bot.set_webhook(
            url=webhook_url,
            #secret_token=os.getenv("WEBHOOK_SECRET")  # Add this line if you have a secret token
        )
        logging.info(f"Webhook set to {webhook_url}")
    except Exception as e:
        logging.error(f"Failed to set webhook: {e}")



def main():
    """Main function to start the bot and Flask app."""
    if not BOT_TOKEN:
        logging.error("BOT TOKEN is missing.")
        return

    # Add handlers to the bot's application.
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.web_app_data.new(), process_order))

    # Run the bot and Flask app
    try:
        # Set the webhook
        app.run_polling(allowed_updates=Update.ALL) # Use long polling
        # set_webhook() # Removed set_webhook()
        # Start the Flask app (for the menu and webhook)
        # flask_app.run(host="0.0.0.0", port=int(PORT), debug=True) # Removed flask_app.run
    except Exception as e:
        logging.error(f"Error starting the bot or Flask app: {e}")



if __name__ == "__main__":
    main()
